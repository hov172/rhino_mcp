"""
MCP server for Rhino 3D.

The server talks to Rhino 8.11+ through McNeel's ``rhinocode`` CLI. Rhino must
be running and its script server must be started with ``StartScriptServer``.
"""

from __future__ import annotations

import argparse
import importlib
import os
import pkgutil
import sys

import yaml
from rhmcp.tools_helpers.tool_runtime import RuntimeMCP as FastMCP

from mcp.types import ToolAnnotations

from rhmcp.tools_helpers.rhinoscript_docs import RHINOSCRIPT_MODULES, get_function

_TRANSPORTS = ("stdio", "http")


def _resolve_profile(
    name: str,
    profiles: dict,
    _depth: int = 0,
) -> set[str] | None:
    """Resolve a profile name to a set of module names, or None for 'load all'."""
    if _depth > 3:
        raise ValueError(
            f"Profile inheritance too deep or cyclic near {name!r}"
        )
    if name not in profiles:
        valid = ", ".join(sorted(profiles))
        print(
            f"rhino-mcp: unknown profile {name!r}. Valid: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)
    profile = profiles[name]
    if profile is None:
        return None
    if isinstance(profile, list):
        return set(profile)
    if isinstance(profile, dict):
        base_name = profile.get("_extends")
        extra: list[str] = profile.get("_modules", [])
        base: set[str] = (
            _resolve_profile(base_name, profiles, _depth + 1)
            if base_name
            else set()
        )
        if base is None:  # extends 'full' → full
            return None
        return base | set(extra)
    raise ValueError(f"Invalid profile definition for {name!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP server for Rhino 3D.")
    parser.add_argument(
        "--transport",
        "-t",
        choices=_TRANSPORTS,
        default="stdio",
        help="Transport protocol (default: stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (default: 127.0.0.1).")
    parser.add_argument("--port", "-p", type=int, default=8000, help="HTTP port (default: 8000).")
    parser.add_argument(
        "--profile",
        default=os.environ.get("RHMCP_PROFILE") or "full",
        metavar="PROFILE",
        help=(
            "Tool profile to load: core, grasshopper, rendering, urban, bim, full. "
            "Env: RHMCP_PROFILE. Default: full."
        ),
    )
    parser.add_argument(
        "--compact",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("RHMCP_COMPACT", "1").strip().lower() not in ("0", "false", "no"),
        help=(
            "Compact mode: 3 meta-tools instead of full schemas (default: on). "
            "Use --no-compact or RHMCP_COMPACT=0 to load all schemas upfront."
        ),
    )
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    with open(os.path.join(data_dir, "prompts.yml"), encoding="utf-8") as fh:
        prompts = yaml.safe_load(fh)

    with open(os.path.join(data_dir, "profiles.yml"), encoding="utf-8") as fh:
        profiles_data = yaml.safe_load(fh)

    active_modules = _resolve_profile(args.profile, profiles_data)

    mcp = FastMCP("rhino-mcp", instructions=str(prompts["initial_instructions"]))

    @mcp.prompt()
    def rhinoscript_workflow() -> str:
        """Mandatory workflow for writing RhinoScript Python — look up docs before coding."""
        return str(prompts["rhinoscript_workflow"])

    @mcp.prompt()
    def asset_general_strategy() -> str:
        """Decision-tree strategy for creating, modifying, and querying Rhino objects."""
        return str(prompts["asset_general_strategy"])

    @mcp.resource("rhinoscript://modules")
    def resource_list_modules() -> str:
        lines = ["# RhinoScript Modules\n", "| Module | Functions |", "|--------|-----------|"]
        for module in RHINOSCRIPT_MODULES:
            lines.append("| {} | {} |".format(module["ModuleName"], len(module["functions"])))
        return "\n".join(lines)

    @mcp.resource("rhinoscript://module/{module_name}")
    def resource_get_module(module_name: str) -> str:
        for module in RHINOSCRIPT_MODULES:
            if module["ModuleName"].lower() == module_name.lower():
                lines = ["# RhinoScript Module: {}\n".format(module["ModuleName"])]
                for func in module["functions"]:
                    lines.append("## {}\n```python\nrs.{}\n```\n{}\n".format(func["Name"], func["Signature"], func["Description"]))
                return "\n".join(lines)
        return "Module '{}' not found.".format(module_name)

    @mcp.resource("rhinoscript://function/{function_name}")
    def resource_get_function(function_name: str) -> str:
        func = get_function(function_name)
        if not func:
            return "Function '{}' not found.".format(function_name)
        return "# {Name}\n\n**Module:** {module}\n\n```python\nrs.{Signature}\n```\n\n{Description}\n\nReturns: {Returns}".format(**func)

    if args.compact:
        from rhmcp.tools_helpers.compact_registry import CompactRegistry

        _registry = CompactRegistry()
        _registry.load_from_modules(active_modules)
        _n = len(_registry._tools)

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
        def list_rhino_tools(category: str = "") -> list[dict]:
            """List all available Rhino tools with one-line descriptions."""
            return _registry.list_tools(category)

        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
        def describe_rhino_tool(name: str) -> dict:
            """Get the full description and input schema for a specific Rhino tool."""
            return _registry.describe_tool(name)

        @mcp.tool(annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False))
        async def call_rhino_tool(name: str, arguments: dict | None = None) -> object:
            """Call any Rhino tool by name with a dict of arguments."""
            return await _registry.call_tool(name, arguments or {})

        print(
            f"Rhino MCP: compact mode — 3 meta-tools loaded ({_n} tools available on demand)",
            file=sys.stderr,
        )
    else:
        import rhmcp.tools as tools_pkg

        _loaded = []
        for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_"):
                continue
            if active_modules is not None and modname not in active_modules:
                continue
            mod = importlib.import_module("rhmcp.tools.{:s}".format(modname))
            if hasattr(mod, "register"):
                mod.register(mcp)
                _loaded.append(modname)

        if args.profile != "full":
            print(
                f"Rhino MCP: profile '{args.profile}' — {len(_loaded)} modules loaded",
                file=sys.stderr,
            )

    # Non-blocking startup connectivity check — printed to stderr only.
    try:
        from rhmcp.tools_helpers.plugin_client import health_check
        hc = health_check(timeout=1.0)
        if hc.get("ok"):
            print(
                "Rhino MCP: plugin connected at {}:{} ({}ms, Rhino {})".format(
                    hc["host"], hc["port"], hc["latency_ms"], hc.get("rhino", "?")
                ),
                file=sys.stderr,
            )
        else:
            print(
                "Rhino MCP: plugin not reachable at startup ({}) — start Rhino and the MCPStart command".format(
                    hc.get("error_code", "unknown")
                ),
                file=sys.stderr,
            )
    except Exception:
        pass

    transport = args.transport
    if transport == "http":
        import ipaddress
        import uvicorn
        from rhmcp.tools_helpers.http_transport import build_app, configure_security
        cert = os.environ.get("RHINO_MCP_HTTP_TLS_CERT")
        key = os.environ.get("RHINO_MCP_HTTP_TLS_KEY")
        try:
            local = args.host == "localhost" or ipaddress.ip_address(args.host).is_loopback
        except ValueError:
            local = False
        if bool(cert) != bool(key) or (not local and not (cert and key)):
            parser.error("Non-loopback HTTP requires RHINO_MCP_HTTP_TLS_CERT and RHINO_MCP_HTTP_TLS_KEY.")
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = "/"
        mcp.settings.stateless_http = True
        configure_security(mcp, args.host)
        app = build_app(mcp.streamable_http_app(), args.port)
        uvicorn.run(app, host=args.host, port=args.port, ssl_certfile=cert, ssl_keyfile=key)
        return 0

    mcp.run(transport=transport)
    return 0

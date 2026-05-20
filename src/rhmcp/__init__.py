"""
MCP server for Rhino 3D.

The server talks to Rhino 8.11+ through McNeel's ``rhinocode`` CLI. Rhino must
be running and its script server must be started with ``StartScriptServer``.
"""

from __future__ import annotations

import argparse
import collections
import importlib
import os
import pkgutil
import secrets
import sys
import time

import yaml
from mcp.server.fastmcp import FastMCP

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

    # Install optional telemetry interceptor after all tools are registered.
    from rhmcp import telemetry
    telemetry.install(mcp)

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
        from starlette.middleware.cors import CORSMiddleware

        transport = "streamable-http"
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = "/"
        mcp.settings.stateless_http = True

        _AUTH_TOKEN = secrets.token_hex(32)
        print(f"Rhino MCP auth token: {_AUTH_TOKEN}", file=sys.stderr)
        print("Pass this as: Authorization: Bearer <token>", file=sys.stderr)

        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Mount, Route

        _RATE_LIMIT_RPM = int(os.environ.get("RHINO_MCP_RATE_LIMIT_RPM", "120"))

        async def health(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok"})

        original_app = mcp.streamable_http_app

        def app_with_cors():
            from starlette.applications import Starlette
            from starlette.middleware.base import BaseHTTPMiddleware
            from starlette.responses import Response as StarletteResponse

            mcp_app = original_app()
            _allowed_origins = [
                "http://localhost",
                "http://127.0.0.1",
                f"http://localhost:{args.port}",
                f"http://127.0.0.1:{args.port}",
            ]
            mcp_app.add_middleware(
                CORSMiddleware,
                allow_origins=_allowed_origins,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
            )

            class _TokenAuth(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    if request.url.path == "/health" or request.method == "OPTIONS":
                        return await call_next(request)
                    auth = request.headers.get("Authorization", "")
                    if not secrets.compare_digest(auth, f"Bearer {_AUTH_TOKEN}"):
                        return StarletteResponse(
                            '{"error":"Unauthorized"}',
                            status_code=401,
                            media_type="application/json",
                        )
                    return await call_next(request)

            # R6-9: Per-token sliding-window rate limiter (120 req/min default)
            class _RateLimiter(BaseHTTPMiddleware):
                def __init__(self, app):
                    super().__init__(app)
                    self._windows: dict = {}
                    self._lock = __import__("threading").Lock()

                async def dispatch(self, request, call_next):
                    if request.url.path == "/health" or request.method == "OPTIONS":
                        return await call_next(request)
                    token = request.headers.get("Authorization", "anonymous")
                    now = time.time()
                    window_start = now - 60.0
                    with self._lock:
                        hits = self._windows.get(token, collections.deque())
                        while hits and hits[0] < window_start:
                            hits.popleft()
                        if len(hits) >= _RATE_LIMIT_RPM:
                            return StarletteResponse(
                                '{"error":"Rate limit exceeded"}',
                                status_code=429,
                                media_type="application/json",
                            )
                        hits.append(now)
                        self._windows[token] = hits
                        # Evict oldest tokens if cache is too large (R7-3)
                        _MAX_WINDOW_KEYS = 4096
                        if len(self._windows) > _MAX_WINDOW_KEYS:
                            stale = [k for k, v in self._windows.items() if not v]
                            for k in stale:
                                del self._windows[k]
                            if len(self._windows) > _MAX_WINDOW_KEYS:
                                evict_count = len(self._windows) - _MAX_WINDOW_KEYS // 2
                                for k in list(self._windows.keys())[:evict_count]:
                                    del self._windows[k]
                    return await call_next(request)

            app = Starlette(routes=[
                Route("/health", health),
                Mount("/", app=mcp_app),
            ])
            app.add_middleware(_TokenAuth)
            app.add_middleware(_RateLimiter)
            return app

        mcp.streamable_http_app = app_with_cors  # type: ignore[method-assign]

    mcp.run(transport=transport)
    return 0

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

import yaml
from mcp.server.fastmcp import FastMCP

from rhmcp.tools_helpers.rhinoscript_docs import RHINOSCRIPT_MODULES, get_function

_TRANSPORTS = ("stdio", "http")


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
    args = parser.parse_args()

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    with open(os.path.join(data_dir, "prompts.yml"), encoding="utf-8") as fh:
        prompts = yaml.safe_load(fh)

    mcp = FastMCP("rhino-mcp", instructions=str(prompts["initial_instructions"]))

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

    for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
        if modname.startswith("_"):
            continue
        mod = importlib.import_module("rhmcp.tools.{:s}".format(modname))
        if hasattr(mod, "register"):
            mod.register(mcp)

    transport = args.transport
    if transport == "http":
        from mcp.server.fastmcp.server import TransportSecuritySettings
        from starlette.middleware.cors import CORSMiddleware

        transport = "streamable-http"
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = "/"
        mcp.settings.stateless_http = True
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )

        original_app = mcp.streamable_http_app

        def app_with_cors():
            app = original_app()
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            )
            return app

        mcp.streamable_http_app = app_with_cors  # type: ignore[method-assign]

    mcp.run(transport=transport)
    return 0

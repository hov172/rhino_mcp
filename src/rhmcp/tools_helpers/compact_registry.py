from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from mcp.server.fastmcp import FastMCP


class _ToolProxy:
    """Mutable proxy around a FastMCP Tool so tests can replace .run."""

    def __init__(self, tool: Any) -> None:
        self._tool = tool
        self.name: str = tool.name
        self.description: str = tool.description or ""
        self.parameters: dict = tool.parameters

    async def run(self, arguments: dict) -> Any:
        return await self._tool.run(arguments)


class CompactRegistry:
    """Captures all tool registrations via a shadow FastMCP for lazy dispatch."""

    def __init__(self) -> None:
        self._tools: dict[str, _ToolProxy] = {}

    def load_from_modules(self, active_modules: set[str] | None) -> None:
        shadow = FastMCP("shadow")
        import rhmcp.tools as tools_pkg

        for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_"):
                continue
            if active_modules is not None and modname not in active_modules:
                continue
            mod = importlib.import_module(f"rhmcp.tools.{modname}")
            if hasattr(mod, "register"):
                mod.register(shadow)

        self._tools = {
            name: _ToolProxy(tool)
            for name, tool in shadow._tool_manager._tools.items()
        }

    def list_tools(self, category: str = "") -> list[dict]:
        results = []
        for name, proxy in self._tools.items():
            if category and category.lower() not in name.lower():
                continue
            first_line = (proxy.description or "").split("\n")[0].strip()
            results.append({"name": name, "description": first_line})
        results.sort(key=lambda t: t["name"])
        return results

    def describe_tool(self, name: str) -> dict:
        proxy = self._tools.get(name)
        if not proxy:
            return {
                "error": f"Tool '{name}' not found. Call list_rhino_tools() to see available tools."
            }
        return {
            "name": name,
            "description": proxy.description,
            "input_schema": proxy.parameters,
        }

    async def call_tool(self, name: str, arguments: dict) -> Any:
        proxy = self._tools.get(name)
        if not proxy:
            raise ValueError(
                f"Tool '{name}' not found. Call list_rhino_tools() to see available tools."
            )
        return await proxy.run(arguments)

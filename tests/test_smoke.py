"""
Smoke tests — verify all tool modules load and register without errors.
No Rhino instance required.
"""

from __future__ import annotations

import importlib
import pkgutil
import unittest
from unittest.mock import patch

import rhmcp.tools as _tools_pkg
from mcp.server.fastmcp import FastMCP


class TestAllModulesLoad(unittest.TestCase):
    def test_all_tool_modules_import(self) -> None:
        """Every module in rhmcp.tools must import without errors."""
        tools_dir = _tools_pkg.__path__[0]
        errors: list[str] = []
        for info in pkgutil.iter_modules([tools_dir]):
            try:
                importlib.import_module(f"rhmcp.tools.{info.name}")
            except Exception as exc:
                errors.append(f"{info.name}: {exc}")
        self.assertFalse(errors, "Import errors:\n" + "\n".join(errors))

    def test_all_tool_modules_register(self) -> None:
        """Every module with a register() must register tools without errors."""
        tools_dir = _tools_pkg.__path__[0]
        errors: list[str] = []
        total = 0
        for info in pkgutil.iter_modules([tools_dir]):
            mod = importlib.import_module(f"rhmcp.tools.{info.name}")
            if not hasattr(mod, "register"):
                continue
            try:
                mcp = FastMCP(f"smoke-{info.name}")
                mod.register(mcp)
                total += len(mcp._tool_manager._tools)
            except Exception as exc:
                errors.append(f"{info.name}: {exc}")
        self.assertFalse(errors, "Register errors:\n" + "\n".join(errors))
        self.assertGreaterEqual(total, 300, f"Expected ≥300 tools, got {total}")

    def test_tool_names_unique(self) -> None:
        """No two tools may share the same name across all modules."""
        tools_dir = _tools_pkg.__path__[0]
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for info in pkgutil.iter_modules([tools_dir]):
            mod = importlib.import_module(f"rhmcp.tools.{info.name}")
            if not hasattr(mod, "register"):
                continue
            mcp = FastMCP(f"dup-{info.name}")
            mod.register(mcp)
            for name in mcp._tool_manager._tools:
                if name in seen:
                    duplicates.append(f"{name} (in {info.name} and {seen[name]})")
                else:
                    seen[name] = info.name
        self.assertFalse(duplicates, "Duplicate tool names:\n" + "\n".join(duplicates))

    def test_helpers_import(self) -> None:
        """All tools_helpers modules must import cleanly."""
        for mod_name in ("backend", "errors", "validate", "plugin_client", "rhinocode"):
            with self.subTest(mod_name):
                importlib.import_module(f"rhmcp.tools_helpers.{mod_name}")


if __name__ == "__main__":
    unittest.main()

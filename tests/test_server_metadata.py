from __future__ import annotations

import asyncio
import os
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_DIR, "src")


class ServerMetadataTest(unittest.TestCase):
    def _list_tools(self, extra_env: dict | None = None) -> list[str]:
        async def run() -> list[str]:
            env = os.environ.copy()
            env["PYTHONPATH"] = SRC_DIR
            if extra_env:
                env.update(extra_env)
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "rhmcp"],
                env=env,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return sorted(tool.name for tool in tools.tools)

        return asyncio.run(run())

    def test_tool_listing_no_compact(self) -> None:
        """Non-compact mode exposes all tools directly."""
        names = self._list_tools({"RHMCP_COMPACT": "0"})
        expected = {
            "capture_rhino_view",
            "create_rhino_geometry",
            "create_rhino_scene",
            "delete_rhino_objects",
            "edit_rhino_object_attributes",
            "execute_rhino_python",
            "export_rhino_document",
            "get_rhino_document_summary",
            "get_rhino_instances",
            "manage_rhino_layer",
            "run_rhino_command",
            "save_rhino_document",
            "search_rhino_docs",
            "select_rhino_objects",
            "set_rhino_view",
            "transform_rhino_objects",
        }
        self.assertTrue(expected.issubset(set(names)), sorted(expected.difference(set(names))))

    def test_tool_listing_compact(self) -> None:
        """Compact mode (default) exposes exactly the 3 meta-tools."""
        names = self._list_tools({"RHMCP_COMPACT": "1"})
        self.assertEqual(
            set(names),
            {"list_rhino_tools", "describe_rhino_tool", "call_rhino_tool"},
        )


if __name__ == "__main__":
    unittest.main()

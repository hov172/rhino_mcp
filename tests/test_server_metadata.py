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
    def test_tool_listing(self) -> None:
        async def run() -> list[str]:
            env = os.environ.copy()
            env["PYTHONPATH"] = SRC_DIR
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

        names = asyncio.run(run())
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


if __name__ == "__main__":
    unittest.main()

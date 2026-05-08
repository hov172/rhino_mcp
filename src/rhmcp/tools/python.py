"""
Tools for executing Python inside Rhino.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Execute Rhino Python", destructiveHint=True))
    def execute_rhino_python(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Execute Python code inside Rhino.

        The code runs with access to Rhino's Python environment, including
        ``rhinoscriptsyntax`` and RhinoCommon. Assign a JSON-serialisable value
        to ``result`` to return data.
        """
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Execute RhinoCommon CSharp", destructiveHint=True))
    def execute_rhino_csharp(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Execute C# code inside Rhino through ``rhinocode script``.

        This requires RhinoCode C# script support in the target Rhino version.
        Return information through stdout or by changing the active document.
        """
        return rhino.execute_script(code, ".cs", rhino_id=rhino_id)

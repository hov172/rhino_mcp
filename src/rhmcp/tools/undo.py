"""
Undo/redo tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Undo Rhino Operation", destructiveHint=True))
    def undo_rhino(count: int = 1, rhino_id: str | None = None) -> dict[str, object]:
        """
        Run Rhino undo one or more times.
        """
        results = [rhino.run_command("_Undo", rhino_id=rhino_id) for _ in range(max(1, count))]
        return {"results": results, "count": len(results), "ok": all(item["ok"] for item in results)}

    @mcp.tool(annotations=ToolAnnotations(title="Redo Rhino Operation", destructiveHint=True))
    def redo_rhino(count: int = 1, rhino_id: str | None = None) -> dict[str, object]:
        """
        Run Rhino redo one or more times.
        """
        results = [rhino.run_command("_Redo", rhino_id=rhino_id) for _ in range(max(1, count))]
        return {"results": results, "count": len(results), "ok": all(item["ok"] for item in results)}

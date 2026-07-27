"""
Tools for Grasshopper definition lifecycle: open, create, save, close, inspect.
All operations require the RhinoMCP plugin with Grasshopper loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Get Grasshopper Definition Info", readOnlyHint=True))
    def gh_get_definition_info(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return metadata about the active Grasshopper definition.

        Returns name, file path, component_count, group_count, solution_state
        (idle/computing/blank), and error_count.
        """
        return _gh("gh_get_definition_info", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Open Grasshopper Definition", readOnlyHint=True))
    def gh_open_definition(path: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Open a Grasshopper definition (.gh or .ghx) from disk.

        path: Absolute file path to the .gh or .ghx file.
        Returns name, component_count, and solution_state of the opened definition.
        """
        if not path:
            return {"ok": False, "error": "path is required"}
        return _gh("gh_open_document", {"path": path}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="New Grasshopper Definition", destructiveHint=True))
    def gh_new_definition(name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Create a new blank Grasshopper definition and make it active.

        name: Optional display name for the definition (default: 'Untitled').
        Returns definition_id (GUID string).
        """
        params: dict[str, object] = {}
        if name:
            params["name"] = name
        return _gh("gh_new_document", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Save Grasshopper Definition", destructiveHint=True))
    def gh_save_definition(path: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Save the active Grasshopper definition to disk.

        path: Optional absolute file path. If omitted, saves to the current file path.
        Returns saved_path on success.
        """
        params: dict[str, object] = {}
        if path:
            params["path"] = path
        return _gh("gh_save_document", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Close Grasshopper Definition", destructiveHint=True))
    def gh_close_definition(rhino_id: str | None = None) -> dict[str, object]:
        """
        Close the active Grasshopper definition.
        """
        return _gh("gh_close_document", {}, rhino_id=rhino_id)


def _gh(command: str, params: dict[str, object], rhino_id: str | None = None) -> dict[str, object]:
    """Plugin-only dispatch — GH has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

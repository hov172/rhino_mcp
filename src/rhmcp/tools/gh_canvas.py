"""
Tools for Grasshopper canvas manipulation: search components, add/remove/move,
wire connections, groups, rename, and comments.
All operations require the RhinoMCP plugin with Grasshopper loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Search Grasshopper Components", readOnlyHint=True))
    def gh_search_components(
        query: str,
        limit: int | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Search available Grasshopper components by name, category, or description.

        query: Search string (e.g. 'circle', 'offset', 'Math').
        limit: Maximum results to return (default..."""
        params: dict[str, object] = {"query": query}
        if limit is not None:
            params["limit"] = limit
        return _gh("gh_search_components", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="List Canvas Components", readOnlyHint=True))
    def gh_list_components(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return a lightweight summary of all objects on the active Grasshopper canvas.

        Returns list of {instance_guid, name, type, x, y}.
        Use gh_get_canvas for full detail including wires.
        """
        return _gh("gh_list_components", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Canvas State", readOnlyHint=True))
    def gh_get_canvas(
        include_wires: bool | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Return the full state of the active Grasshopper canvas.

        include_wires: If True (default), include wire connections between params.
        Returns {components[], wires[], groups[]} with..."""
        params: dict[str, object] = {}
        if include_wires is not None:
            params["include_wires"] = include_wires
        return _gh("gh_get_canvas", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Component Info", readOnlyHint=True))
    def gh_get_component_info(
        instance_guid: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Return detailed information about a single Grasshopper component.

        instance_guid: The instance GUID of the component (from gh_list_components).
        Returns name, nick_name, type,..."""
        return _gh("gh_get_component_info", {"instance_guid": instance_guid}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Component to Canvas", destructiveHint=True))
    def gh_add_component(
        component_guid: str,
        x: float,
        y: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Place a Grasshopper component on the canvas by its type GUID.

        component_guid: The component type GUID from gh_search_components.
        x, y: Canvas coordinates for placement...."""
        return _gh("gh_add_component", {"component_guid": component_guid, "x": x, "y": y}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Remove Component from Canvas", destructiveHint=True))
    def gh_remove_component(
        instance_guid: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Remove a component from the Grasshopper canvas.

        instance_guid: The instance GUID of the component to remove.
        """
        return _gh("gh_remove_component", {"instance_guid": instance_guid}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Move Component on Canvas", destructiveHint=True))
    def gh_move_component(
        instance_guid: str,
        x: float,
        y: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Move a component to new absolute canvas coordinates.

        instance_guid: The instance GUID of the component.
        x, y: New canvas position (absolute coordinates, not delta).
        """
        return _gh("gh_move_component", {"instance_guid": instance_guid, "x": x, "y": y}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Rename Component", destructiveHint=True))
    def gh_rename_component(
        instance_guid: str,
        new_name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Rename (set NickName of) a Grasshopper component.

        instance_guid: The instance GUID of the component.
        new_name: The new display name.
        """
        return _gh("gh_rename_component", {"instance_guid": instance_guid, "new_name": new_name}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Component Comment", destructiveHint=True))
    def gh_set_component_comment(
        instance_guid: str,
        comment: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set an inline description/comment on a Grasshopper component.

        instance_guid: The instance GUID of the component.
        comment: The description text to attach to the component.
        """
        return _gh("gh_set_component_comment", {"instance_guid": instance_guid, "comment": comment}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Connect Component Parameters", destructiveHint=True))
    def gh_connect_params(
        from_guid: str,
        from_output: str,
        to_guid: str,
        to_input: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Draw a wire connecting an output parameter to an input parameter.

        from_guid: Instance GUID of the source component.
        from_output: NickName of the output parameter on the source (e.g...."""
        return _gh("gh_connect_wire", {
            "from_guid": from_guid,
            "from_output": from_output,
            "to_guid": to_guid,
            "to_input": to_input,
        }, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Disconnect Component Parameters", destructiveHint=True))
    def gh_disconnect_params(
        from_guid: str,
        from_output: str,
        to_guid: str,
        to_input: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Remove a wire between an output parameter and an input parameter.

        from_guid: Instance GUID of the source component.
        from_output: NickName of the output parameter on the..."""
        return _gh("gh_disconnect_wire", {
            "from_guid": from_guid,
            "from_output": from_output,
            "to_guid": to_guid,
            "to_input": to_input,
        }, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Component Group", destructiveHint=True))
    def gh_add_group(
        instance_guids: list[str],
        label: str | None = None,
        color: list[int] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Group multiple Grasshopper components with an optional label and color.

        instance_guids: List of component instance GUIDs to include in the group.
        label: Optional display label for..."""
        params: dict[str, object] = {"instance_guids": instance_guids}
        if label is not None:
            params["label"] = label
        if color is not None:
            params["color"] = color
        return _gh("gh_add_group", params, rhino_id=rhino_id)


def _gh(command: str, params: dict[str, object], rhino_id: str | None = None) -> dict[str, object]:
    """Plugin-only dispatch — GH has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

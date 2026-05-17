"""
Tools for Grasshopper 2 canvas operations: place components, wire connections,
solve, and inspect the active GH2 definition.
All operations require the RhinoMCP plugin with Grasshopper 2 loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _gh2(command: str, params: dict, rhino_id: str | None = None) -> dict:
    """Plugin-only dispatch — GH2 has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params)
    except OSError:
        return {"ok": False, "error": "Grasshopper 2 plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Start Grasshopper 2"))
    def gh2_start(rhino_id: str | None = None) -> dict:
        """Start the Grasshopper 2 editor."""
        return _gh2("gh2_start", {})

    @mcp.tool(annotations=ToolAnnotations(title="Get GH2 Canvas Graph", readOnlyHint=True))
    def gh2_get_canvas_graph(sample_size: int = 3, rhino_id: str | None = None) -> dict:
        """
        Get a full snapshot of the active Grasshopper 2 canvas.
        Returns components, wires, and volatile data samples.
        sample_size: number of data items to return per output (default 3).
        """
        return _gh2("gh2_get_canvas_graph", {"sample_size": sample_size})

    @mcp.tool(annotations=ToolAnnotations(title="Apply GH2 Graph"))
    def gh2_apply_graph(
        components: list,
        wires: list | None = None,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Atomically place components and wire them in one call.

        components: list of {key, type_name, x, y} or {key, type="slider", min, max, value, x, y}
        wires: list of {from_key, from_output, to_key, to_input}

        Returns {ok, placed: {key: instanceGuid}, wired: N, errors: [...]}
        """
        params: dict = {"components": components}
        if wires:
            params["wires"] = wires
        return _gh2("gh2_apply_graph", params)

    @mcp.tool(annotations=ToolAnnotations(title="Place GH2 Component"))
    def gh2_place_component(
        type_name: str | None = None,
        component_guid: str | None = None,
        x: float = 0,
        y: float = 0,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Place a Grasshopper 2 component on the canvas.
        type_name: component name (e.g. "Point", "Circle"). Either type_name or component_guid required.
        component_guid: component type GUID (preferred to avoid ambiguity).
        x, y: canvas position.
        Returns instance_guid of the placed component.
        """
        params: dict = {"x": x, "y": y}
        if type_name:
            params["name"] = type_name
        if component_guid:
            params["component_guid"] = component_guid
        return _gh2("gh2_place_component", params)

    @mcp.tool(annotations=ToolAnnotations(title="Place GH2 Number Slider"))
    def gh2_place_slider(
        min: float = 0,
        max: float = 1,
        value: float = 0.5,
        decimals: int = 2,
        x: float = 0,
        y: float = 0,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Place a GH2 Number Slider on the canvas.
        Returns instance_guid of the placed slider.
        """
        return _gh2("gh2_place_slider", {"min": min, "max": max, "value": value, "decimals": decimals, "x": x, "y": y})

    @mcp.tool(annotations=ToolAnnotations(title="Connect GH2 Components"))
    def gh2_connect(
        from_instance: str,
        from_output: int | str = 0,
        to_instance: str,
        to_input: int | str = 0,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Wire a single output to an input in Grasshopper 2.
        from_instance: source component instance GUID.
        from_output: output index (int) or param name (str).
        to_instance: target component instance GUID.
        to_input: input index (int) or param name (str).
        """
        return _gh2("gh2_connect", {
            "from_instance": from_instance,
            "from_output": from_output,
            "to_instance": to_instance,
            "to_input": to_input,
        })

    @mcp.tool(annotations=ToolAnnotations(title="Connect Many GH2 Components"))
    def gh2_connect_many(wires: list, rhino_id: str | None = None) -> dict:
        """
        Wire multiple connections at once. Continues past individual failures.
        wires: list of {from_instance, from_output, to_instance, to_input}
        Returns {ok, wired: N, errors: [...]}
        """
        return _gh2("gh2_connect_many", {"wires": wires})

    @mcp.tool(annotations=ToolAnnotations(title="Describe GH2 Component", readOnlyHint=True))
    def gh2_describe_component(
        instance_guid: str | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Get metadata for a Grasshopper 2 component: category, description, input/output param names and types.
        instance_guid: instance GUID of a placed component. Either instance_guid or name required.
        """
        params: dict = {}
        if instance_guid:
            params["instance_guid"] = instance_guid
        if name:
            params["name"] = name
        return _gh2("gh2_describe_component", params)

    @mcp.tool(annotations=ToolAnnotations(title="Search GH2 Components", readOnlyHint=True))
    def gh2_search_components(
        query: str,
        category: str | None = None,
        rhino_id: str | None = None,
    ) -> dict:
        """
        Search available Grasshopper 2 components by name, nickname, or description.
        query: substring to search for.
        category: optional category filter.
        """
        params: dict = {"query": query}
        if category:
            params["category"] = category
        return _gh2("gh2_search_components", params)

    @mcp.tool(annotations=ToolAnnotations(title="Solve GH2 Graph"))
    def gh2_solve_graph(rhino_id: str | None = None) -> dict:
        """
        Expire and re-solve the active Grasshopper 2 canvas. Returns list of errors.
        """
        return _gh2("gh2_solve_graph", {})

    @mcp.tool(annotations=ToolAnnotations(title="Clear GH2 Canvas", destructiveHint=True))
    def gh2_clear_canvas(confirm: bool = False, rhino_id: str | None = None) -> dict:
        """
        Clear all objects from the active Grasshopper 2 canvas.
        confirm: must be True to proceed (safety guard against accidental clearing).
        """
        if not confirm:
            return {"ok": False, "error": "Set confirm=True to clear the canvas."}
        return _gh2("gh2_clear_canvas", {"confirm": confirm})

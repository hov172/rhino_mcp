"""
Tools for Grasshopper 2 canvas operations: place components, wire connections,
solve, and inspect the active GH2 definition.
All operations require the RhinoMCP plugin with Grasshopper 2 loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Start Grasshopper 2"))
    def gh2_start(rhino_id: str | None = None) -> dict[str, object]:
        """Start the Grasshopper 2 editor."""
        return _gh2("gh2_start", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get GH2 Canvas Graph", readOnlyHint=True))
    def gh2_get_canvas_graph(sample_size: int = 3, rhino_id: str | None = None) -> dict[str, object]:
        """
        Get a full snapshot of the active Grasshopper 2 canvas.
        Returns components, wires, and volatile data samples.
        sample_size: number of data items to return per output (default 3).
        """
        return _gh2("gh2_get_canvas_graph", {"sample_size": sample_size}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Apply GH2 Graph"))
    def gh2_apply_graph(
        components: list,
        wires: list | None = None,
        solve: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Atomically place components and wire them in one call.

        components: list of component items, each with a unique `key` used by wires:
          - {key, type_name, x, y} or {key, component_guid, x, y} places a component
            (`name` is accepted as an alias of `type_name`).
          - {key, type: "slider", min, max, value, decimals, x, y} places a Number Slider.
        wires: list of {from_key, from_output, to_key, to_input}. `from_key`/`to_key`
          reference keys placed in this call; `from_guid`/`to_guid` may be used instead
          to reference components already on the canvas. `from_output`/`to_input` accept
          a param nickname (str) or a 0-based index (int).
        solve: re-solve after wiring (default True) and return `solve`:
          {solved, error_count, warning_count, errors, diagnostics: [{instance_guid, name,
          level, message}]}. Pass False to batch several calls and solve once at the end.
        Returns {ok, placed: {key: instance_guid}, wired: N, errors: [...], solve}.
        ok is False if any placement or wire failed; successful items are kept. A canvas
        that placed cleanly but fails to solve has ok=True and solve.solved=False.
        """
        params: dict[str, object] = {"components": components, "solve": solve}
        if wires:
            params["wires"] = wires
        return _gh2("gh2_apply_graph", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Place GH2 Component"))
    def gh2_place_component(
        type_name: str | None = None,
        component_guid: str | None = None,
        x: float = 0,
        y: float = 0,
        solve: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Place a Grasshopper 2 component on the canvas. Same shape as gh_add_component.
        type_name: component name (e.g. "Point", "Circle"). Either type_name or component_guid required.
        component_guid: component type GUID (use when the name is ambiguous).
        x, y: canvas pivot position.
        solve: re-solve after placing and return a `solve` summary (see gh2_apply_graph).
        Returns {ok, instance_guid, solve}.
        """
        if not type_name and not component_guid:
            return {"ok": False, "error": "Either type_name or component_guid is required."}
        params: dict[str, object] = {"x": x, "y": y, "solve": solve}
        if type_name:
            params["name"] = type_name  # plugin uses "name" key for component type lookup
        if component_guid:
            params["component_guid"] = component_guid
        return _gh2("gh2_place_component", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Place GH2 Number Slider"))
    def gh2_place_slider(
        min: float = 0,
        max: float = 1,
        value: float = 0.5,
        decimals: int = 2,
        x: float = 0,
        y: float = 0,
        solve: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Place a GH2 Number Slider on the canvas.
        solve: re-solve after placing and return a `solve` summary (see gh2_apply_graph).
        Returns {ok, instance_guid, solve}.
        """
        return _gh2("gh2_place_slider", {
            "min": min, "max": max, "value": value, "decimals": decimals, "x": x, "y": y, "solve": solve,
        }, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Connect GH2 Components"))
    def gh2_connect(
        from_guid: str,
        from_output: int | str = 0,
        to_guid: str = "",
        to_input: int | str = 0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Wire a single output to an input in Grasshopper 2. Same shape as gh_connect_params.
        from_guid: source component instance GUID.
        from_output: output param nickname (str) or 0-based index (int).
        to_guid: target component instance GUID.
        to_input: input param nickname (str) or 0-based index (int).
        Returns {ok} or {ok: False, error}.
        """
        if not to_guid:
            return {"ok": False, "error": "to_guid is required."}
        return _gh2("gh2_connect", {
            "from_guid": from_guid,
            "from_output": from_output,
            "to_guid": to_guid,
            "to_input": to_input,
        }, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Connect Many GH2 Components"))
    def gh2_connect_many(wires: list, rhino_id: str | None = None) -> dict[str, object]:
        """
        Wire multiple connections at once. Continues past individual failures.
        wires: list of {from_guid, from_output, to_guid, to_input}
          (from_instance/to_instance accepted as legacy aliases). from_output/to_input
          accept a param nickname (str) or 0-based index (int).
        Returns {ok, connected: N, errors: [{wire, errors: [...]}]}
        """
        return _gh2("gh2_connect_many", {"wires": [_normalize_wire(w) for w in wires]}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Describe GH2 Component", readOnlyHint=True))
    def gh2_describe_component(
        instance_guid: str | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Get metadata for a Grasshopper 2 component: category, description, input/output param names and types.
        instance_guid: instance GUID of a placed component (describes that instance, including its
          current input/output nicknames). Either instance_guid or name is required.
        name: component type name to look up in the component library.
        """
        if not instance_guid and not name:
            return {"ok": False, "error": "Either instance_guid or name is required."}
        params: dict[str, object] = {}
        if instance_guid:
            params["instance_guid"] = instance_guid
        if name:
            params["name"] = name
        return _gh2("gh2_describe_component", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Search GH2 Components", readOnlyHint=True))
    def gh2_search_components(
        query: str,
        category: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Search available Grasshopper 2 components by name, nickname, or description.
        query: substring to search for.
        category: optional category filter.
        """
        params: dict[str, object] = {"query": query}
        if category:
            params["category"] = category
        return _gh2("gh2_search_components", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Solve GH2 Graph"))
    def gh2_solve_graph(rhino_id: str | None = None) -> dict[str, object]:
        """
        Expire and re-solve the active Grasshopper 2 canvas.
        Returns {ok, solved, error_count, warning_count, errors, diagnostics} where each
        diagnostic is {instance_guid, name, level: error|warning|remark, message}.
        """
        return _gh2("gh2_solve_graph", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Clear GH2 Canvas", destructiveHint=True))
    def gh2_clear_canvas(confirm: bool = False, rhino_id: str | None = None) -> dict[str, object]:
        """
        Clear all objects from the active Grasshopper 2 canvas.
        confirm: must be True to proceed (safety guard against accidental clearing).
        """
        if not confirm:
            return {"ok": False, "error": "Set confirm=True to clear the canvas."}
        return _gh2("gh2_clear_canvas", {"confirm": confirm}, rhino_id=rhino_id)


def _normalize_wire(wire: object) -> object:
    """Map from_instance/to_instance to the from_guid/to_guid keys the plugin reads."""
    if not isinstance(wire, dict):
        return wire
    out = {k: v for k, v in wire.items() if k not in ("from_instance", "to_instance")}
    if "from_instance" in wire and "from_guid" not in wire:
        out["from_guid"] = wire["from_instance"]
    if "to_instance" in wire and "to_guid" not in wire:
        out["to_guid"] = wire["to_instance"]
    return out


def _gh2(command: str, params: dict[str, object], rhino_id: str | None = None) -> dict[str, object]:
    """Plugin-only dispatch — GH2 has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper 2 plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

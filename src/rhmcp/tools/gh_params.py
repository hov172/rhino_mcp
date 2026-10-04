"""
Tools for Grasshopper parameter control: sliders, panels, number/point params,
output reading, error inspection, and script components.
All operations require the RhinoMCP plugin with Grasshopper loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Get Component Output", readOnlyHint=True))
    def gh_get_output(
        instance_guid: str,
        output_name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Retrieve computed output data from a Grasshopper component after solution.

        instance_guid: Instance GUID of the component.
        output_name: NickName of the specific output param (e.g. "Pt"). If omitted, all outputs are returned.
        Returns {ok, outputs: [{name, data_type, path_count, value_count, values}]}.
        """
        params: dict[str, object] = {"instance_guid": instance_guid}
        if output_name is not None:
            params["output_name"] = output_name
        return _gh("gh_get_output", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Solution Errors", readOnlyHint=True))
    def gh_get_errors(
        instance_guid: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Retrieve runtime error and warning messages from Grasshopper components.

        instance_guid: If provided, get messages only from that component.
                       If omitted, get messages from every component in the active document.
        Returns {ok, messages: [{component, message, level}], count} where level is "error" or "warning".
        """
        params: dict[str, object] = {}
        if instance_guid is not None:
            params["instance_guid"] = instance_guid
        return _gh("gh_get_solution_errors", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Slider Value", destructiveHint=True))
    def gh_set_slider(
        instance_guid: str,
        value: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Set the numeric value of a Grasshopper Number Slider component.

        instance_guid: Instance GUID of the slider component.
        value: New slider value (will be clamped to the slider's min/max range and rounded
               to its decimal places). Triggers a re-solve.
        """
        return _gh("gh_set_slider", {"instance_guid": instance_guid, "value": value}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Panel Text", destructiveHint=True))
    def gh_set_panel(
        instance_guid: str,
        text: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the text content of a Grasshopper Panel component.

        instance_guid: Instance GUID of the panel component.
        text: The text to display in the panel.
        """
        return _gh("gh_set_panel", {"instance_guid": instance_guid, "text": text}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Number Parameter Values", destructiveHint=True))
    def gh_set_number_param(
        instance_guid: str,
        values: list[float],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Set persistent numeric values on a Grasshopper Number parameter component.

        instance_guid: Instance GUID of the Number param.
        values: One or more numeric values as a list (e.g. [1.0, 2.5, 3.0]). Replaces any
                existing persistent data and triggers a re-solve.
        """
        return _gh("gh_set_number_param", {"instance_guid": instance_guid, "values": values}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Point Parameter Values", destructiveHint=True))
    def gh_set_point_param(
        instance_guid: str,
        points: list[list[float]],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Set persistent point values on a Grasshopper Point parameter component.

        instance_guid: Instance GUID of the Point param.
        points: List of points, each as [x, y, z] (e.g. [[0,0,0], [10,0,0]]). Two-element
                points are treated as [x, y, 0]. Replaces existing persistent data and re-solves.
        """
        # Flatten [[x,y,z],...] to [x,y,z,x,y,z,...] for C# handler
        flat: list[float] = []
        for i, pt in enumerate(points):
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                return {
                    "ok": False,
                    "error": f"points[{i}] is malformed: {pt!r}. Each point must be [x, y] or [x, y, z].",
                }
            if len(pt) == 2:
                flat.extend([pt[0], pt[1], 0.0])
            else:
                flat.extend([pt[0], pt[1], pt[2]])
        return _gh("gh_set_point_param", {"instance_guid": instance_guid, "points": flat}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Script Component", destructiveHint=True))
    def gh_add_script_component(
        language: str,
        code: str,
        inputs: list[str],
        outputs: list[str],
        x: float,
        y: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Add a script component (Python or C#) to the Grasshopper canvas. Requires Rhino 8.

        language: 'python' or 'csharp' (also accepts 'cs').
        code: Source code string to pre-load into the component. Must be non-empty; fails
              with an error if the component exposes no string-typed source input.
        inputs: Nicknames for the component's variable input params. Existing variable inputs
                are renamed/added/removed so they match this list exactly, in order.
        outputs: Nicknames for the variable output params, matched the same way. Fixed params
                 the component does not allow removing (e.g. `out`) are kept and reported.
        x, y: Canvas pivot position.
        Returns {ok, instance_guid, inputs, outputs} with the final param nicknames, or an
        explicit error if the component cannot be reshaped or the code cannot be injected.
        """
        if language not in ("python", "csharp", "cs"):
            return {"ok": False, "error": "language must be 'python' or 'csharp'"}
        return _gh("gh_add_script_component", {
            "language": language,
            "code": code,
            "inputs": inputs,
            "outputs": outputs,
            "x": x,
            "y": y,
        }, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Script Component Code", destructiveHint=True))
    def gh_set_script_code(
        instance_guid: str,
        code: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Replace the source code in an existing Grasshopper script component. Requires Rhino 8.

        instance_guid: Instance GUID of the script component.
        code: New source code string. Replaces the existing source and triggers a re-solve.
        """
        return _gh("gh_set_script_code", {"instance_guid": instance_guid, "code": code}, rhino_id=rhino_id)


def _gh(command: str, params: dict[str, object], rhino_id: str | None = None) -> dict[str, object]:
    """Plugin-only dispatch — GH has no rhinocode fallback."""
    from rhmcp.tools_helpers.security import command_execution_gate
    error = command_execution_gate(command, params)
    if error:
        return error
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

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
        """
        Retrieve computed output data from a Grasshopper component after solution.

        instance_guid: Instance GUID of the component.
        output_name: NickName of the specific output param (e.g. 'C'). If omitted, returns all outputs.
        Returns outputs[] each with name, data_type, path_count, value_count, and values[].
        Note: Run gh_run_solution first to ensure output data is current.
        """
        params: dict[str, object] = {"instance_guid": instance_guid}
        if output_name is not None:
            params["output_name"] = output_name
        return _gh("gh_get_output", params)

    @mcp.tool(annotations=ToolAnnotations(title="Get Solution Errors", readOnlyHint=True))
    def gh_get_errors(
        instance_guid: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Retrieve runtime error and warning messages from Grasshopper components.

        instance_guid: If provided, get messages only from that component.
                       If omitted, get messages from all components in the definition.
        Returns messages[] each with component name, message text, and level (error/warning).
        """
        params: dict[str, object] = {}
        if instance_guid is not None:
            params["instance_guid"] = instance_guid
        return _gh("gh_get_solution_errors", params)

    @mcp.tool(annotations=ToolAnnotations(title="Set Slider Value", destructiveHint=True))
    def gh_set_slider(
        instance_guid: str,
        value: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the numeric value of a Grasshopper Number Slider component.

        instance_guid: Instance GUID of the slider component.
        value: New slider value (will be clamped to the slider's min/max range).
        Returns clamped_value — the actual value set after clamping.
        Triggers a solution refresh automatically.
        """
        return _gh("gh_set_slider", {"instance_guid": instance_guid, "value": value})

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
        return _gh("gh_set_panel", {"instance_guid": instance_guid, "text": text})

    @mcp.tool(annotations=ToolAnnotations(title="Set Number Parameter Values", destructiveHint=True))
    def gh_set_number_param(
        instance_guid: str,
        values: list[float],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set persistent numeric values on a Grasshopper Number parameter component.

        instance_guid: Instance GUID of the Number param.
        values: One or more numeric values as a list (e.g. [1.0, 2.5, 3.14]).
        Replaces any existing persistent data on the parameter.
        """
        return _gh("gh_set_number_param", {"instance_guid": instance_guid, "values": values})

    @mcp.tool(annotations=ToolAnnotations(title="Set Point Parameter Values", destructiveHint=True))
    def gh_set_point_param(
        instance_guid: str,
        points: list[list[float]],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set persistent point values on a Grasshopper Point parameter component.

        instance_guid: Instance GUID of the Point param.
        points: List of points, each as [x, y, z] (e.g. [[0,0,0], [1,0,0]]).
                2D points [x, y] are accepted and extended to [x, y, 0].
        Replaces any existing persistent data on the parameter.
        """
        # Flatten [[x,y,z],...] to [x,y,z,x,y,z,...] for C# handler
        flat: list[float] = []
        for pt in points:
            if len(pt) == 2:
                flat.extend([pt[0], pt[1], 0.0])
            elif len(pt) >= 3:
                flat.extend([pt[0], pt[1], pt[2]])
        return _gh("gh_set_point_param", {"instance_guid": instance_guid, "points": flat})

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
        """
        Add a script component (Python or C#) to the Grasshopper canvas. Requires Rhino 8.

        language: 'python' or 'csharp' (also accepts 'cs').
        code: Source code string to pre-load into the script component.
        inputs: List of input parameter names (e.g. ['x', 'y']).
        outputs: List of output parameter names (e.g. ['result']).
        x, y: Canvas coordinates for placement.
        Returns instance_guid of the new script component.
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
        })

    @mcp.tool(annotations=ToolAnnotations(title="Set Script Component Code", destructiveHint=True))
    def gh_set_script_code(
        instance_guid: str,
        code: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Replace the source code in an existing Grasshopper script component. Requires Rhino 8.

        instance_guid: Instance GUID of the script component.
        code: New source code string.
        Triggers a solution refresh automatically.
        """
        return _gh("gh_set_script_code", {"instance_guid": instance_guid, "code": code})


def _gh(command: str, params: dict[str, object]) -> dict[str, object]:
    """Plugin-only dispatch — GH has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

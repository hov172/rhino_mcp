"""
Tools for Grasshopper solution execution: run solver, bake geometry to Rhino,
enable/disable components, and inspect solution state.
All operations require the RhinoMCP plugin with Grasshopper loaded.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Get Solution State", readOnlyHint=True))
    def gh_get_solution_state(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return the current Grasshopper solution state.

        Returns state (idle/computing/blank/post_process), duration_ms of last solution,
        and error_count across all components.
        """
        return _gh("gh_get_solution_state", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Run Grasshopper Solution", destructiveHint=True))
    def gh_run_solution(
        instance_guids: list[str] | None = None,
        wait_ms: int | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Trigger the Grasshopper solver and wait for it to complete.

        instance_guids: If provided, expire only these components before solving.
                        If omitted, expires and..."""
        params: dict[str, object] = {}
        if instance_guids is not None:
            params["instance_guids"] = instance_guids
        if wait_ms is not None:
            params["wait_ms"] = wait_ms
        return _gh("gh_run_solution", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Bake Component Output", destructiveHint=True))
    def gh_bake(
        instance_guid: str,
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Bake geometry output from a single Grasshopper component into the Rhino document.

        instance_guid: Instance GUID of the component to bake.
        layer: Optional Rhino layer name for baked..."""
        params: dict[str, object] = {"instance_guid": instance_guid}
        if layer is not None:
            params["layer"] = layer
        return _gh("gh_bake_component", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Bake All Outputs", destructiveHint=True))
    def gh_bake_all(
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Bake all geometry outputs from the entire Grasshopper definition into Rhino.

        layer: Optional Rhino layer name for all baked objects (created if it doesn't exist).
               Defaults to..."""
        params: dict[str, object] = {}
        if layer is not None:
            params["layer"] = layer
        return _gh("gh_bake_all", params, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Enable or Disable Component", destructiveHint=True))
    def gh_enable_component(
        instance_guid: str,
        enabled: bool,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Enable or disable a Grasshopper component on the canvas.

        instance_guid: Instance GUID of the component.
        enabled: True to enable, False to disable (lock) the component...."""
        return _gh("gh_enable_component", {"instance_guid": instance_guid, "enabled": enabled}, rhino_id=rhino_id)


def _gh(command: str, params: dict[str, object], rhino_id: str | None = None) -> dict[str, object]:
    """Plugin-only dispatch — GH has no rhinocode fallback."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

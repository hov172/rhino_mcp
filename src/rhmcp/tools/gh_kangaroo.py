"""Kangaroo Physics workflow tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

_GOAL_TYPES = {
    "Length": "Length",
    "Angle": "Angle",
    "Anchor": "Anchor",
    "OnMesh": "On Mesh",
    "Spring": "Spring",
    "Pressure": "Pressure",
    "Load": "Load",
    "Hinge": "Hinge",
    "Laplacian": "Laplacian Smoothing",
}


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Kangaroo"):
        return "Kangaroo Physics is not available. In Rhino 8 it is built-in; ensure Grasshopper is open with a document loaded."
    return None


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Setup Solver", destructiveHint=True))
    def gh_kangaroo_setup_solver(
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Add a Kangaroo2 Solver component to the Grasshopper canvas.
        Returns the instance_guid of the placed solver component.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Kangaroo2 Solver")
        if not guid:
            return {"success": False, "message": "Could not find Kangaroo Solver component GUID."}
        result = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": canvas_x, "y": canvas_y})
        return {"success": True, "solver": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Add Goal", destructiveHint=True))
    def gh_kangaroo_add_goal(
        goal_type: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Add a Kangaroo goal component to the canvas.
        goal_type: one of Length, Angle, Anchor, OnMesh, Spring, Pressure, Load, Hinge, Laplacian.
        Returns instance_guid of the placed component.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        search_name = _GOAL_TYPES.get(goal_type)
        if not search_name:
            return {"success": False, "message": f"Unknown goal type '{goal_type}'. Valid types: {', '.join(_GOAL_TYPES)}"}
        guid = _find_guid(search_name)
        if not guid:
            return {"success": False, "message": f"Could not find Kangaroo component for goal type '{goal_type}'."}
        result = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": canvas_x, "y": canvas_y})
        return {"success": True, "goal_type": goal_type, "component": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Connect Goal to Solver", destructiveHint=True))
    def gh_kangaroo_connect_goal(
        solver_instance_guid: str,
        goal_instance_guid: str,
    ) -> dict[str, object]:
        """
        Wire a goal component's output into the Kangaroo Solver's Goals input.
        solver_instance_guid: instance GUID of the K2 Solver component.
        goal_instance_guid: instance GUID of the goal component.
        """
        result = rhino.plugin_result("gh_connect_wire", {
            "source_instance_guid": goal_instance_guid,
            "source_param_name": "G",
            "target_instance_guid": solver_instance_guid,
            "target_param_name": "Goals",
        })
        return {"success": True, "wire": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Configure Solver", destructiveHint=True))
    def gh_kangaroo_configure_solver(
        solver_instance_guid: str,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Set Iterations and Threshold on an existing Kangaroo Solver component.
        solver_instance_guid: instance GUID of the solver.
        """
        r1 = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": solver_instance_guid,
            "param_name": "Iterations",
            "value": iterations,
        })
        r2 = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": solver_instance_guid,
            "param_name": "Threshold",
            "value": threshold,
        })
        return {"success": True, "iterations_result": r1, "threshold_result": r2}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Run Physics", destructiveHint=True))
    def gh_kangaroo_run_physics(solver_instance_guid: str) -> dict[str, object]:
        """
        Trigger a Grasshopper solution to advance the Kangaroo physics simulation.
        solver_instance_guid: instance GUID of the K2 Solver.
        """
        result = rhino.plugin_result("gh_run_solution", {})
        return {"success": True, "solution": result.get("result", {})}

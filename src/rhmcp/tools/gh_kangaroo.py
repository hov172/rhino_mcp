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

# Standalone Number parameter (GH_PersistentParam<GH_Number>) type GUID.
_NUMBER_PARAM_GUID = "3e8ca6be-fda8-4aaf-b5c0-3c54c8bb7312"


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0].get("guid") if comps else None


def _check() -> str | None:
    if not _search("Kangaroo"):
        return "Kangaroo Physics is not available. In Rhino 8 it is built-in; ensure Grasshopper is open with a document loaded."
    return None


def _err(resp: dict) -> str | None:
    """Return the error message from a plugin_result response, or None on success."""
    if not isinstance(resp, dict):
        return "Plugin returned an unexpected response."
    if resp.get("ok") is False:
        return str(resp.get("error") or resp.get("message") or "Plugin command failed.")
    inner = resp.get("result")
    if isinstance(inner, dict) and (inner.get("ok") is False or inner.get("success") is False):
        return str(inner.get("error") or inner.get("message") or "Plugin command failed.")
    return None


def _wire(src: str, sp: str, tgt: str, tp: str) -> str | None:
    """Connect a wire; return an error message on failure, None on success."""
    resp = rhino.plugin_result("gh_connect_wire", {
        "from_guid": src,
        "from_output": sp,
        "to_guid": tgt,
        "to_input": tp,
    })
    return _err(resp)


def _feed_number(target_iid: str, input_name: str, value: float, x: float, y: float) -> dict[str, object]:
    """Place a standalone Number param, set its value, and wire it into a named
    input on the target component."""
    placed = rhino.plugin_result("gh_add_component", {"component_guid": _NUMBER_PARAM_GUID, "x": x, "y": y})
    err = _err(placed)
    if err:
        return {"success": False, "error": f"Could not place Number param for input '{input_name}': {err}"}
    param_iid = placed.get("result", {}).get("instance_guid", "")
    if not param_iid:
        return {"success": False, "error": f"Number param for input '{input_name}' was placed but returned no instance_guid."}
    err = _err(rhino.plugin_result("gh_set_number_param", {"instance_guid": param_iid, "values": [float(value)]}))
    if err:
        return {"success": False, "error": f"Could not set value on Number param for input '{input_name}': {err}"}
    err = _wire(param_iid, "out", target_iid, input_name)
    if err:
        return {"success": False, "error": f"Could not wire Number param into input '{input_name}': {err}"}
    return {"success": True, "param_instance_guid": param_iid}


def _component_pos(instance_guid: str) -> tuple[float, float]:
    """Best-effort canvas position of a component (0,0 if unavailable)."""
    info = rhino.plugin_result("gh_get_component_info", {"instance_guid": instance_guid})
    inner = info.get("result", {}) if isinstance(info, dict) else {}
    if _err(info) is None and isinstance(inner, dict):
        return float(inner.get("x", 0.0)), float(inner.get("y", 0.0))
    return 0.0, 0.0


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Setup Solver", destructiveHint=True))
    def gh_kangaroo_setup_solver(
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Add a Kangaroo2 Solver component to the Grasshopper canvas and wire
        standalone Number params into its Iterations and Threshold inputs.
        Returns the instance_guid of the placed solver component.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Kangaroo2 Solver")
        if not guid:
            return {"success": False, "message": "Could not find Kangaroo Solver component GUID."}
        result = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": canvas_x, "y": canvas_y})
        perr = _err(result)
        if perr:
            return {"success": False, "error": perr}
        solver = result.get("result", {})
        solver_iid = solver.get("instance_guid", "") if isinstance(solver, dict) else ""
        if not solver_iid:
            return {"success": False, "error": "Solver was placed but no instance_guid was returned.", "solver": solver}
        fed = _feed_number(solver_iid, "Iterations", iterations, canvas_x - 200, canvas_y - 40)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "solver": solver}
        fed = _feed_number(solver_iid, "Threshold", threshold, canvas_x - 200, canvas_y + 40)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "solver": solver}
        return {"success": True, "solver": solver}

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
        perr = _err(result)
        if perr:
            return {"success": False, "error": perr}
        return {"success": True, "goal_type": goal_type, "component": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Connect Goal to Solver", destructiveHint=True))
    def gh_kangaroo_connect_goal(
        solver_instance_guid: str,
        goal_instance_guid: str,
    ) -> dict[str, object]:
        """Wire a goal component's output into the Kangaroo Solver's Goals input.
        solver_instance_guid: instance GUID of the K2 Solver component.
        goal_instance_guid: instance GUID of the goal..."""
        werr = _wire(goal_instance_guid, "G", solver_instance_guid, "Goals")
        if werr:
            return {"success": False, "error": werr}
        return {"success": True}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Configure Solver", destructiveHint=True))
    def gh_kangaroo_configure_solver(
        solver_instance_guid: str,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Set Iterations and Threshold on an existing Kangaroo Solver component by
        placing standalone Number params and wiring them into the solver's inputs.
        solver_instance_guid: instance GUID of the solver.
        """
        x, y = _component_pos(solver_instance_guid)
        r1 = _feed_number(solver_instance_guid, "Iterations", iterations, x - 200, y - 40)
        if not r1.get("success"):
            return {"success": False, "error": r1.get("error")}
        r2 = _feed_number(solver_instance_guid, "Threshold", threshold, x - 200, y + 40)
        if not r2.get("success"):
            return {"success": False, "error": r2.get("error")}
        return {"success": True, "iterations_result": r1, "threshold_result": r2}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Run Physics", destructiveHint=True))
    def gh_kangaroo_run_physics(solver_instance_guid: str) -> dict[str, object]:
        """
        Trigger a Grasshopper solution to advance the Kangaroo physics simulation.
        solver_instance_guid: instance GUID of the K2 Solver. The solver component
        is expired first, then a full-document solution runs.
        """
        result = rhino.plugin_result("gh_run_solution", {"instance_guids": [solver_instance_guid]})
        rerr = _err(result)
        if rerr:
            return {"success": False, "error": rerr}
        return {"success": True, "solution": result.get("result", {})}

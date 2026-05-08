"""Anemone looping tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Anemone"):
        return "Anemone is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Anemone'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Anemone: Setup Loop", destructiveHint=True))
    def gh_anemone_setup_loop(
        max_loops: int = 100,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Place Anemone Loop Start and Loop End components side-by-side.
        Returns instance GUIDs for both; connect your loop logic between them.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        start_guid = _find_guid("Loop Start")
        end_guid = _find_guid("Loop End")
        if not start_guid:
            return {"success": False, "message": "Could not find 'Loop Start' component."}
        if not end_guid:
            return {"success": False, "message": "Could not find 'Loop End' component."}
        start_placed = _add(start_guid, canvas_x, canvas_y)
        end_placed = _add(end_guid, canvas_x + 400, canvas_y)
        start_iid = start_placed.get("result", {}).get("instance_guid", "")
        end_iid = end_placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": start_iid, "param_name": "Max Loops", "value": max_loops})
        return {"success": True, "loop_start_instance_guid": start_iid, "loop_end_instance_guid": end_iid}

    @mcp.tool(annotations=ToolAnnotations(title="Anemone: Set Max Loops", destructiveHint=True))
    def gh_anemone_set_max_loops(
        loop_start_instance_guid: str,
        max_loops: int = 100,
    ) -> dict[str, object]:
        """Set the Max Loops count on an existing Anemone Loop Start component."""
        result = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": loop_start_instance_guid,
            "param_name": "Max Loops",
            "value": max_loops,
        })
        return {"success": True, "max_loops": max_loops, "result": result}

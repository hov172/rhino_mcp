"""Anemone looping tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# Standalone Number parameter (GH_PersistentParam<GH_Number>) type GUID.
_NUMBER_PARAM_GUID = "3e8ca6be-fda8-4aaf-b5c0-3c54c8bb7312"


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0].get("guid") if comps else None


def _check() -> str | None:
    if not _search("Anemone"):
        return "Anemone is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Anemone'."
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


def _place(guid: str, x: float, y: float) -> tuple[str, str | None]:
    """Place a component; return (instance_guid, error). error is None on success."""
    placed = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})
    err = _err(placed)
    if err:
        return "", err
    iid = placed.get("result", {}).get("instance_guid", "")
    if not iid:
        return "", "Component was placed but no instance_guid was returned."
    return iid, None


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
    param_iid, err = _place(_NUMBER_PARAM_GUID, x, y)
    if err:
        return {"success": False, "error": f"Could not place Number param for input '{input_name}': {err}"}
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
        start_iid, perr = _place(start_guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        end_iid, perr = _place(end_guid, canvas_x + 400, canvas_y)
        if perr:
            return {"success": False, "error": perr, "loop_start_instance_guid": start_iid}
        fed = _feed_number(start_iid, "Max Loops", max_loops, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {
                "success": False,
                "error": fed.get("error"),
                "loop_start_instance_guid": start_iid,
                "loop_end_instance_guid": end_iid,
            }
        return {"success": True, "loop_start_instance_guid": start_iid, "loop_end_instance_guid": end_iid}

    @mcp.tool(annotations=ToolAnnotations(title="Anemone: Set Max Loops", destructiveHint=True))
    def gh_anemone_set_max_loops(
        loop_start_instance_guid: str,
        max_loops: int = 100,
    ) -> dict[str, object]:
        """Set the Max Loops count on an existing Anemone Loop Start component by
        placing a standalone Number param and wiring it into the Max Loops input."""
        x, y = _component_pos(loop_start_instance_guid)
        result = _feed_number(loop_start_instance_guid, "Max Loops", max_loops, x - 200, y + 80)
        if not result.get("success"):
            return {"success": False, "error": result.get("error")}
        return {"success": True, "max_loops": max_loops, "result": result}

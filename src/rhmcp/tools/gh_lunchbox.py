"""LunchBox paneling and structural tools for Grasshopper."""

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
    if not _search("LunchBox"):
        return "LunchBox is not installed. Install from the Rhino Package Manager: search 'LunchBox'."
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


def _panel_tool(name: str, component_query: str, surface_instance_guid: str, u_count: int, v_count: int, canvas_x: float, canvas_y: float) -> dict:
    err = _check()
    if err:
        return {"success": False, "message": err}
    guid = _find_guid(component_query)
    if not guid:
        return {"success": False, "message": f"Could not find '{component_query}' component."}
    iid, perr = _place(guid, canvas_x, canvas_y)
    if perr:
        return {"success": False, "error": perr}
    werr = _wire(surface_instance_guid, "surface", iid, "Surface")
    if werr:
        return {"success": False, "error": werr, "instance_guid": iid}
    fed = _feed_number(iid, "U Count", u_count, canvas_x - 200, canvas_y - 40)
    if not fed.get("success"):
        return {"success": False, "error": fed.get("error"), "instance_guid": iid}
    fed = _feed_number(iid, "V Count", v_count, canvas_x - 200, canvas_y + 40)
    if not fed.get("success"):
        return {"success": False, "error": fed.get("error"), "instance_guid": iid}
    return {"success": True, "panel_type": name, "instance_guid": iid}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Quad Panels", destructiveHint=True))
    def gh_lunchbox_quad_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Quad Panels component on a surface."""
        return _panel_tool("Quad", "Quad Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Triangle Panels A", destructiveHint=True))
    def gh_lunchbox_tri_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Triangle Panels A component on a surface."""
        return _panel_tool("Triangle", "Triangle Panels A", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Diamond Panels", destructiveHint=True))
    def gh_lunchbox_diamond_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Diamond Panels component on a surface."""
        return _panel_tool("Diamond", "Diamond Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Hexagonal Panels", destructiveHint=True))
    def gh_lunchbox_hex_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Hexagonal Panels component on a surface."""
        return _panel_tool("Hexagonal", "Hexagonal Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Space Frame", destructiveHint=True))
    def gh_lunchbox_space_frame(
        surface_instance_guid: str,
        depth: float = 1.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Space Frame component and connect a surface."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Space Frame")
        if not guid:
            return {"success": False, "message": "Could not find 'Space Frame' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(surface_instance_guid, "surface", iid, "Surface")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "Depth", depth, canvas_x - 200, canvas_y + 40)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

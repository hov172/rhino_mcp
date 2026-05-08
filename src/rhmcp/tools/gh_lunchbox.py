"""LunchBox paneling and structural tools for Grasshopper."""

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
    if not _search("LunchBox"):
        return "LunchBox is not installed. Install from the Rhino Package Manager: search 'LunchBox'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def _panel_tool(name: str, component_query: str, surface_instance_guid: str, u_count: int, v_count: int, canvas_x: float, canvas_y: float) -> dict:
    err = _check()
    if err:
        return {"success": False, "message": err}
    guid = _find_guid(component_query)
    if not guid:
        return {"success": False, "message": f"Could not find '{component_query}' component."}
    placed = _add(guid, canvas_x, canvas_y)
    iid = placed.get("result", {}).get("instance_guid", "")
    _wire(surface_instance_guid, "surface", iid, "Surface")
    rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "U Count", "value": u_count})
    rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "V Count", "value": v_count})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(surface_instance_guid, "surface", iid, "Surface")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Depth", "value": depth})
        return {"success": True, "instance_guid": iid}

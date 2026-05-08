"""Pufferfish geometry morphing tools for Grasshopper."""

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
    if not _search("Pufferfish"):
        return "Pufferfish is not installed. Install from the Rhino Package Manager: search 'Pufferfish'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src_iid: str, src_param: str, tgt_iid: str, tgt_param: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src_iid, "source_param_name": src_param, "target_instance_guid": tgt_iid, "target_param_name": tgt_param})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Tween Curves", destructiveHint=True))
    def gh_pufferfish_tween_curves(
        curve1_instance_guid: str,
        curve2_instance_guid: str,
        count: int = 5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Pufferfish Tween Curves component and connect two curve sources."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Tween Curves")
        if not guid:
            return {"success": False, "message": "Could not find 'Tween Curves' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(curve1_instance_guid, "curve", iid, "Curve A")
        _wire(curve2_instance_guid, "curve", iid, "Curve B")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Number of Tweens", "value": count})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Morph Surface", destructiveHint=True))
    def gh_pufferfish_morph_surface(
        geometry_instance_guid: str,
        source_surface_instance_guid: str,
        target_surface_instance_guid: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Surface Morph component and connect geometry, source, and target surfaces."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Surface Morph")
        if not guid:
            return {"success": False, "message": "Could not find 'Surface Morph' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(source_surface_instance_guid, "surface", iid, "Source")
        _wire(target_surface_instance_guid, "surface", iid, "Target")
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Blend Surfaces", destructiveHint=True))
    def gh_pufferfish_blend_surfaces(
        surface1_instance_guid: str,
        surface2_instance_guid: str,
        count: int = 5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Tween Surfaces component and connect two surface sources."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Tween Surfaces")
        if not guid:
            return {"success": False, "message": "Could not find 'Tween Surfaces' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(surface1_instance_guid, "surface", iid, "Surface A")
        _wire(surface2_instance_guid, "surface", iid, "Surface B")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Number of Tweens", "value": count})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Twist Object", destructiveHint=True))
    def gh_pufferfish_twist(
        geometry_instance_guid: str,
        axis_instance_guid: str,
        angle_degrees: float = 45.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Twist Object component and connect geometry and axis line."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Twist Object")
        if not guid:
            return {"success": False, "message": "Could not find 'Twist Object' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(axis_instance_guid, "line", iid, "Axis")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Angle", "value": angle_degrees})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Bend Object", destructiveHint=True))
    def gh_pufferfish_bend(
        geometry_instance_guid: str,
        axis_instance_guid: str,
        angle_degrees: float = 45.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Bend Object component and connect geometry and axis line."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Bend Object")
        if not guid:
            return {"success": False, "message": "Could not find 'Bend Object' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(axis_instance_guid, "line", iid, "Axis")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Angle", "value": angle_degrees})
        return {"success": True, "instance_guid": iid}

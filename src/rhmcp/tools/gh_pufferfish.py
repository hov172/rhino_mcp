"""Pufferfish geometry morphing tools for Grasshopper."""

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
    if not _search("Pufferfish"):
        return "Pufferfish is not installed. Install from the Rhino Package Manager: search 'Pufferfish'."
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


def _wire(src_iid: str, src_param: str, tgt_iid: str, tgt_param: str) -> str | None:
    """Connect a wire; return an error message on failure, None on success."""
    resp = rhino.plugin_result("gh_connect_wire", {
        "from_guid": src_iid,
        "from_output": src_param,
        "to_guid": tgt_iid,
        "to_input": tgt_param,
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(curve1_instance_guid, "curve", iid, "Curve A")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(curve2_instance_guid, "curve", iid, "Curve B")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "Number of Tweens", count, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(source_surface_instance_guid, "surface", iid, "Source")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(target_surface_instance_guid, "surface", iid, "Target")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(surface1_instance_guid, "surface", iid, "Surface A")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(surface2_instance_guid, "surface", iid, "Surface B")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "Number of Tweens", count, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(axis_instance_guid, "line", iid, "Axis")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "Angle", angle_degrees, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(axis_instance_guid, "line", iid, "Axis")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "Angle", angle_degrees, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

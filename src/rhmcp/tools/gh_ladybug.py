"""Ladybug Tools and Honeybee workflow helpers for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# Standalone Number parameter (GH_PersistentParam<GH_Number>) type GUID.
_NUMBER_PARAM_GUID = "3e8ca6be-fda8-4aaf-b5c0-3c54c8bb7312"
# Panel (GH_Panel) type GUID.
_PANEL_GUID = "59e0b89a-e487-49f8-bab8-b5bab16be14c"


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0].get("guid") if comps else None


def _check() -> str | None:
    if not _search("Ladybug"):
        return "Ladybug Tools is not installed. Install from the Rhino Package Manager: search 'Ladybug'."
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


def _feed_text(target_iid: str, input_name: str, text: str, x: float, y: float) -> dict[str, object]:
    """Place a Panel, set its text, and wire it into a named input on the target component."""
    panel_iid, err = _place(_PANEL_GUID, x, y)
    if err:
        return {"success": False, "error": f"Could not place Panel for input '{input_name}': {err}"}
    err = _err(rhino.plugin_result("gh_set_panel", {"instance_guid": panel_iid, "text": text}))
    if err:
        return {"success": False, "error": f"Could not set text on Panel for input '{input_name}': {err}"}
    err = _wire(panel_iid, "out", target_iid, input_name)
    if err:
        return {"success": False, "error": f"Could not wire Panel into input '{input_name}': {err}"}
    return {"success": True, "param_instance_guid": panel_iid}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Load Weather File", destructiveHint=True))
    def gh_ladybug_load_weather(
        epw_file_path: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Import EPW component and feed the file path via a wired Panel. Returns instance_guid."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Import EPW")
        if not guid:
            return {"success": False, "message": "Could not find 'Import EPW' component."}
        instance_guid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        fed = _feed_text(instance_guid, "_epw_file", epw_file_path, canvas_x - 200, canvas_y)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": instance_guid}
        return {"success": True, "instance_guid": instance_guid, "epw_file_path": epw_file_path}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Sun Path", destructiveHint=True))
    def gh_ladybug_sun_path(
        location_instance_guid: str,
        north_angle: float = 0.0,
        canvas_x: float = 200.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Sun Path component and connect a location output to it."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Sun Path")
        if not guid:
            return {"success": False, "message": "Could not find 'Sun Path' component."}
        instance_guid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(location_instance_guid, "location", instance_guid, "_location")
        if werr:
            return {"success": False, "error": werr, "instance_guid": instance_guid}
        return {"success": True, "instance_guid": instance_guid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Radiation Analysis", destructiveHint=True))
    def gh_ladybug_radiation_analysis(
        geometry_instance_guid: str,
        location_instance_guid: str,
        canvas_x: float = 200.0,
        canvas_y: float = 200.0,
    ) -> dict[str, object]:
        """Place a Radiation Analysis component and connect geometry and location."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Radiation Analysis")
        if not guid:
            return {"success": False, "message": "Could not find 'Radiation Analysis' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(geometry_instance_guid, "geometry", iid, "_geometry")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(location_instance_guid, "location", iid, "_location")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Wind Rose", destructiveHint=True))
    def gh_ladybug_wind_rose(
        location_instance_guid: str,
        canvas_x: float = 200.0,
        canvas_y: float = 400.0,
    ) -> dict[str, object]:
        """Place a Wind Rose component connected to a location."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Wind Rose")
        if not guid:
            return {"success": False, "message": "Could not find 'Wind Rose' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(location_instance_guid, "location", iid, "_location")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: UTCI Comfort", destructiveHint=True))
    def gh_ladybug_utci_comfort(
        location_instance_guid: str,
        geometry_instance_guid: str,
        canvas_x: float = 400.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a UTCI Comfort component for outdoor thermal comfort analysis."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("UTCI Comfort")
        if not guid:
            return {"success": False, "message": "Could not find 'UTCI Comfort' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(location_instance_guid, "location", iid, "_location")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(geometry_instance_guid, "geometry", iid, "_mesh")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Create Room", destructiveHint=True))
    def gh_honeybee_create_room(
        geometry_component_id: str,
        room_name: str = "HBRoom",
        canvas_x: float = 200.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Honeybee 'HB Room from Solid' component and connect geometry."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Room from Solid")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Room from Solid'. Ensure Honeybee is installed."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(geometry_component_id, "geometry", iid, "_geo")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_text(iid, "_name", room_name, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Add Windows by Ratio", destructiveHint=True))
    def gh_honeybee_add_window(
        room_instance_guid: str,
        ratio: float = 0.4,
        canvas_x: float = 400.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place HB Add Subface (by ratio) and connect a room."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Add Subface")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Add Subface' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(room_instance_guid, "room", iid, "_rooms")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_number(iid, "_ratio", ratio, canvas_x - 200, canvas_y + 80)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Run Energy Simulation", destructiveHint=True))
    def gh_honeybee_run_energy(
        model_instance_guid: str,
        canvas_x: float = 600.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place HB Model to IDF and connect a model for energy simulation."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Model to IDF")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Model to IDF' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(model_instance_guid, "model", iid, "_model")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

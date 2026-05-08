"""Ladybug Tools and Honeybee workflow helpers for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Ladybug"):
        return "Ladybug Tools is not installed. Install from the Rhino Package Manager: search 'Ladybug'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Load Weather File", destructiveHint=True))
    def gh_ladybug_load_weather(
        epw_file_path: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Import EPW component and set the file path. Returns instance_guid."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Import EPW")
        if not guid:
            return {"success": False, "message": "Could not find 'Import EPW' component."}
        placed = _add(guid, canvas_x, canvas_y)
        instance_guid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_panel", {"instance_guid": instance_guid, "param_name": "_epw_file", "value": epw_file_path})
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
        placed = _add(guid, canvas_x, canvas_y)
        instance_guid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {
            "source_instance_guid": location_instance_guid,
            "source_param_name": "location",
            "target_instance_guid": instance_guid,
            "target_param_name": "_location",
        })
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_instance_guid, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_geometry"})
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_instance_guid, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_mesh"})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_component_id, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_geo"})
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "_name", "value": room_name})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": room_instance_guid, "source_param_name": "room", "target_instance_guid": iid, "target_param_name": "_rooms"})
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "_ratio", "value": ratio})
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
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": model_instance_guid, "source_param_name": "model", "target_instance_guid": iid, "target_param_name": "_model"})
        return {"success": True, "instance_guid": iid}

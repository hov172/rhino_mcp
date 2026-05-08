"""Human and Elefront Grasshopper attribute management tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check_elefront() -> str | None:
    if not _search("Elefront"):
        return "Elefront is not installed. Install from the Rhino Package Manager: search 'Elefront'."
    return None


def _check_human() -> str | None:
    if not _search("Human"):
        return "Human is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Human'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Bake with Attributes", destructiveHint=True))
    def gh_elefront_bake_attributes(
        component_instance_guid: str,
        layer: str = "Default",
        name: str = "",
        user_text: dict[str, str] | None = None,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Place an Elefront Bake Objects component, connect geometry, and configure layer, name, and user text.
        user_text: dict of key→value pairs to set as object user text.
        """
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Bake Objects")
        if not guid:
            return {"success": False, "message": "Could not find Elefront 'Bake Objects' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "G")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "L", "value": layer})
        if name:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "N", "value": name})
        if user_text:
            for k, v in user_text.items():
                rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": k})
                rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "V", "value": v})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Reference Objects by Filter", destructiveHint=True))
    def gh_elefront_reference_by_filter(
        layer: str | None = None,
        name_filter: str | None = None,
        user_text_key: str | None = None,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Elefront Reference by Filter component and configure filter criteria."""
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Reference by Filter")
        if not guid:
            return {"success": False, "message": "Could not find 'Reference by Filter' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        if layer:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "L", "value": layer})
        if name_filter:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "N", "value": name_filter})
        if user_text_key:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": user_text_key})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Set User Text", destructiveHint=True))
    def gh_elefront_set_user_text(
        component_instance_guid: str,
        key: str,
        value: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Elefront Set User Text component and connect geometry with a key-value pair."""
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Set User Text")
        if not guid:
            return {"success": False, "message": "Could not find 'Set User Text' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "G")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": key})
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "V", "value": value})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Human: Get Object Attributes", destructiveHint=True))
    def gh_human_get_attributes(
        rhino_object_id: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Human Get Object Attributes component and set the object ID."""
        err = _check_human()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Get Object Attributes")
        if not guid:
            return {"success": False, "message": "Could not find Human 'Get Object Attributes' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "Object", "value": rhino_object_id})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Human: Set User Text on Objects", destructiveHint=True))
    def gh_human_set_user_text(
        component_instance_guid: str,
        key: str,
        value_component_instance_guid: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Human Set User Text component, connect objects and wire the value from another component."""
        err = _check_human()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Set User Text")
        if not guid:
            return {"success": False, "message": "Could not find Human 'Set User Text' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "Objects")
        _wire(value_component_instance_guid, "value", iid, "Value")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "Key", "value": key})
        return {"success": True, "instance_guid": iid}

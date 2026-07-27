"""Human and Elefront Grasshopper attribute management tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# Panel (GH_Panel) type GUID.
_PANEL_GUID = "59e0b89a-e487-49f8-bab8-b5bab16be14c"


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0].get("guid") if comps else None


def _check_elefront() -> str | None:
    if not _search("Elefront"):
        return "Elefront is not installed. Install from the Rhino Package Manager: search 'Elefront'."
    return None


def _check_human() -> str | None:
    if not _search("Human"):
        return "Human is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Human'."
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
        Place an Elefront Bake Objects component, connect geometry, and configure
        layer, name, and user text via wired Panels. Each user_text pair adds one
        Panel wired into K and one into V (wires merge, so keys and values stay in
        matching order).
        user_text: dict of key→value pairs to set as object user text.
        """
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Bake Objects")
        if not guid:
            return {"success": False, "message": "Could not find Elefront 'Bake Objects' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(component_instance_guid, "geometry", iid, "G")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_text(iid, "L", layer, canvas_x - 200, canvas_y)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        if name:
            fed = _feed_text(iid, "N", name, canvas_x - 200, canvas_y + 60)
            if not fed.get("success"):
                return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        if user_text:
            offset = 0.0
            for k, v in user_text.items():
                fed = _feed_text(iid, "K", k, canvas_x - 200, canvas_y + 120 + offset)
                if not fed.get("success"):
                    return {"success": False, "error": fed.get("error"), "instance_guid": iid}
                fed = _feed_text(iid, "V", v, canvas_x - 100, canvas_y + 120 + offset)
                if not fed.get("success"):
                    return {"success": False, "error": fed.get("error"), "instance_guid": iid}
                offset += 60.0
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Reference Objects by Filter", destructiveHint=True))
    def gh_elefront_reference_by_filter(
        layer: str | None = None,
        name_filter: str | None = None,
        user_text_key: str | None = None,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Elefront Reference by Filter component and configure filter criteria via wired Panels."""
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Reference by Filter")
        if not guid:
            return {"success": False, "message": "Could not find 'Reference by Filter' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        if layer:
            fed = _feed_text(iid, "L", layer, canvas_x - 200, canvas_y)
            if not fed.get("success"):
                return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        if name_filter:
            fed = _feed_text(iid, "N", name_filter, canvas_x - 200, canvas_y + 60)
            if not fed.get("success"):
                return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        if user_text_key:
            fed = _feed_text(iid, "K", user_text_key, canvas_x - 200, canvas_y + 120)
            if not fed.get("success"):
                return {"success": False, "error": fed.get("error"), "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(component_instance_guid, "geometry", iid, "G")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_text(iid, "K", key, canvas_x - 200, canvas_y + 60)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        fed = _feed_text(iid, "V", value, canvas_x - 200, canvas_y + 120)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Human: Get Object Attributes", destructiveHint=True))
    def gh_human_get_attributes(
        rhino_object_id: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Human Get Object Attributes component and feed the object ID via a wired Panel."""
        err = _check_human()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Get Object Attributes")
        if not guid:
            return {"success": False, "message": "Could not find Human 'Get Object Attributes' component."}
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        fed = _feed_text(iid, "Object", rhino_object_id, canvas_x - 200, canvas_y)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
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
        iid, perr = _place(guid, canvas_x, canvas_y)
        if perr:
            return {"success": False, "error": perr}
        werr = _wire(component_instance_guid, "geometry", iid, "Objects")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        werr = _wire(value_component_instance_guid, "value", iid, "Value")
        if werr:
            return {"success": False, "error": werr, "instance_guid": iid}
        fed = _feed_text(iid, "Key", key, canvas_x - 200, canvas_y + 60)
        if not fed.get("success"):
            return {"success": False, "error": fed.get("error"), "instance_guid": iid}
        return {"success": True, "instance_guid": iid}

"""Weaverbird mesh subdivision tools for Grasshopper."""

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
    if not _search("Weaverbird"):
        return "Weaverbird is not installed. Install from food4rhino.com or the Rhino Package Manager."
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


def _mesh_tool(component_query: str, missing_msg: str, mesh_instance_guid: str, number_input: str, number_value: float, canvas_x: float, canvas_y: float) -> dict[str, object]:
    """Shared flow: place a Weaverbird component, wire the mesh, feed one number input."""
    err = _check()
    if err:
        return {"success": False, "message": err}
    guid = _find_guid(component_query)
    if not guid:
        return {"success": False, "message": missing_msg}
    iid, perr = _place(guid, canvas_x, canvas_y)
    if perr:
        return {"success": False, "error": perr}
    werr = _wire(mesh_instance_guid, "mesh", iid, "Mesh")
    if werr:
        return {"success": False, "error": werr, "instance_guid": iid}
    fed = _feed_number(iid, number_input, number_value, canvas_x - 200, canvas_y + 80)
    if not fed.get("success"):
        return {"success": False, "error": fed.get("error"), "instance_guid": iid}
    return {"success": True, "instance_guid": iid}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Catmull-Clark Subdivision", destructiveHint=True))
    def gh_wb_catmull_clark(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Catmull-Clark Subdivision component and connect a mesh."""
        return _mesh_tool("Catmull-Clark", "Could not find 'Catmull-Clark Subdivision' component.", mesh_instance_guid, "Iterations", iterations, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Loop Subdivision", destructiveHint=True))
    def gh_wb_loop(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Loop Subdivision component and connect a mesh."""
        return _mesh_tool("Loop Subdivision", "Could not find 'Loop Subdivision' component.", mesh_instance_guid, "Iterations", iterations, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Butterfly Subdivision", destructiveHint=True))
    def gh_wb_butterfly(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Butterfly Subdivision component and connect a mesh."""
        return _mesh_tool("Butterfly Subdivision", "Could not find 'Butterfly Subdivision' component.", mesh_instance_guid, "Iterations", iterations, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Mesh Frame", destructiveHint=True))
    def gh_wb_frame(
        mesh_instance_guid: str,
        offset: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Frame component and connect a mesh."""
        return _mesh_tool("Mesh Frame", "Could not find 'Mesh Frame' component.", mesh_instance_guid, "Offset", offset, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Thicken Mesh", destructiveHint=True))
    def gh_wb_thicken(
        mesh_instance_guid: str,
        thickness: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Thickening component and connect a mesh."""
        return _mesh_tool("Mesh Thickening", "Could not find 'Mesh Thickening' component.", mesh_instance_guid, "Distance", thickness, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Extrude Face", destructiveHint=True))
    def gh_wb_extrude_face(
        mesh_instance_guid: str,
        distance: float = 0.5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Extrude Face component and connect a mesh."""
        return _mesh_tool("Extrude Face", "Could not find 'Extrude Face' component.", mesh_instance_guid, "Distance", distance, canvas_x, canvas_y)

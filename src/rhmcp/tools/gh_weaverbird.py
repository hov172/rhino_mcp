"""Weaverbird mesh subdivision tools for Grasshopper."""

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
    if not _search("Weaverbird"):
        return "Weaverbird is not installed. Install from food4rhino.com or the Rhino Package Manager."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Catmull-Clark Subdivision", destructiveHint=True))
    def gh_wb_catmull_clark(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Catmull-Clark Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Catmull-Clark")
        if not guid:
            return {"success": False, "message": "Could not find 'Catmull-Clark Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Loop Subdivision", destructiveHint=True))
    def gh_wb_loop(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Loop Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Loop Subdivision")
        if not guid:
            return {"success": False, "message": "Could not find 'Loop Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Butterfly Subdivision", destructiveHint=True))
    def gh_wb_butterfly(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Butterfly Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Butterfly Subdivision")
        if not guid:
            return {"success": False, "message": "Could not find 'Butterfly Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Mesh Frame", destructiveHint=True))
    def gh_wb_frame(
        mesh_instance_guid: str,
        offset: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Frame component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Mesh Frame")
        if not guid:
            return {"success": False, "message": "Could not find 'Mesh Frame' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Offset", "value": offset})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Thicken Mesh", destructiveHint=True))
    def gh_wb_thicken(
        mesh_instance_guid: str,
        thickness: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Thickening component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Mesh Thickening")
        if not guid:
            return {"success": False, "message": "Could not find 'Mesh Thickening' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Distance", "value": thickness})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Extrude Face", destructiveHint=True))
    def gh_wb_extrude_face(
        mesh_instance_guid: str,
        distance: float = 0.5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Extrude Face component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Extrude Face")
        if not guid:
            return {"success": False, "message": "Could not find 'Extrude Face' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Distance", "value": distance})
        return {"success": True, "instance_guid": iid}

"""VisualARQ architectural BIM tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("VisualARQ" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "VisualARQ is not installed or not loaded. Install from visualarq.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Wall", destructiveHint=True))
    def varq_create_wall(
        start_pt: list[float],
        end_pt: list[float],
        height: float = 3.0,
        style_name: str = "Basic Wall",
        layer: str | None = None,
    ) -> dict[str, object]:
        """
        Create a VisualARQ wall between two points.
        start_pt / end_pt: [x, y, z]. height in document units.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        sx, sy, sz = start_pt[:3]
        ex, ey, ez = end_pt[:3]
        code = f"""
import visualarq.py as va
import Rhino.Geometry as rg
start = rg.Point3d({sx}, {sy}, {sz})
end = rg.Point3d({ex}, {ey}, {ez})
style_id = va.vaWallStyles.FindByName({style_name!r})
wall_id = va.vaWall.Add(start, end, {height}, style_id)
result = {{"wall_id": str(wall_id)}}
"""
        res = _py(code)
        return {"success": True, "start_pt": start_pt, "end_pt": end_pt, "height": height, "style": style_name, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Add Opening (Window/Door)", destructiveHint=True))
    def varq_add_opening(
        wall_id: str,
        opening_type: str = "window",
        position_along_wall: float = 0.5,
        width: float = 1.0,
        height: float = 2.0,
        style_name: str | None = None,
    ) -> dict[str, object]:
        """
        Add a window or door to a VisualARQ wall.
        opening_type: window | door.
        position_along_wall: 0.0-1.0 (fraction along wall length).
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        cmd = "vaWindow" if opening_type.lower() == "window" else "vaDoor"
        result = _run(f"_{cmd}")
        return {"success": True, "wall_id": wall_id, "opening_type": opening_type, "width": width, "height": height, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Slab", destructiveHint=True))
    def varq_create_slab(
        boundary_curve_ids: list[str],
        thickness: float = 0.3,
        style_name: str = "Basic Slab",
        layer: str | None = None,
    ) -> dict[str, object]:
        """Create a VisualARQ floor slab from closed boundary curves."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaSlab")
        return {"success": True, "boundary_count": len(boundary_curve_ids), "thickness": thickness, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Column", destructiveHint=True))
    def varq_create_column(
        position: list[float],
        height: float = 3.0,
        style_name: str = "Basic Column",
        layer: str | None = None,
    ) -> dict[str, object]:
        """Create a VisualARQ structural column at a point."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaColumn")
        return {"success": True, "position": position, "height": height, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Stair", destructiveHint=True))
    def varq_create_stair(
        start_pt: list[float],
        direction: list[float],
        width: float = 1.2,
        rise: float = 0.175,
        run: float = 0.28,
        story_count: int = 1,
        style_name: str = "Basic Stair",
    ) -> dict[str, object]:
        """Create a VisualARQ stair. direction: [x,y,z] unit vector for stair direction."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaStair")
        return {"success": True, "start_pt": start_pt, "width": width, "rise": rise, "run": run, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Railing", destructiveHint=True))
    def varq_create_railing(
        path_curve_id: str,
        height: float = 1.0,
        style_name: str = "Basic Railing",
    ) -> dict[str, object]:
        """Create a VisualARQ railing along a curve path."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaRailing")
        return {"success": True, "path_curve_id": path_curve_id, "height": height, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Set Level", destructiveHint=True))
    def varq_set_level(name: str, elevation: float = 0.0) -> dict[str, object]:
        """Create or update a VisualARQ building level."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaLevels")
        return {"success": True, "name": name, "elevation": elevation, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Export IFC", destructiveHint=True))
    def varq_export_ifc(
        output_path: str,
        ifc_version: str = "IFC4",
    ) -> dict[str, object]:
        """
        Export the model to IFC format.
        ifc_version: IFC2x3 | IFC4.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"_vaExportIFC {output_path!r}")
        return {"success": True, "output_path": output_path, "ifc_version": ifc_version, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Get Object Properties", readOnlyHint=True))
    def varq_get_object_properties(object_id: str) -> dict[str, object]:
        """Get VisualARQ type, style, level, and IFC properties for an object."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import visualarq.py as va
import System
obj_id = System.Guid({object_id!r})
va_obj = va.vaObject.GetObject(obj_id)
if va_obj:
    result = {{"type": str(va_obj.ObjectType), "style": str(va_obj.StyleId), "level": str(va_obj.LevelId)}}
else:
    result = {{"error": "Not a VisualARQ object"}}
"""
        res = _py(code)
        return {"success": True, "object_id": object_id, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: List Styles", readOnlyHint=True))
    def varq_list_styles(object_type: str = "wall") -> dict[str, object]:
        """
        List available VisualARQ styles for an object type.
        object_type: wall | door | window | slab | column | stair | railing.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        style_map = {
            "wall": "vaWallStyles",
            "door": "vaDoorStyles",
            "window": "vaWindowStyles",
            "slab": "vaSlabStyles",
            "column": "vaColumnStyles",
            "stair": "vaStairStyles",
            "railing": "vaRailingStyles",
        }
        style_cls = style_map.get(object_type.lower())
        if not style_cls:
            return {"success": False, "message": f"Unknown object_type '{object_type}'. Valid: {', '.join(style_map)}"}
        code = f"""
import visualarq.py as va
styles = [{style_cls}]
names = [s.Name for s in styles] if hasattr(styles, '__iter__') else []
result = {{"object_type": {object_type!r}, "styles": names}}
"""
        res = _py(code)
        return {"success": True, "object_type": object_type, "result": res}

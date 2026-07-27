"""VisualARQ architectural BIM tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend
from rhmcp.tools_helpers import plugin_client
from rhmcp.tools_helpers.security import sanitise_rhino_path


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("VisualARQ" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "VisualARQ is not installed or not loaded. Install from visualarq.com."
    return None


def _run(command: str) -> dict:
    return backend.run_command(command)


def _py(code: str) -> dict:
    return backend.execute_python(code)


def _outcome(res: dict) -> tuple[bool, str | None]:
    """Extract (ok, error) from a backend response so failures propagate."""
    ok = bool(res.get("ok"))
    if ok:
        return True, None
    return False, str(res.get("error") or res.get("message") or "Rhino command failed")


# Guarded probe for a VisualARQ Python scripting module. VisualARQ does not
# document a Python API, so we only ever *look* for one (no blind imports) and
# fail honestly when none is found. Works in both IronPython 2 (imp) and
# CPython 3 (importlib.util.find_spec).
_VA_PROBE = r'''
def _find_va_module():
    names = ("VisualARQ", "visualarq")
    try:
        from importlib.util import find_spec
    except ImportError:
        find_spec = None
    for _name in names:
        if find_spec is not None:
            try:
                if find_spec(_name) is not None:
                    return _name
            except (ImportError, ValueError):
                continue
        else:
            try:
                import imp
                imp.find_module(_name)
                return _name
            except ImportError:
                continue
    return None

_VA_UNAVAILABLE = (
    "VisualARQ does not expose a documented Python scripting module in this "
    "Rhino Python environment (checked: VisualARQ, visualarq). Use VisualARQ's "
    "interactive commands or its Grasshopper components instead."
)
'''


def _va_script_result(operation: str) -> dict:
    """Run the probe inside Rhino and return an honest ok:False response."""
    code = _VA_PROBE + f"""
_mod = _find_va_module()
if _mod is None:
    result = {{"ok": False, "error": _VA_UNAVAILABLE}}
else:
    result = {{"ok": False, "error": (
        "Python module '%s' is present, but rhino_mcp has no verified "
        "VisualARQ scripting API for {operation}; refusing to guess at an "
        "undocumented API." % _mod)}}
"""
    return _py(code)


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
        res = _va_script_result("creating walls")
        ok, error = _outcome(res)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"start_pt": start_pt, "end_pt": end_pt, "height": height, "style": style_name},
            "result": res,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "opening_type": opening_type,
            "note": (
                f"_{cmd} is an interactive VisualARQ command that expects mouse "
                "input; wall_id, position_along_wall, width, height, and "
                "style_name could not be applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_vaSlab is an interactive VisualARQ command that expects mouse "
                "input; boundary_curve_ids, thickness, and style_name could not "
                "be applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_vaColumn is an interactive VisualARQ command that expects mouse "
                "input; position, height, and style_name could not be applied "
                "programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_vaStair is an interactive VisualARQ command that expects mouse "
                "input; start_pt, direction, width, rise, run, story_count, and "
                "style_name could not be applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_vaRailing is an interactive VisualARQ command that expects mouse "
                "input; path_curve_id, height, and style_name could not be "
                "applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Set Level", destructiveHint=True))
    def varq_set_level(name: str, elevation: float = 0.0) -> dict[str, object]:
        """Create or update a VisualARQ building level."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaLevels")
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_vaLevels opens the interactive Levels dialog; name and elevation "
                "could not be applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        safe_path = sanitise_rhino_path(output_path)
        result = _run('_vaExportIFC "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "output_path": output_path,
            "ifc_version": ifc_version,
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Get Object Properties", readOnlyHint=True))
    def varq_get_object_properties(object_id: str) -> dict[str, object]:
        """Get VisualARQ type, style, level, and IFC properties for an object."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        res = _va_script_result("reading object properties")
        ok, error = _outcome(res)
        out: dict[str, object] = {"success": ok, "object_id": object_id, "result": res}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: List Styles", readOnlyHint=True))
    def varq_list_styles(object_type: str = "wall") -> dict[str, object]:
        """
        List available VisualARQ styles for an object type.
        object_type: wall | door | window | slab | column | stair | railing.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        valid = ("wall", "door", "window", "slab", "column", "stair", "railing")
        if object_type.lower() not in valid:
            return {"success": False, "message": f"Unknown object_type '{object_type}'. Valid: {', '.join(valid)}"}
        res = _va_script_result(f"listing {object_type.lower()} styles")
        ok, error = _outcome(res)
        out: dict[str, object] = {"success": ok, "object_type": object_type, "result": res}
        if error:
            out["error"] = error
        return out

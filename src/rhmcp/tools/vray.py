"""V-Ray for Rhino tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend
from rhmcp.tools_helpers import plugin_client
from rhmcp.tools_helpers.security import sanitise_rhino_path


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("V-Ray" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "V-Ray for Rhino is not installed or not loaded. Install from chaos.com."
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


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Start IPR", destructiveHint=True))
    def vray_start_ipr() -> dict[str, object]:
        """Start V-Ray Interactive Production Rendering in the active viewport."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPR")
        ok, error = _outcome(result)
        out: dict[str, object] = {"success": ok, "result": result}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Stop IPR", destructiveHint=True))
    def vray_stop_ipr() -> dict[str, object]:
        """Stop V-Ray Interactive Production Rendering."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPRStop")
        ok, error = _outcome(result)
        out: dict[str, object] = {"success": ok, "result": result}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Render", destructiveHint=True))
    def vray_render(
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        quality_preset: str = "medium",
    ) -> dict[str, object]:
        """
        Render with V-Ray and save to output_path.
        quality_preset: low | medium | high | ultra.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        code = f"""
import os
import rhinoscriptsyntax as rs
import Rhino
rs.RenderResolution(({width}, {height}))
rendered = Rhino.RhinoApp.RunScript("_-Render", False)
save_cmd = '_-SaveRenderWindowAs "' + {safe_path!r} + '"'
saved = Rhino.RhinoApp.RunScript(save_cmd, False)
exists = os.path.exists({safe_path!r})
result = {{
    "ok": bool(rendered),
    "rendered": bool(rendered),
    "saved": bool(saved) and exists,
}}
"""
        res = _py(code)
        script = res.get("script_result")
        script = script if isinstance(script, dict) else {}
        saved = bool(script.get("saved"))
        ok = bool(res.get("ok")) and saved
        out: dict[str, object] = {
            "success": ok,
            "rendered": bool(script.get("rendered")),
            "saved": saved,
            "output_path": output_path if saved else None,
            "width": width,
            "height": height,
            "note": (
                "quality_preset is not scriptable for V-Ray from the Rhino command "
                "line and was not applied; render size was set via the document "
                "render settings before rendering."
            ),
            "result": res,
        }
        if not ok:
            out["error"] = str(
                res.get("error")
                or "Render window was not saved to output_path — the render may "
                   "have failed or still be in progress."
            )
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Create Material", destructiveHint=True))
    def vray_create_material(
        name: str,
        diffuse_color: list[int] | None = None,
        roughness: float = 0.5,
        metalness: float = 0.0,
        ior: float = 1.5,
        opacity: float = 1.0,
    ) -> dict[str, object]:
        """
        Create a V-Ray material via Python scripting inside Rhino.
        diffuse_color: [r, g, b] 0-255.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        r, g, b = (diffuse_color or [200, 200, 200])[:3]
        code = f"""
import Rhino
mat = Rhino.DocObjects.Material()
mat.Name = {name!r}
mat.DiffuseColor = Rhino.Display.Color4f({r} / 255.0, {g} / 255.0, {b} / 255.0, 1.0).AsSystemColor()
index = Rhino.RhinoDoc.ActiveDoc.Materials.Add(mat)
result = {{"ok": index >= 0, "name": {name!r}, "material_index": index}}
"""
        res = _py(code)
        ok, error = _outcome(res)
        out: dict[str, object] = {"success": ok, "name": name, "result": res}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Apply Material", destructiveHint=True))
    def vray_apply_material(
        object_ids: list[str],
        material_name: str,
    ) -> dict[str, object]:
        """Assign a named material to a list of Rhino objects by GUID."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        ids_repr = repr(object_ids)
        code = f"""
import rhinoscriptsyntax as rs
import Rhino
doc = Rhino.RhinoDoc.ActiveDoc
mat_index = doc.Materials.Find({material_name!r}, True)
if mat_index < 0:
    result = {{"ok": False, "error": "Material not found: " + {material_name!r}}}
else:
    applied = 0
    for oid in {ids_repr}:
        obj = doc.Objects.FindId(rs.coerceguid(oid))
        if obj:
            obj.Attributes.MaterialIndex = mat_index
            obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
            obj.CommitChanges()
            applied += 1
    result = {{"ok": True, "applied": applied, "material": {material_name!r}}}
"""
        res = _py(code)
        ok, error = _outcome(res)
        out: dict[str, object] = {
            "success": ok,
            "material_name": material_name,
            "object_count": len(object_ids),
            "result": res,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Add Light", destructiveHint=True))
    def vray_add_light(
        light_type: str = "Rectangle",
        position: list[float] | None = None,
        target: list[float] | None = None,
        intensity: float = 1.0,
        color: list[int] | None = None,
    ) -> dict[str, object]:
        """
        Add a V-Ray light via Rhino command.
        light_type: Rectangle | Sphere | IES | Dome | Sun.
        position: [x, y, z]. target: [x, y, z].
        color: [r, g, b] 0-255.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        cmd_map = {
            "Rectangle": "_VRayLightRect",
            "Sphere": "_VRayLightSphere",
            "IES": "_VRayLightIES",
            "Dome": "_VRayLightDome",
            "Sun": "_VRaySun",
        }
        cmd = cmd_map.get(light_type, "_VRayLightRect")
        result = _run(cmd)
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "light_type": light_type,
            "note": (
                f"{cmd} is an interactive Rhino command that expects mouse input; "
                "position, target, intensity, and color could not be applied "
                "programmatically. Adjust the light in the V-Ray Asset Editor."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Set Environment (HDRI)", destructiveHint=True))
    def vray_set_environment(
        hdri_path: str,
        intensity: float = 1.0,
        rotation_degrees: float = 0.0,
    ) -> dict[str, object]:
        """Set the V-Ray environment to an HDRI file."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayOptions")
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "_VRayOptions opens the interactive V-Ray Asset Editor; hdri_path, "
                "intensity, and rotation_degrees could not be applied programmatically. "
                "Set the environment HDRI manually in the editor."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Set Render Settings", destructiveHint=True))
    def vray_set_render_settings(
        width: int = 1920,
        height: int = 1080,
        aa_subdivs: int = 4,
        gi_preset: str = "interior",
        time_limit_seconds: int = 0,
    ) -> dict[str, object]:
        """
        Configure V-Ray render resolution and quality settings.
        gi_preset: interior | exterior | studio.
        time_limit_seconds: 0 means no limit.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import rhinoscriptsyntax as rs
previous = rs.RenderResolution(({width}, {height}))
result = {{"ok": True, "width": {width}, "height": {height}, "previous": list(previous) if previous else None}}
"""
        res = _py(code)
        ok, error = _outcome(res)
        out: dict[str, object] = {
            "success": ok,
            "width": width,
            "height": height,
            "note": (
                "Only the render resolution is scriptable here; aa_subdivs, "
                "gi_preset, and time_limit_seconds are V-Ray Asset Editor settings "
                "and were not applied programmatically."
            ),
            "result": res,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Export VRScene", destructiveHint=True))
    def vray_export_vrscene(
        output_path: str,
        compressed: bool = False,
    ) -> dict[str, object]:
        """Export the current scene as a .vrscene file for V-Ray Standalone."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('_VRayExportScene "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "output_path": output_path,
            "compressed": compressed,
            "result": result,
        }
        if error:
            out["error"] = error
        return out

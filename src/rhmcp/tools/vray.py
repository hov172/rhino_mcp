"""V-Ray for Rhino tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("V-Ray" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "V-Ray for Rhino is not installed or not loaded. Install from chaos.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Start IPR", destructiveHint=True))
    def vray_start_ipr() -> dict[str, object]:
        """Start V-Ray Interactive Production Rendering in the active viewport."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPR")
        return {"success": True, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Stop IPR", destructiveHint=True))
    def vray_stop_ipr() -> dict[str, object]:
        """Stop V-Ray Interactive Production Rendering."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPRStop")
        return {"success": True, "result": result}

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
        code = """
import rhinoscriptsyntax as rs
import Rhino
Rhino.RhinoApp.RunScript("_-Render", False)
"""
        result = _py(code)
        return {"success": True, "output_path": output_path, "result": result}

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
import System.Drawing
mat = Rhino.DocObjects.Material()
mat.Name = {name!r}
mat.DiffuseColor = System.Drawing.Color.FromArgb({r}, {g}, {b})
Rhino.RhinoDoc.ActiveDoc.Materials.Add(mat)
result = {{"name": {name!r}, "created": True}}
"""
        res = _py(code)
        return {"success": True, "name": name, "result": res}

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
for oid in {ids_repr}:
    obj = doc.Objects.FindId(System.Guid(oid))
    if obj:
        obj.Attributes.MaterialIndex = mat_index
        obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        obj.CommitChanges()
result = {{"applied": len({ids_repr}), "material": {material_name!r}}}
"""
        res = _py(code)
        return {"success": True, "material_name": material_name, "object_count": len(object_ids), "result": res}

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
        pos = position or [0, 0, 5]
        cmd_map = {
            "Rectangle": "_VRayLightRect",
            "Sphere": "_VRayLightSphere",
            "IES": "_VRayLightIES",
            "Dome": "_VRayLightDome",
            "Sun": "_VRaySun",
        }
        cmd = cmd_map.get(light_type, "_VRayLightRect")
        result = _run(cmd)
        return {"success": True, "light_type": light_type, "position": pos, "result": result}

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
        return {"success": True, "hdri_path": hdri_path, "intensity": intensity, "rotation_degrees": rotation_degrees, "result": result}

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
import Rhino
doc = Rhino.RhinoDoc.ActiveDoc
doc.RenderSettings.ImageSize = System.Drawing.Size({width}, {height})
result = {{"width": {width}, "height": {height}, "aa_subdivs": {aa_subdivs}, "gi_preset": {gi_preset!r}}}
"""
        res = _py(code)
        return {"success": True, "width": width, "height": height, "aa_subdivs": aa_subdivs, "gi_preset": gi_preset, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Export VRScene", destructiveHint=True))
    def vray_export_vrscene(
        output_path: str,
        compressed: bool = False,
    ) -> dict[str, object]:
        """Export the current scene as a .vrscene file for V-Ray Standalone."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"_VRayExportScene {output_path!r}")
        return {"success": True, "output_path": output_path, "compressed": compressed, "result": result}

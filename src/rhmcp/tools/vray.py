"""V-Ray for Rhino tools.

Scriptable settings go through the documented V-Ray Python module
(``rh8VRay`` for CPython, ``rhVRay`` for IronPython): render size, quality
preset and rendering.  Everything else uses the documented ``vray*`` Rhino
commands, several of which are interactive.  Every result reports what was
``applied`` and what was ``not_applied``.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend
from rhmcp.tools_helpers import plugin_client
from rhmcp.tools_helpers.security import sanitise_rhino_path

# quality_preset -> V-Ray SettingsOptions.quality_preset
# (0 Low, 1 Low+, 2 Medium, 3 Medium+, 4 High, 5 High+, 6 Custom)
_QUALITY_PRESETS = {"low": 0, "medium": 2, "high": 4, "ultra": 5}

_LIGHT_TYPES = {
    "Rectangle": "Rectangular",
    "Sphere": "Sphere",
    "Directional": "Directional",
    "Spot": "Spot",
    "IES": "IES",
    "Omni": "Omni",
    "Dome": "Dome",
    "Sun": "Sun",
}

# Guarded import of the documented V-Ray for Rhino scripting module.
_VRAY_IMPORT = r'''
try:
    import rh8VRay as vray
except ImportError:
    try:
        import rhVRay as vray
    except ImportError:
        vray = None
'''

_SCRIPT_VRAY_SETTINGS = _VRAY_IMPORT + r'''
_applied = {}
_not_applied = {}
_error = None
if vray is None:
    _not_applied.update(_mcp_settings)
    _error = "V-Ray Python module (rh8VRay / rhVRay) is not importable in this Rhino."
else:
    try:
        with vray.Scene.Transaction():
            if "width" in _mcp_settings:
                vray.Scene.SettingsOutput.img_width = int(_mcp_settings["width"])
                _applied["width"] = _mcp_settings["width"]
            if "height" in _mcp_settings:
                vray.Scene.SettingsOutput.img_height = int(_mcp_settings["height"])
                _applied["height"] = _mcp_settings["height"]
            if "quality_preset" in _mcp_settings:
                vray.Scene.SettingsOptions.quality_preset = int(_mcp_quality_value)
                _applied["quality_preset"] = _mcp_settings["quality_preset"]
    except Exception as ex:
        _error = str(ex)
    for _k in _mcp_settings:
        if _k not in _applied:
            _not_applied[_k] = _mcp_settings[_k]
result = {"ok": not _not_applied, "applied": _applied, "not_applied": _not_applied}
if _error:
    result["error"] = _error
'''

_SCRIPT_VRAY_RENDER = _VRAY_IMPORT + r'''
import os
_rendered = False
_error = None
if vray is None:
    _error = "V-Ray Python module (rh8VRay / rhVRay) is not importable in this Rhino."
else:
    try:
        # mode 0 = production, engine 0 = CPU, timeout -1 = wait for completion
        vray.Render(0, 0, -1)
        _rendered = True
    except Exception as ex:
        _error = str(ex)
_saved = False
if _rendered and _mcp_output_path:
    try:
        import Rhino
        Rhino.RhinoApp.RunScript('_-SaveRenderWindowAs "' + _mcp_output_path + '"', False)
    except Exception:
        pass
    _saved = os.path.exists(_mcp_output_path)
result = {"ok": _rendered, "rendered": _rendered, "saved": _saved}
if _error:
    result["error"] = _error
'''


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


def _script(res: dict) -> dict:
    script = res.get("script_result")
    return script if isinstance(script, dict) else {}


def _apply_settings(settings: dict[str, object]) -> dict[str, object]:
    """Apply width/height/quality_preset through the V-Ray Python module."""
    preset = settings.get("quality_preset")
    code = (
        "_mcp_settings = {}\n"
        "_mcp_quality_value = {}\n"
        "{}"
    ).format(
        json.dumps(settings),
        json.dumps(_QUALITY_PRESETS.get(str(preset), 2)),
        _SCRIPT_VRAY_SETTINGS,
    )
    res = _py(code)
    script = _script(res)
    out: dict[str, object] = {
        "success": bool(res.get("ok")) and bool(script.get("ok")),
        "applied": script.get("applied", {}),
        "not_applied": script.get("not_applied", settings),
        "result": res,
    }
    error = script.get("error") or (None if res.get("ok") else res.get("error"))
    if error:
        out["error"] = str(error)
    return out


def _command_tool(command: str, note: str, **extra: object) -> dict[str, object]:
    result = _run(command)
    ok, error = _outcome(result)
    out: dict[str, object] = {"success": ok, "command": command, "note": note, "result": result}
    out.update(extra)
    if error:
        out["error"] = error
    return out


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Start IPR", destructiveHint=True))
    def vray_start_ipr() -> dict[str, object]:
        """Start V-Ray interactive rendering by running ``_vrayRender _Interactive``."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _command_tool("_vrayRender _Interactive", "Runs the documented vrayRender command in Interactive mode.")

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Stop IPR", destructiveHint=True))
    def vray_stop_ipr() -> dict[str, object]:
        """Stop V-Ray rendering by running ``_vrayRender _Stop``."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _command_tool("_vrayRender _Stop", "Runs the documented vrayRender command in Stop mode.")

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Render", destructiveHint=True))
    def vray_render(
        output_path: str | None = None,
        width: int = 1920,
        height: int = 1080,
        quality_preset: str = "medium",
    ) -> dict[str, object]:
        """Render a production image with V-Ray.

        ``width``, ``height`` and ``quality_preset`` (``low`` | ``medium`` |
        ``high`` | ``ultra``, mapped to V-Ray's Low/Medium/High/High+ presets)
        are applied through the V-Ray Python module, then ``vray.Render`` runs
        synchronously. When ``output_path`` is given Rhino's
        ``_-SaveRenderWindowAs`` is attempted and ``saved`` reports whether
        the file exists; V-Ray's own frame buffer may not honour it, so check
        ``saved``. The result lists ``applied`` / ``not_applied`` settings.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        preset = quality_preset.strip().lower()
        if preset not in _QUALITY_PRESETS:
            return {"success": False, "message": "quality_preset must be one of: " + ", ".join(_QUALITY_PRESETS)}
        settings = _apply_settings({"width": int(width), "height": int(height), "quality_preset": preset})
        safe_path = sanitise_rhino_path(output_path) if output_path else ""
        res = _py("_mcp_output_path = {}\n{}".format(json.dumps(safe_path), _SCRIPT_VRAY_RENDER))
        script = _script(res)
        rendered = bool(res.get("ok")) and bool(script.get("rendered"))
        saved = bool(script.get("saved"))
        out: dict[str, object] = {
            "success": rendered,
            "rendered": rendered,
            "saved": saved,
            "output_path": output_path if saved else None,
            "applied": settings["applied"],
            "not_applied": settings["not_applied"],
            "result": res,
        }
        error = script.get("error") or settings.get("error") or (None if res.get("ok") else res.get("error"))
        if error:
            out["error"] = str(error)
        return out

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Create Material", destructiveHint=True))
    def vray_create_material(
        name: str,
        diffuse_color: list[int] | None = None,
        opacity: float = 1.0,
    ) -> dict[str, object]:
        """Create a standard Rhino material that V-Ray converts when rendering.

        Only ``diffuse_color`` ([r, g, b] 0-255) and ``opacity`` (0-1, stored
        as Rhino ``Material.Transparency``) exist on a Rhino material; V-Ray
        documents no scripting API for creating VRayMtl assets, so
        roughness, metalness and IOR are not offered. Use the V-Ray Asset
        Editor (``vray_set_environment``) or ``_vrayMtlFromRhino`` to convert.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        r, g, b = (diffuse_color or [200, 200, 200])[:3]
        opacity = max(0.0, min(1.0, float(opacity)))
        code = f"""
import Rhino
mat = Rhino.DocObjects.Material()
mat.Name = {name!r}
mat.DiffuseColor = Rhino.Display.Color4f({r} / 255.0, {g} / 255.0, {b} / 255.0, 1.0).AsSystemColor()
mat.Transparency = 1.0 - {opacity}
index = Rhino.RhinoDoc.ActiveDoc.Materials.Add(mat)
result = {{"ok": index >= 0, "name": {name!r}, "material_index": index}}
"""
        res = _py(code)
        ok, error = _outcome(res)
        requested = {"diffuse_color": [r, g, b], "opacity": opacity}
        out: dict[str, object] = {
            "success": ok,
            "name": name,
            "applied": requested if ok else {},
            "not_applied": {} if ok else requested,
            "note": "Standard Rhino material; V-Ray converts it on render.",
            "result": res,
        }
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
    def vray_add_light(light_type: str = "Rectangle") -> dict[str, object]:
        """Launch the interactive ``_vrayLight _Create`` command for a light type.

        ``light_type``: Rectangle | Sphere | Directional | Spot | IES | Omni |
        Dome | Sun. The command then expects mouse input for placement;
        position, target, intensity and colour cannot be scripted and are
        set afterwards in the V-Ray Asset Editor.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        option = _LIGHT_TYPES.get(light_type)
        if option is None:
            return {"success": False, "message": "light_type must be one of: " + ", ".join(_LIGHT_TYPES)}
        cmd = f"_vrayLight _Create _{option}"
        return _command_tool(
            cmd,
            f"{cmd} is interactive and expects mouse input for placement.",
            light_type=light_type,
        )

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Open Asset Editor (Environment)", destructiveHint=True))
    def vray_set_environment() -> dict[str, object]:
        """Open the V-Ray Asset Editor (``_vrayShowAssetEditor``).

        V-Ray documents no scripting API for the environment/dome HDRI, so
        this tool only opens the editor where the environment is set
        interactively; nothing is applied programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _command_tool(
            "_vrayShowAssetEditor",
            "Opens the interactive V-Ray Asset Editor; set the environment HDRI there.",
        )

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Set Render Settings", destructiveHint=True))
    def vray_set_render_settings(
        width: int | None = None,
        height: int | None = None,
        quality_preset: str | None = None,
    ) -> dict[str, object]:
        """Set V-Ray output size and quality preset through the V-Ray Python module.

        ``quality_preset``: low | medium | high | ultra (V-Ray Low / Medium /
        High / High+). Only the parameters passed are changed. V-Ray documents
        no scripting access for AA subdivisions, GI presets or time limits,
        so none are offered. The result lists ``applied`` / ``not_applied``.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        settings: dict[str, object] = {}
        if width is not None:
            settings["width"] = int(width)
        if height is not None:
            settings["height"] = int(height)
        if quality_preset is not None:
            preset = quality_preset.strip().lower()
            if preset not in _QUALITY_PRESETS:
                return {"success": False, "message": "quality_preset must be one of: " + ", ".join(_QUALITY_PRESETS)}
            settings["quality_preset"] = preset
        if not settings:
            return {"success": False, "message": "Pass at least one setting to change."}
        return _apply_settings(settings)

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Export VRScene", destructiveHint=True))
    def vray_export_vrscene(output_path: str) -> dict[str, object]:
        """Export the scene as a ``.vrscene`` via ``_vrayExportVRScene``.

        The command documents no compression option, so none is offered.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        return _command_tool(
            '_vrayExportVRScene "' + safe_path + '"',
            "Runs the documented vrayExportVRScene command; it may prompt interactively.",
            output_path=output_path,
        )

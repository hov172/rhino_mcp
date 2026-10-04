"""
Tools for visual / game-engine export formats: OBJ, FBX, GLB/GLTF.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Export OBJ", destructiveHint=True))
    def export_obj(
        path: str,
        export_materials: bool = True,
        export_textures: bool = True,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to a Wavefront OBJ file.

        When ``export_materials`` is True an accompanying ``.mtl`` file is
        written beside the OBJ.  ``export_textures`` controls whether texture
        coordinates are written.  Rhino's ``FileObjWriteOptions`` has no
        weld-angle setting, so none is offered here.  The result reports
        ``applied`` / ``not_applied`` for each option."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_export_textures = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            repr(export_materials),
            repr(export_textures),
            repr(object_ids),
            _OBJ_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export FBX", destructiveHint=True))
    def export_fbx(
        path: str,
        file_type: str = "binary7",
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to an FBX file for game engines and DCC tools.

        ``file_type`` selects ``FileFbxWriteOptions.FileType``: ``binary7``
        (default), ``binary6``, ``ascii7`` or ``ascii6`` (FBX format
        version 7.x / 6.x).  Rhino exposes no FBX SDK year version and no
        texture embedding switch; textures are always written as external
        references.  The result reports ``applied`` / ``not_applied``."""
        file_type = file_type.strip().lower()
        if file_type not in _FBX_FILE_TYPES:
            return {
                "ok": False,
                "error": "file_type must be one of: {}".format(", ".join(sorted(_FBX_FILE_TYPES))),
            }
        code = (
            "_mcp_path = {}\n"
            "_mcp_file_type = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(_FBX_FILE_TYPES[file_type]),
            repr(object_ids),
            _FBX_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export GLB / glTF", destructiveHint=True))
    def export_glb(
        path: str,
        draco_compression: bool = False,
        export_materials: bool = True,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to a GLB or glTF file.

        The extension decides texture handling: ``.glb`` always embeds
        textures in one binary file, ``.gltf`` always writes a JSON file with
        external resources.  There is no separate embed switch.  The result
        reports ``applied`` / ``not_applied`` for ``draco_compression`` and
        ``export_materials``."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_draco_compression = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            repr(draco_compression),
            repr(export_materials),
            repr(object_ids),
            _GLB_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


_FBX_FILE_TYPES = {
    "binary7": "Binary7",
    "binary6": "Binary6",
    "ascii7": "Ascii7",
    "ascii6": "Ascii6",
}


# ---------------------------------------------------------------------------
# Embedded Python scripts executed inside Rhino
# ---------------------------------------------------------------------------

_OBJ_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Select objects ---------------------------------------------------------
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

# Attempt RhinoCommon FileObjWriteOptions --------------------------------
_ok = False
_options_applied = False
try:
    _fwo = Rhino.FileIO.FileWriteOptions()
    _fwo.SuppressDialogBoxes = True
    _fwo.SuppressAllInput = True
    if _mcp_object_ids:
        _fwo.WriteSelectedObjectsOnly = True
    opts = Rhino.FileIO.FileObjWriteOptions(_fwo)
    opts.ExportMaterialDefinitions = _mcp_export_materials
    opts.MapZtoY = True
    opts.ExportTcs = _mcp_export_textures
    _rc = Rhino.FileIO.FileObj.Write(_mcp_path, doc, opts)
    _ok = (_rc == Rhino.PlugIns.WriteFileResult.Success)
    _options_applied = _ok
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False)
    import os
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
_requested = {
    "export_materials": _mcp_export_materials,
    "export_texture_coordinates": _mcp_export_textures,
}
result = {
    "path": _mcp_path,
    "format": "OBJ",
    "ok": bool(_ok),
    "requested": _requested,
    "applied": _requested if _options_applied else {},
    "not_applied": {} if _options_applied else _requested,
}
if _ok and not _options_applied:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current OBJ "
        "settings; the requested options were not applied."
    )
'''

_FBX_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Select objects ---------------------------------------------------------
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

# Attempt RhinoCommon FileFbxWriteOptions --------------------------------
_ok = False
_file_type_applied = False
try:
    opts = Rhino.FileIO.FileFbxWriteOptions()
    _ft = getattr(Rhino.FileIO.FileFbxWriteOptions.FileType, _mcp_file_type, None)
    if _ft is not None:
        opts.SaveFileAs = _ft
        _file_type_applied = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(doc.Export(_mcp_path, opts.ToDictionary()))
    _file_type_applied = _file_type_applied and _ok
except Exception:
    _ok = False
    _file_type_applied = False

# Fallback to command export ---------------------------------------------
if not _ok:
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False)
    import os
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": "FBX",
    "ok": bool(_ok),
    "requested": {"file_type": _mcp_file_type},
    "applied": {"file_type": _mcp_file_type} if _file_type_applied else {},
    "not_applied": {} if _file_type_applied else {"file_type": _mcp_file_type},
}
if _ok and not _file_type_applied:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current FBX "
        "settings; file_type was not applied."
    )
'''

_GLB_SCRIPT = r'''
import os
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Select objects ---------------------------------------------------------
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

# Derive reported format from file extension -----------------------------
_ext = os.path.splitext(_mcp_path)[1].lower()
_fmt = "GLTF" if _ext == ".gltf" else "GLB"

# Attempt RhinoCommon FileGltfWriteOptions -------------------------------
_ok = False
_options_applied = False
try:
    opts = Rhino.FileIO.FileGltfWriteOptions()
    opts.UseDracoCompression = _mcp_draco_compression
    opts.ExportMaterials = _mcp_export_materials
    opts.ExportTextureCoordinates = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(doc.Export(_mcp_path, opts.ToDictionary()))
    _options_applied = _ok
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False)
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
_requested = {
    "draco_compression": _mcp_draco_compression,
    "export_materials": _mcp_export_materials,
}
result = {
    "path": _mcp_path,
    "format": _fmt,
    "textures": "embedded" if _fmt == "GLB" else "external",
    "ok": bool(_ok),
    "requested": _requested,
    "applied": _requested if _options_applied else {},
    "not_applied": {} if _options_applied else _requested,
}
if _ok and not _options_applied:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current glTF "
        "settings; the requested options were not applied."
    )
'''

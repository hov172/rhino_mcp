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
        weld_angle: float = 30.0,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to a Wavefront OBJ file.

        When ``export_materials`` is True an accompanying ``.mtl`` file is
        written beside the OBJ.  ``export_textures`` controls whether..."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_export_textures = {}\n"
            "_mcp_weld_angle = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            repr(export_materials),
            repr(export_textures),
            json.dumps(weld_angle),
            repr(object_ids),
            _OBJ_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export FBX", destructiveHint=True))
    def export_fbx(
        path: str,
        fbx_version: str = "FBX202000",
        embed_textures: bool = True,
        save_textures_as_references: bool = False,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to an FBX file for game engines and DCC tools.

        ``fbx_version`` must be one of ``FBX201400``, ``FBX201600``,
        ``FBX201800``, or ``FBX202000``.  When ``embed_textures``..."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_fbx_version = {}\n"
            "_mcp_embed_textures = {}\n"
            "_mcp_save_textures_as_references = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(fbx_version),
            repr(embed_textures),
            repr(save_textures_as_references),
            repr(object_ids),
            _FBX_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export GLB / glTF", destructiveHint=True))
    def export_glb(
        path: str,
        embed_textures: bool = True,
        draco_compression: bool = False,
        export_materials: bool = True,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export geometry to a GLB or glTF file.

        Use a ``.glb`` extension for a single self-contained binary file or
        ``.gltf`` for a JSON-based file with external resources...."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_embed_textures = {}\n"
            "_mcp_draco_compression = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            repr(embed_textures),
            repr(draco_compression),
            repr(export_materials),
            repr(object_ids),
            _GLB_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


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
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False)
    import os
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": "OBJ",
    "export_materials": _mcp_export_materials,
    "export_texture_coordinates": _mcp_export_textures,
    "ok": bool(_ok),
    "requested_not_applied": {"weld_angle": _mcp_weld_angle},
    "note": "FileObjWriteOptions has no weld-angle option; weld_angle was not applied.",
}
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
try:
    opts = Rhino.FileIO.FileFbxWriteOptions()
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(Rhino.FileIO.FileFbx.Write(_mcp_path, doc, opts))
except Exception:
    _ok = False

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
    "requested_not_applied": {
        "fbx_version": _mcp_fbx_version,
        "embed_textures": _mcp_embed_textures,
        "save_textures_as_references": _mcp_save_textures_as_references,
    },
    "note": (
        "FileFbxWriteOptions exposes no FBX version or texture-embedding "
        "options (only SaveFileAs binary/ascii 6/7, SaveMaterialsAs, "
        "SaveObjectsAs, etc.); these requested settings were not applied."
    ),
}
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
try:
    opts = Rhino.FileIO.FileGltfWriteOptions()
    opts.UseDracoCompression = _mcp_draco_compression
    opts.ExportMaterials = _mcp_export_materials
    opts.ExportTextureCoordinates = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(Rhino.FileIO.FileGltf.Write(_mcp_path, doc, opts))
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False)
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": _fmt,
    "draco_compression": _mcp_draco_compression,
    "export_materials": _mcp_export_materials,
    "ok": bool(_ok),
    "requested_not_applied": {"embed_textures": _mcp_embed_textures},
    "note": (
        "FileGltfWriteOptions has no texture-embedding switch; .glb always "
        "embeds textures and .gltf writes external resources."
    ),
}
'''

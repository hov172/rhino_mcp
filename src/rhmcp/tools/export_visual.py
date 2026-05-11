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
        """
        Export geometry to a Wavefront OBJ file.

        When ``export_materials`` is True an accompanying ``.mtl`` file is
        written beside the OBJ.  ``export_textures`` controls whether texture
        paths are written into the MTL.  ``weld_angle`` sets the smoothing-group
        crease threshold in degrees.  Pass ``object_ids`` to restrict export to
        specific objects; otherwise all visible objects are exported.
        """
        code = (
            "_mcp_path = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_export_textures = {}\n"
            "_mcp_weld_angle = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(export_materials),
            json.dumps(export_textures),
            json.dumps(weld_angle),
            json.dumps(object_ids),
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
        """
        Export geometry to an FBX file for game engines and DCC tools.

        ``fbx_version`` must be one of ``FBX201400``, ``FBX201600``,
        ``FBX201800``, or ``FBX202000``.  When ``embed_textures`` is True,
        texture data is stored inside the FBX; set
        ``save_textures_as_references`` to True to keep textures as external
        file references instead.  Pass ``object_ids`` to restrict export to
        specific objects.
        """
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
            json.dumps(embed_textures),
            json.dumps(save_textures_as_references),
            json.dumps(object_ids),
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
        """
        Export geometry to a GLB or glTF file.

        Use a ``.glb`` extension for a single self-contained binary file or
        ``.gltf`` for a JSON-based file with external resources.
        ``embed_textures`` stores texture data inside the file.
        ``draco_compression`` enables Draco mesh compression to reduce file
        size (requires the Draco encoder to be available in Rhino).
        Pass ``object_ids`` to restrict export to specific objects.
        """
        code = (
            "_mcp_path = {}\n"
            "_mcp_embed_textures = {}\n"
            "_mcp_draco_compression = {}\n"
            "_mcp_export_materials = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(embed_textures),
            json.dumps(draco_compression),
            json.dumps(export_materials),
            json.dumps(object_ids),
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
    opts = Rhino.FileIO.FileObjWriteOptions(Rhino.FileIO.FileWriteOptions())
    if hasattr(opts, 'ExportMaterialDefinitions'):
        opts.ExportMaterialDefinitions = _mcp_export_materials
    if hasattr(opts, 'MapRhinoZToObjY'):
        opts.MapRhinoZToObjY = True
    if hasattr(opts, 'WeldAngle'):
        opts.WeldAngle = _mcp_weld_angle
    if hasattr(opts, 'ExportTextureCoordinates'):
        opts.ExportTextureCoordinates = _mcp_export_textures
    _ok = Rhino.FileIO.FileObj.Write(_mcp_path, doc, opts)
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path), False)
    import os
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": "OBJ",
    "export_materials": _mcp_export_materials,
    "ok": bool(_ok),
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
    opts = Rhino.FileIO.FileFbxWriteOptions(Rhino.FileIO.FileWriteOptions())
    if hasattr(opts, 'FbxVersion'):
        _version_map = {
            'FBX201400': Rhino.FileIO.FileFbxWriteOptions.FBXVersion.FBX201400,
            'FBX201600': Rhino.FileIO.FileFbxWriteOptions.FBXVersion.FBX201600,
            'FBX201800': Rhino.FileIO.FileFbxWriteOptions.FBXVersion.FBX201800,
            'FBX202000': Rhino.FileIO.FileFbxWriteOptions.FBXVersion.FBX202000,
        }
        _ver = _version_map.get(_mcp_fbx_version)
        if _ver is not None:
            opts.FbxVersion = _ver
    if hasattr(opts, 'EmbedTexturesInFile'):
        opts.EmbedTexturesInFile = _mcp_embed_textures
    if hasattr(opts, 'SaveTexturesAsReferences'):
        opts.SaveTexturesAsReferences = _mcp_save_textures_as_references
    _ok = Rhino.FileIO.FileFbx.Write(_mcp_path, doc, opts)
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path), False)
    import os
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": "FBX",
    "fbx_version": _mcp_fbx_version,
    "ok": bool(_ok),
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
    opts = Rhino.FileIO.FileGltfWriteOptions(Rhino.FileIO.FileWriteOptions())
    if hasattr(opts, 'EmbedTextures'):
        opts.EmbedTextures = _mcp_embed_textures
    if hasattr(opts, 'UseDracoCompression'):
        opts.UseDracoCompression = _mcp_draco_compression
    if hasattr(opts, 'ExportMaterials'):
        opts.ExportMaterials = _mcp_export_materials
    if hasattr(opts, 'ExportTextureCoordinates'):
        opts.ExportTextureCoordinates = _mcp_export_textures
    _ok = Rhino.FileIO.FileGltf.Write(_mcp_path, doc, opts)
except Exception:
    _ok = False

# Fallback to command export ---------------------------------------------
if not _ok:
    rs.Command('_-Export "{}" _Enter'.format(_mcp_path), False)
    _ok = os.path.isfile(_mcp_path)

rs.UnselectAllObjects()
result = {
    "path": _mcp_path,
    "format": _fmt,
    "ok": bool(_ok),
}
'''

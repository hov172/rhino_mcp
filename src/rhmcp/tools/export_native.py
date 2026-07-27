"""
Tool for exporting Rhino documents to the native 3DM format.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Export 3DM", destructiveHint=True))
    def export_3dm(
        path: str,
        rhino_version: int = 8,
        include_render_meshes: bool = True,
        include_preview_image: bool = True,
        object_ids: list[str] | None = None,
        notes: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export the active Rhino document (or a subset of objects) to a native
        3DM file.

        ``path`` must end in ``.3dm``.  ``rhino_version`` controls the on-disk
        format version (4, 5,..."""
        code = (
            "_mcp_path = {path}\n"
            "_mcp_rhino_version = {rhino_version}\n"
            "_mcp_render_meshes = {render_meshes}\n"
            "_mcp_preview_image = {preview_image}\n"
            "_mcp_object_ids = {object_ids}\n"
            "_mcp_notes = {notes}\n"
            "{script}"
        ).format(
            path=json.dumps(path),
            rhino_version=json.dumps(rhino_version),
            render_meshes=repr(include_render_meshes),
            preview_image=repr(include_preview_image),
            object_ids=repr(object_ids),
            notes=repr(notes),
            script=_EXPORT_3DM_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


_EXPORT_3DM_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Embed notes when requested
if _mcp_notes is not None:
    try:
        doc.Notes.Notes = _mcp_notes
    except Exception:
        pass

ok = False

if _mcp_object_ids is None:
    # Save the full document
    try:
        options = Rhino.FileIO.FileWriteOptions()
        options.SuppressDialogBoxes = True
        options.SuppressAllInput = True
        options.FileVersion = int(_mcp_rhino_version)
        options.IncludeRenderMeshes = _mcp_render_meshes
        options.IncludePreviewImage = _mcp_preview_image
        ok = bool(doc.WriteFile(_mcp_path, options))
    except Exception:
        ok = False
    if not ok:
        try:
            _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
            ok = bool(rs.Command(
                '_-SaveAs _Version={} "{}" _Enter'.format(int(_mcp_rhino_version), _mcp_path_safe),
                False,
            ))
        except Exception:
            ok = False
else:
    # Save only the listed objects into a new File3dm archive
    try:
        import System
        archive = Rhino.FileIO.File3dm()
        for id_str in _mcp_object_ids:
            try:
                guid = System.Guid(id_str)
            except Exception:
                continue
            obj = doc.Objects.FindId(guid)
            if obj is not None:
                archive.Objects.AddObject(obj.Geometry, obj.Attributes)
        ok = bool(archive.Write(_mcp_path, int(_mcp_rhino_version)))
    except Exception as _e:
        ok = False
        try:
            _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
            ok = bool(rs.Command(
                '_-SaveAs _Version={} "{}" _Enter'.format(int(_mcp_rhino_version), _mcp_path_safe),
                False,
            ))
        except Exception:
            ok = False

result = {
    "path": _mcp_path,
    "format": "3DM",
    "rhino_version": _mcp_rhino_version,
    "include_render_meshes": _mcp_render_meshes,
    "ok": ok,
}
'''

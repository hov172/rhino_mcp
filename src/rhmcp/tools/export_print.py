"""
Tools for exporting Rhino geometry to 3D-printing formats (STL, 3MF).
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Export STL", destructiveHint=True))
    def export_stl(
        path: str,
        binary: bool = True,
        object_ids: list[str] | None = None,
        tolerance: float | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Export geometry to an STL file for 3D printing.

        Parameters
        ----------
        path:
            Output file path; must end in ``.stl``.
        binary:
            ``True`` (default) writes compact binary STL.
            ``False`` writes human-readable ASCII STL.
        object_ids:
            List of object GUIDs to export.  ``None`` exports everything in
            the document.
        tolerance:
            Mesh tolerance override (document units).  ``None`` uses the
            document's current absolute tolerance.
        rhino_id:
            Target Rhino instance ID when multiple instances are running.
        """
        code = (
            "_mcp_path = {path}\n"
            "_mcp_binary = {binary}\n"
            "_mcp_object_ids = {ids}\n"
            "_mcp_tolerance = {tol}\n"
            "{script}"
        ).format(
            path=json.dumps(path),
            binary=repr(binary),
            ids=repr(object_ids),
            tol=repr(tolerance),
            script=_STL_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export 3MF", destructiveHint=True))
    def export_3mf(
        path: str,
        object_ids: list[str] | None = None,
        mesh_quality: str = "normal",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Export geometry to a 3MF file (Rhino 8 natively supports this format).

        Parameters
        ----------
        path:
            Output file path; must end in ``.3mf``.
        object_ids:
            List of object GUIDs to export.  ``None`` exports everything in
            the document.
        mesh_quality:
            Controls mesh density used when tessellating NURBS geometry.
            Accepted values: ``"coarse"``, ``"normal"`` (default), ``"fine"``,
            ``"custom"``.  Passed as a hint only; the exporter may ignore it
            if the 3MF plugin does not expose a quality option via command
            line.
        rhino_id:
            Target Rhino instance ID when multiple instances are running.
        """
        code = (
            "_mcp_path = {path}\n"
            "_mcp_object_ids = {ids}\n"
            "_mcp_mesh_quality = {quality}\n"
            "{script}"
        ).format(
            path=json.dumps(path),
            ids=repr(object_ids),
            quality=json.dumps(mesh_quality),
            script=_3MF_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


# ---------------------------------------------------------------------------
# Embedded Python scripts (run inside Rhino)
# ---------------------------------------------------------------------------

_STL_SCRIPT = r'''
import os
import rhinoscriptsyntax as rs
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc

# --- Select objects --------------------------------------------------------
rs.UnselectAllObjects()
if _mcp_object_ids:
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.SelectAllObjects()

selected = rs.SelectedObjects()
if not selected:
    result = {"path": _mcp_path, "format": "STL", "binary": _mcp_binary, "ok": False,
              "error": "No objects selected for export."}
else:
    # --- Optionally override mesh tolerance ---------------------------------
    if _mcp_tolerance is not None:
        mp = Rhino.Geometry.MeshingParameters.Default
        mp.RelativeTolerance = 0.0
        mp.MinimumTolerance = float(_mcp_tolerance)
        mp.Tolerance = float(_mcp_tolerance)
        Rhino.ApplicationSettings.MeshingParameters.CurrentParameters = mp

    # --- Attempt RhinoCommon FileIO write first, fall back to _-Export ------
    _wrote_ok = False
    try:
        opts = Rhino.FileIO.FileStlWriteOptions()
        opts.ExportOpenObjects = True
        if hasattr(opts, 'ExportBinaryFile'):
            opts.ExportBinaryFile = bool(_mcp_binary)
        _wrote_ok = Rhino.FileIO.RhinoFile.Write(_mcp_path, opts)
    except Exception as _fe:
        pass

    if not _wrote_ok:
        # Fall back: use the interactive Export command on the current selection
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '').replace('\0', '')
        _cmd = '_-Export "{}" _Enter'.format(_mcp_path_safe)
        rs.Command(_cmd, False)
        _wrote_ok = os.path.isfile(_mcp_path)

    rs.UnselectAllObjects()
    result = {
        "path": _mcp_path,
        "format": "STL",
        "binary": _mcp_binary,
        "ok": bool(_wrote_ok),
    }
    if not _wrote_ok:
        result["error"] = "Export produced no output file at: {}".format(_mcp_path)
'''

_3MF_SCRIPT = r'''
import os
import rhinoscriptsyntax as rs
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc

# --- Select objects --------------------------------------------------------
rs.UnselectAllObjects()
if _mcp_object_ids:
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.SelectAllObjects()

selected = rs.SelectedObjects()
if not selected:
    result = {"path": _mcp_path, "format": "3MF", "ok": False,
              "error": "No objects selected for export."}
else:
    # Export via built-in _-Export command (Rhino 8 supports 3MF natively)
    _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '').replace('\0', '')
    _cmd = '_-Export "{}" _Enter'.format(_mcp_path_safe)
    rs.Command(_cmd, False)
    _wrote_ok = os.path.isfile(_mcp_path)

    rs.UnselectAllObjects()
    result = {
        "path": _mcp_path,
        "format": "3MF",
        "mesh_quality": _mcp_mesh_quality,
        "ok": bool(_wrote_ok),
    }
    if not _wrote_ok:
        result["error"] = "Export produced no output file at: {}".format(_mcp_path)
'''

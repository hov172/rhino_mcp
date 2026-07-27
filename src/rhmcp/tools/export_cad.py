"""
Tools for engineering CAD format export: STEP, IGES, DWG/DXF.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Export STEP", destructiveHint=True))
    def export_step(
        path: str,
        schema: str = "AP214",
        tolerance: float = 0.001,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export selected objects (or all objects) to a STEP file.

        ``path`` must end in ``.step`` or ``.stp``.
        ``schema`` controls the STEP application protocol: ``"AP203"``,..."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_schema = {}\n"
            "_mcp_tolerance = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(schema),
            json.dumps(tolerance),
            repr(object_ids),
            _STEP_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export IGES", destructiveHint=True))
    def export_iges(
        path: str,
        tolerance: float = 0.001,
        trim_type: str = "parametric",
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export selected objects (or all objects) to an IGES file.

        ``path`` must end in ``.igs`` or ``.iges``.
        ``tolerance`` is the export tolerance in document units.
        ``trim_type``..."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_tolerance = {}\n"
            "_mcp_trim_type = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(tolerance),
            json.dumps(trim_type),
            repr(object_ids),
            _IGES_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export DWG / DXF", destructiveHint=True))
    def export_dwg(
        path: str,
        autocad_version: str = "2018",
        export_layout: bool = False,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Export selected objects (or all objects) to a DWG or DXF file.

        ``path`` must end in ``.dwg`` or ``.dxf``.
        ``autocad_version`` selects the AutoCAD file format version:..."""
        code = (
            "_mcp_path = {}\n"
            "_mcp_autocad_version = {}\n"
            "_mcp_export_layout = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(autocad_version),
            repr(export_layout),
            repr(object_ids),
            _DWG_SCRIPT,
        )
        return rhino.execute_python(code, rhino_id=rhino_id)


# ---------------------------------------------------------------------------
# Embedded Python scripts – each assigns a JSON-serialisable dict to `result`
# ---------------------------------------------------------------------------

_STEP_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Select objects
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

_ok = False
_error = None
_used_fallback = False
_schema_applied = False

try:
    opts = Rhino.FileIO.FileStpWriteOptions()
    # Map schema string to the real StepSchema enum names
    _schema_map = {
        "AP203": "SF_203",
        "AP214": "SF_214",
        "AP242": "SF_242",
    }
    _attr = _schema_map.get(_mcp_schema.upper())
    if _attr:
        _schema_enum = getattr(Rhino.FileIO.FileStpWriteOptions.StepSchema, _attr, None)
        if _schema_enum is not None:
            opts.Schema = _schema_enum
            _schema_applied = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(Rhino.FileIO.FileStp.Write(_mcp_path, doc, opts))
except Exception as _ex:
    _error = str(_ex)

if not _ok:
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
        _used_fallback = _ok
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "STEP",
    "ok": _ok,
    "requested": {"schema": _mcp_schema, "tolerance": _mcp_tolerance},
    "applied": {"schema": _mcp_schema} if (_schema_applied and not _used_fallback) else {},
    "note": "FileStpWriteOptions has no tolerance option; tolerance was not applied.",
}
if _used_fallback:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current STEP "
        "settings; the requested schema and tolerance were not applied."
    )
if _error and not _ok:
    result["error"] = _error
'''


_IGES_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# Select objects
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

_ok = False
_error = None
_used_fallback = False
_tolerance_applied = False

try:
    opts = Rhino.FileIO.FileIgsWriteOptions()
    opts.Tolerance = float(_mcp_tolerance)
    _tolerance_applied = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(Rhino.FileIO.FileIgs.Write(_mcp_path, doc, opts))
except Exception as _ex:
    _error = str(_ex)
    _tolerance_applied = False

if not _ok:
    _tolerance_applied = False
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
        _used_fallback = _ok
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "IGES",
    "ok": _ok,
    "requested": {"tolerance": _mcp_tolerance, "trim_type": _mcp_trim_type},
    "applied": {"tolerance": _mcp_tolerance} if _tolerance_applied else {},
    "note": "FileIgsWriteOptions has no trim-curve-type option; trim_type was not applied.",
}
if _used_fallback:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current IGES "
        "settings; the requested tolerance and trim_type were not applied."
    )
if _error and not _ok:
    result["error"] = _error
'''


_DWG_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc

# AutoCAD version -> RhinoCommon enum name mapping
_VERSION_MAP = {
    "2004": "Acad2004",
    "2007": "Acad2007",
    "2010": "Acad2010",
    "2013": "Acad2013",
    "2018": "Acad2018",
}

# Select objects
if _mcp_object_ids:
    rs.UnselectAllObjects()
    for oid in _mcp_object_ids:
        try:
            rs.SelectObject(oid)
        except Exception:
            pass
else:
    rs.Command("_SelAll", False)

_ok = False
_error = None
_used_fallback = False
_version_applied = False

try:
    opts = Rhino.FileIO.FileDwgWriteOptions()
    _enum_name = _VERSION_MAP.get(str(_mcp_autocad_version), "Acad2018")
    _version_enum = getattr(Rhino.FileIO.FileDwgWriteOptions.AutocadVersion, _enum_name, None)
    if _version_enum is not None:
        opts.Version = _version_enum
        _version_applied = True
    if _mcp_object_ids:
        # ExportSelected honours the selection made above.
        _ok = bool(doc.ExportSelected(_mcp_path, opts.ToDictionary()))
    else:
        _ok = bool(Rhino.FileIO.FileDwg.Write(_mcp_path, doc, opts))
except Exception as _ex:
    _error = str(_ex)
    _version_applied = False

if not _ok:
    _version_applied = False
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
        _used_fallback = _ok
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "DWG" if _mcp_path.lower().endswith(".dwg") else "DXF",
    "ok": _ok,
    "requested": {"autocad_version": _mcp_autocad_version, "export_layout": _mcp_export_layout},
    "applied": {"autocad_version": _mcp_autocad_version} if _version_applied else {},
    "note": "FileDwgWriteOptions has no layout-export option; export_layout was not applied.",
}
if _used_fallback:
    result["note"] = (
        "Exported via the _-Export command using Rhino's current DWG/DXF "
        "settings; the requested autocad_version and export_layout were not applied."
    )
if _error and not _ok:
    result["error"] = _error
'''

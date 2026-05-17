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
        """
        Export selected objects (or all objects) to a STEP file.

        ``path`` must end in ``.step`` or ``.stp``.
        ``schema`` controls the STEP application protocol: ``"AP203"``,
        ``"AP214"`` (default), or ``"AP242"``.
        ``tolerance`` is the export tolerance in document units.
        ``object_ids`` restricts the export to those object GUIDs; when
        ``None`` all visible objects are exported.
        """
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
            json.dumps(object_ids),
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
        """
        Export selected objects (or all objects) to an IGES file.

        ``path`` must end in ``.igs`` or ``.iges``.
        ``tolerance`` is the export tolerance in document units.
        ``trim_type`` controls how trimmed surfaces are written: ``"parametric"``
        (default, more compact) or ``"3d"`` (explicit 3-D trim curves).
        ``object_ids`` restricts the export to those object GUIDs; when
        ``None`` all visible objects are exported.
        """
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
            json.dumps(object_ids),
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
        """
        Export selected objects (or all objects) to a DWG or DXF file.

        ``path`` must end in ``.dwg`` or ``.dxf``.
        ``autocad_version`` selects the AutoCAD file format version: ``"2004"``,
        ``"2007"``, ``"2010"``, ``"2013"``, or ``"2018"`` (default).
        ``export_layout`` — when ``False`` (default) objects are written to
        model space; when ``True`` the active layout / paper space is exported.
        ``object_ids`` restricts the export to those object GUIDs; when
        ``None`` all visible objects are exported.
        """
        code = (
            "_mcp_path = {}\n"
            "_mcp_autocad_version = {}\n"
            "_mcp_export_layout = {}\n"
            "_mcp_object_ids = {}\n"
            "{}"
        ).format(
            json.dumps(path),
            json.dumps(autocad_version),
            json.dumps(export_layout),
            json.dumps(object_ids),
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

try:
    opts = Rhino.FileIO.FileStepWriteOptions()
    # Map schema string to the enum when the attribute exists
    _schema_map = {
        "AP203": "Ap203",
        "AP214": "Ap214",
        "AP242": "Ap242",
    }
    _attr = _schema_map.get(_mcp_schema.upper())
    if _attr and hasattr(opts, "Schema"):
        _schema_enum = getattr(Rhino.FileIO.FileStepWriteOptions.StepSchema, _attr, None)
        if _schema_enum is not None:
            opts.Schema = _schema_enum
    if hasattr(opts, "Tolerance"):
        opts.Tolerance = _mcp_tolerance
    _ok = bool(Rhino.FileIO.RhinoFile.Write(_mcp_path, opts))
except Exception as _ex:
    _error = str(_ex)
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "STEP",
    "schema": _mcp_schema,
    "tolerance": _mcp_tolerance,
    "ok": _ok,
}
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

try:
    opts = Rhino.FileIO.FileIgesWriteOptions()
    if hasattr(opts, "Tolerance"):
        opts.Tolerance = _mcp_tolerance
    # trim_type: "parametric" -> parametric (default), "3d" -> 3-D curves
    if _mcp_trim_type.lower() == "3d" and hasattr(opts, "TrimCurveType"):
        _tc = getattr(Rhino.FileIO.FileIgesWriteOptions.IgesTrimCurveType, "Curve3d", None)
        if _tc is not None:
            opts.TrimCurveType = _tc
    _ok = bool(Rhino.FileIO.RhinoFile.Write(_mcp_path, opts))
except Exception as _ex:
    _error = str(_ex)
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "IGES",
    "tolerance": _mcp_tolerance,
    "trim_type": _mcp_trim_type,
    "ok": _ok,
}
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

try:
    opts = Rhino.FileIO.FileAcadWriteOptions()
    _enum_name = _VERSION_MAP.get(str(_mcp_autocad_version), "Acad2018")
    if hasattr(opts, "AcadVersion"):
        _version_enum = getattr(Rhino.FileIO.FileAcadWriteOptions.AcadFileVersion, _enum_name, None)
        if _version_enum is not None:
            opts.AcadVersion = _version_enum
    if hasattr(opts, "ExportLayout"):
        opts.ExportLayout = bool(_mcp_export_layout)
    _ok = bool(Rhino.FileIO.RhinoFile.Write(_mcp_path, opts))
except Exception as _ex:
    _error = str(_ex)
    try:
        _mcp_path_safe = _mcp_path.replace('"', '').replace('\r', '').replace('\n', '')
        _ok = bool(rs.Command('_-Export "{}" _Enter'.format(_mcp_path_safe), False))
    except Exception as _ex2:
        _error = "{} | fallback: {}".format(_error, _ex2)
        _ok = False

rs.UnselectAllObjects()

result = {
    "path": _mcp_path,
    "format": "DWG" if _mcp_path.lower().endswith(".dwg") else "DXF",
    "autocad_version": _mcp_autocad_version,
    "ok": _ok,
}
if _error and not _ok:
    result["error"] = _error
'''

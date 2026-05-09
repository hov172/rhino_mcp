"""
Tools for Rhino document inspection and file operations.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Document Summary", readOnlyHint=True))
    def get_rhino_document_summary(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return document, layer, object, material, and view summary information.
        """
        return rhino.execute_python(_SUMMARY_SCRIPT, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Save Rhino Document", destructiveHint=True))
    def save_rhino_document(path: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Save the active Rhino document. If ``path`` is given, save as that file.
        """
        code = "_mcp_path = {!s}\n{}".format(json.dumps(path), _SAVE_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Enable Viewport Redraw", destructiveHint=True))
    def enable_redraw(
        enable: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Enable or disable viewport redraw.

        Disable redraw before batch operations to prevent flickering and speed
        things up, then re-enable when done.
        """
        code = "__mcp_redraw = {!r}\nimport rhinoscriptsyntax as rs\nrs.EnableRedraw(__mcp_redraw)\nresult = {{'enabled': __mcp_redraw}}".format(enable)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Unit System", destructiveHint=True))
    def set_unit_system(
        unit_system: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the document unit system.

        ``unit_system`` accepts a name string: ``Millimeters``, ``Centimeters``,
        ``Meters``, ``Kilometers``, ``Inches``, ``Feet``, ``Miles``,
        ``Microns``, or ``None``.
        """
        code = "__mcp_units = {!r}\n{}".format(unit_system, _UNITS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export Rhino Document", destructiveHint=True))
    def export_rhino_document(path: str, select_all: bool = True, rhino_id: str | None = None) -> dict[str, object]:
        """
        Export the active Rhino document or current selection to ``path``.

        The file extension controls Rhino's exporter, for example ``.3dm``,
        ``.obj``, ``.stl``, ``.fbx``, ``.step``, ``.iges``, or ``.dwg``.
        """
        command = "_-Export"
        if select_all:
            command = "_SelAll " + command
        command = '{} "{}" _Enter'.format(command, path)
        return rhino.run_command(command, rhino_id=rhino_id)


_UNITS_SCRIPT = r'''
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc
name = __mcp_units.strip().lower()
_MAP = {
    "none": Rhino.UnitSystem.None_,
    "microns": Rhino.UnitSystem.Microns,
    "millimeters": Rhino.UnitSystem.Millimeters,
    "centimeters": Rhino.UnitSystem.Centimeters,
    "meters": Rhino.UnitSystem.Meters,
    "kilometers": Rhino.UnitSystem.Kilometers,
    "microinches": Rhino.UnitSystem.Microinches,
    "mils": Rhino.UnitSystem.Mils,
    "inches": Rhino.UnitSystem.Inches,
    "feet": Rhino.UnitSystem.Feet,
    "miles": Rhino.UnitSystem.Miles,
}
us = _MAP.get(name)
if us is None:
    result = {"ok": False, "error": "Unknown unit system: {}".format(__mcp_units)}
else:
    doc.ModelUnitSystem = us
    result = {"ok": True, "unit_system": doc.ModelUnitSystem.ToString()}
'''


_SUMMARY_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs

doc = Rhino.RhinoDoc.ActiveDoc
objects = []
for obj in doc.Objects:
    if obj.IsDeleted:
        continue
    bbox = obj.Geometry.GetBoundingBox(True)
    objects.append({
        "id": str(obj.Id),
        "name": obj.Name,
        "type": obj.ObjectType.ToString(),
        "layer": doc.Layers[obj.Attributes.LayerIndex].FullPath if obj.Attributes.LayerIndex >= 0 else None,
        "is_hidden": obj.IsHidden,
        "is_locked": obj.IsLocked,
        "bbox_min": [bbox.Min.X, bbox.Min.Y, bbox.Min.Z],
        "bbox_max": [bbox.Max.X, bbox.Max.Y, bbox.Max.Z],
    })

layers = []
for layer in doc.Layers:
    if layer.IsDeleted:
        continue
    layers.append({
        "name": layer.FullPath,
        "visible": layer.IsVisible,
        "locked": layer.IsLocked,
        "color": [layer.Color.R, layer.Color.G, layer.Color.B],
    })

views = [view.ActiveViewport.Name for view in doc.Views]
result = {
    "name": doc.Name,
    "path": doc.Path,
    "object_count": len(objects),
    "objects": objects,
    "layers": layers,
    "materials": [mat.Name for mat in doc.Materials if not mat.IsDeleted],
    "views": views,
    "unit_system": doc.ModelUnitSystem.ToString(),
}
'''

_SAVE_SCRIPT = r'''
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc
if _mcp_path:
    ok = doc.WriteFile(_mcp_path, Rhino.FileIO.FileWriteOptions())
else:
    ok = doc.Save()
result = {"saved": bool(ok), "path": doc.Path}
'''

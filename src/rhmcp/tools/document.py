"""
Tools for Rhino document inspection and file operations.
"""

from __future__ import annotations

import json

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

    @mcp.tool(annotations=ToolAnnotations(title="Normalize Imported Object Materials", destructiveHint=True))
    def normalize_imported_objects(
        layer_names: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Fix display colors on objects imported from 3DS, FBX, OBJ, and similar
        formats whose materials are baked at import time.

        **Why this is needed:** Rhino's 3DS/FBX/OBJ importers stamp every mesh
        with ``MaterialFromObject`` pointing at a source-file material.  Calling
        ``ModifyAttributes`` afterward updates the data structure but does *not*
        invalidate Rhino's display cache for those objects, so the viewport keeps
        showing the original import color regardless of what attributes you set.
        The only reliable fix is to delete each object and re-add its geometry as
        a fresh document object with clean ``ObjectAttributes``
        (``MaterialFromParent``, ``ColorFromLayer``).

        This tool performs that delete-and-readd pass in bulk.  After it runs,
        you can freely set object colors, materials, and layers through the normal
        attribute APIs and they will display correctly.

        :param layer_names: Layer names to normalize.  Pass ``null`` / omit to
            normalize every object in the document.  Use layer full-paths for
            nested layers, e.g. ``"Buildings::Residential"``.
        """
        code = "_mcp_layer_names = {}\n{}".format(
            json.dumps(layer_names), _NORMALIZE_SCRIPT
        )
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

_NORMALIZE_SCRIPT = r'''
import Rhino
import Rhino.Geometry as rg

doc = Rhino.RhinoDoc.ActiveDoc

# Resolve target layer indices.  None means all layers.
if _mcp_layer_names is None:
    target_layer_indices = None  # sentinel: match everything
else:
    target_layer_indices = set()
    for lname in _mcp_layer_names:
        lyr = doc.Layers.FindName(lname)
        if lyr is not None:
            target_layer_indices.add(lyr.Index)

# Snapshot the IDs so we can iterate safely while deleting.
candidates = []
for obj in doc.Objects:
    if obj.IsDeleted:
        continue
    if obj.ObjectType.ToString() == "Light":
        continue
    if target_layer_indices is not None:
        if obj.Attributes.LayerIndex not in target_layer_indices:
            continue
    # Only objects whose material source is baked from import need fixing.
    # MaterialFromObject with an index >= 0 is the tell-tale sign.
    src = obj.Attributes.MaterialSource.ToString()
    if src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0:
        candidates.append((obj.Id, obj.Attributes.LayerIndex))

normalized = 0
skipped = 0

for obj_id, layer_idx in candidates:
    obj = doc.Objects.Find(obj_id)
    if obj is None or obj.IsDeleted:
        skipped += 1
        continue

    geo = obj.Geometry
    otype = obj.ObjectType.ToString()

    # Duplicate the geometry so we have a fresh copy after deletion.
    if otype == "Mesh":
        new_geo = geo.DuplicateMesh()
    else:
        new_geo = geo.Duplicate()

    if new_geo is None:
        skipped += 1
        continue

    # Build clean attributes: inherit color and material from layer.
    oa = Rhino.DocObjects.ObjectAttributes()
    oa.LayerIndex = layer_idx
    oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
    oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromParent
    oa.Name = obj.Attributes.Name or ""

    doc.Objects.Delete(obj_id, True)

    if otype == "Mesh":
        doc.Objects.AddMesh(new_geo, oa)
    elif otype == "Brep":
        doc.Objects.AddBrep(new_geo, oa)
    elif otype == "Surface":
        doc.Objects.AddSurface(new_geo, oa)
    elif otype == "Curve":
        doc.Objects.AddCurve(new_geo, oa)
    elif otype == "Point":
        doc.Objects.AddPoint(new_geo.Location, oa)
    else:
        doc.Objects.Add(new_geo, oa)

    normalized += 1

doc.Views.Redraw()

result = {
    "ok": True,
    "normalized": normalized,
    "skipped": skipped,
    "note": (
        "Objects re-added with MaterialFromParent + ColorFromLayer. "
        "You can now set object colors and materials freely via standard attribute APIs."
    ),
}
'''

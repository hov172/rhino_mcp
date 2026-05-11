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

    @mcp.tool(annotations=ToolAnnotations(title="Import File", destructiveHint=True))
    def import_file(
        path: str,
        normalize_materials: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Import a file into the active Rhino document and immediately fix any
        import-baked material overrides so colors work correctly afterward.

        Supports any format Rhino can open: ``.3ds``, ``.obj``, ``.fbx``,
        ``.stl``, ``.iges``, ``.step``, ``.dxf``, ``.dwg``, ``.3dm``, etc.

        **Why normalize_materials matters:** 3DS, FBX, and OBJ importers stamp
        every mesh with ``MaterialFromObject`` from the source file.  Any
        subsequent attempt to set ``ObjectColor`` or assign a new material via
        ``ModifyAttributes`` will be silently ignored because Rhino's display
        cache retains the import-time material color.  With ``normalize_materials``
        enabled (the default) this tool detects newly added objects with baked
        materials and re-adds them with clean ``ObjectAttributes`` automatically,
        so ``set_object_display_color`` and all other color APIs work immediately
        after import.

        :param path: Absolute path to the file to import.
        :param normalize_materials: When ``True`` (default), automatically
            normalize import-baked materials on newly imported objects.
            Set to ``False`` only if you want to preserve the source-file
            materials for rendering.
        """
        code = "_mcp_import_path = {}\n_mcp_normalize = {!r}\n{}".format(
            json.dumps(path), normalize_materials, _IMPORT_SCRIPT
        )
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Object Display Color", destructiveHint=True))
    def set_object_display_color(
        color: list[int],
        object_ids: list[str] | None = None,
        layer_names: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the display color of objects so it shows correctly in **both**
        Shaded and Rendered viewport modes.

        **Why a dedicated tool is needed:** Rhino's color pipeline has three
        priority levels.  ``ObjectColor`` alone only controls wireframe edges;
        face fill in Shaded mode uses the assigned material's diffuse color
        instead.  Rendered mode always uses the material and ignores
        ``ObjectColor`` entirely.  This tool sets both the object color and a
        matching render material in one call, so the result is consistent
        across all display modes.

        If any targeted object still has an import-baked material
        (``MaterialFromObject`` from a 3DS/FBX/OBJ import), this tool
        normalizes it automatically before applying the color — no need to
        call ``normalize_imported_objects`` first.

        :param color: RGB values as ``[R, G, B]`` integers 0–255.
        :param object_ids: GUIDs of specific objects to recolor.  Pass
            ``null`` to target by layer instead.
        :param layer_names: Layer names whose objects should be recolored.
            Ignored when ``object_ids`` is provided.  Pass ``null`` for both
            parameters to recolor every object in the document.
        """
        code = (
            "_mcp_color = {}\n"
            "_mcp_object_ids = {}\n"
            "_mcp_layer_names = {}\n"
            "{}"
        ).format(
            json.dumps(color),
            json.dumps(object_ids),
            json.dumps(layer_names),
            _SET_COLOR_SCRIPT,
        )
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

# Detect objects whose material was baked at import time.
# These objects will ignore ObjectColor changes until normalized.
baked_ids = []
for obj in doc.Objects:
    if obj.IsDeleted:
        continue
    if (obj.Attributes.MaterialSource.ToString() == "MaterialFromObject"
            and obj.Attributes.MaterialIndex >= 0):
        baked_ids.append(str(obj.Id))

warnings = []
if baked_ids:
    warnings.append(
        "{} object(s) have import-baked materials (MaterialFromObject). "
        "ObjectColor changes will NOT display correctly until you call "
        "normalize_imported_objects() to fix them.".format(len(baked_ids))
    )

result = {
    "name": doc.Name,
    "path": doc.Path,
    "object_count": len(objects),
    "objects": objects,
    "layers": layers,
    "materials": [mat.Name for mat in doc.Materials if not mat.IsDeleted],
    "views": views,
    "unit_system": doc.ModelUnitSystem.ToString(),
    "baked_import_material_count": len(baked_ids),
    "warnings": warnings,
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

_IMPORT_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg

doc = Rhino.RhinoDoc.ActiveDoc

# Snapshot IDs that exist before the import.
ids_before = set(str(o.Id) for o in doc.Objects if not o.IsDeleted)

# Run the import via Rhino command; False = don't echo to command line.
cmd = '_-Import "{}" _Enter'.format(_mcp_import_path)
ok = rs.Command(cmd, False)

if not ok:
    result = {"ok": False, "error": "Import command failed for: {}".format(_mcp_import_path)}
else:
    # Identify objects that were just added.
    new_objs = [o for o in doc.Objects
                if not o.IsDeleted and str(o.Id) not in ids_before]

    normalized = 0
    skipped = 0

    if _mcp_normalize:
        # Cache of color_key -> material_index to share one material per unique RGB.
        color_mat_cache = {}

        for obj in new_objs:
            if obj.ObjectType.ToString() == "Light":
                continue
            src = obj.Attributes.MaterialSource.ToString()
            if not (src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0):
                continue  # already clean

            geo = obj.Geometry
            otype = obj.ObjectType.ToString()
            layer_idx = obj.Attributes.LayerIndex
            obj_name = obj.Attributes.Name or ""

            # Read the original material's diffuse color BEFORE deleting.
            # This is what the online viewer sees — we preserve it so the
            # imported scene looks the same as the source file intended.
            orig_mat = doc.Materials[obj.Attributes.MaterialIndex]
            dc = orig_mat.DiffuseColor
            color_key = (dc.R, dc.G, dc.B)

            # Find or create a clean MCP_Color material for this RGB so it
            # works in both Shaded and Rendered mode (not just wireframe).
            if color_key not in color_mat_cache:
                mat_name = "MCP_Color_{:02X}{:02X}{:02X}".format(*color_key)
                mat_idx = -1
                for i, m in enumerate(doc.Materials):
                    if not m.IsDeleted and m.Name == mat_name:
                        mat_idx = i
                        break
                if mat_idx == -1:
                    mat_idx = doc.Materials.Add()
                    new_mat = doc.Materials[mat_idx]
                    new_mat.Name = mat_name
                    new_mat.DiffuseColor = dc
                    new_mat.CommitChanges()
                color_mat_cache[color_key] = mat_idx
            clean_mat_idx = color_mat_cache[color_key]

            new_geo = geo.DuplicateMesh() if otype == "Mesh" else geo.Duplicate()
            if new_geo is None:
                skipped += 1
                continue

            doc.Objects.Delete(obj.Id, True)

            oa = Rhino.DocObjects.ObjectAttributes()
            oa.LayerIndex = layer_idx
            oa.Name = obj_name
            oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            oa.ObjectColor = dc
            oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
            oa.MaterialIndex = clean_mat_idx

            if otype == "Mesh":
                doc.Objects.AddMesh(new_geo, oa)
            elif otype == "Brep":
                doc.Objects.AddBrep(new_geo, oa)
            elif otype == "Surface":
                doc.Objects.AddSurface(new_geo, oa)
            elif otype == "Curve":
                doc.Objects.AddCurve(new_geo, oa)
            else:
                doc.Objects.Add(new_geo, oa)

            normalized += 1

    doc.Views.Redraw()

    result = {
        "ok": True,
        "path": _mcp_import_path,
        "objects_imported": len(new_objs),
        "materials_normalized": normalized,
        "skipped": skipped,
        "normalize_materials": _mcp_normalize,
    }
'''

_SET_COLOR_SCRIPT = r'''
import Rhino
import Rhino.Geometry as rg
import System

doc = Rhino.RhinoDoc.ActiveDoc
r_val, g_val, b_val = int(_mcp_color[0]), int(_mcp_color[1]), int(_mcp_color[2])
target_color = System.Drawing.Color.FromArgb(r_val, g_val, b_val)

# ── Find or create a shared render material for this exact RGB ────────────────
mat_name = "MCP_Color_{:02X}{:02X}{:02X}".format(r_val, g_val, b_val)
mat_idx = -1
for i, m in enumerate(doc.Materials):
    if not m.IsDeleted and m.Name == mat_name:
        mat_idx = i
        break

if mat_idx == -1:
    mat_idx = doc.Materials.Add()
    mat = doc.Materials[mat_idx]
    mat.Name = mat_name
    mat.DiffuseColor = target_color
    mat.CommitChanges()

# ── Resolve which objects to target ──────────────────────────────────────────
import System as _Sys

def _collect_targets():
    if _mcp_object_ids is not None:
        ids = set()
        for s in _mcp_object_ids:
            try:
                ids.add(_Sys.Guid(s))
            except Exception:
                pass
        return [obj for obj in doc.Objects
                if not obj.IsDeleted and obj.Id in ids]

    if _mcp_layer_names is not None:
        idxs = set()
        for lname in _mcp_layer_names:
            lyr = doc.Layers.FindName(lname)
            if lyr is not None:
                idxs.add(lyr.Index)
        return [obj for obj in doc.Objects
                if not obj.IsDeleted
                and obj.Attributes.LayerIndex in idxs]

    return [obj for obj in doc.Objects if not obj.IsDeleted]

targets = _collect_targets()

# ── Apply color, normalizing any import-baked objects first ──────────────────
normalized = 0
colored = 0

for obj in targets:
    if obj.ObjectType.ToString() == "Light":
        continue

    src = obj.Attributes.MaterialSource.ToString()
    baked = (src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0
             and doc.Materials[obj.Attributes.MaterialIndex].Name != mat_name)

    if baked:
        # Must delete + readd to bust the display cache from the importer.
        geo = obj.Geometry
        otype = obj.ObjectType.ToString()
        layer_idx = obj.Attributes.LayerIndex
        obj_name = obj.Attributes.Name or ""

        new_geo = geo.DuplicateMesh() if otype == "Mesh" else geo.Duplicate()
        if new_geo is None:
            continue

        doc.Objects.Delete(obj.Id, True)

        oa = Rhino.DocObjects.ObjectAttributes()
        oa.LayerIndex = layer_idx
        oa.Name = obj_name
        oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        oa.ObjectColor = target_color
        oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        oa.MaterialIndex = mat_idx

        if otype == "Mesh":
            doc.Objects.AddMesh(new_geo, oa)
        elif otype == "Brep":
            doc.Objects.AddBrep(new_geo, oa)
        elif otype == "Surface":
            doc.Objects.AddSurface(new_geo, oa)
        elif otype == "Curve":
            doc.Objects.AddCurve(new_geo, oa)
        else:
            doc.Objects.Add(new_geo, oa)

        normalized += 1
        colored += 1
    else:
        attr = obj.Attributes.Duplicate()
        attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        attr.ObjectColor = target_color
        attr.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        attr.MaterialIndex = mat_idx
        doc.Objects.ModifyAttributes(obj, attr, True)
        colored += 1

doc.Views.Redraw()

result = {
    "ok": True,
    "colored": colored,
    "auto_normalized": normalized,
    "material_name": mat_name,
    "material_index": mat_idx,
    "color_rgb": [r_val, g_val, b_val],
}
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
color_mat_cache = {}

for obj_id, layer_idx in candidates:
    obj = doc.Objects.Find(obj_id)
    if obj is None or obj.IsDeleted:
        skipped += 1
        continue

    geo = obj.Geometry
    otype = obj.ObjectType.ToString()

    # Preserve the original diffuse color from the baked material so the
    # scene looks the same as in the source file / online viewers.
    orig_mat = doc.Materials[obj.Attributes.MaterialIndex]
    dc = orig_mat.DiffuseColor
    color_key = (dc.R, dc.G, dc.B)

    if color_key not in color_mat_cache:
        mat_name = "MCP_Color_{:02X}{:02X}{:02X}".format(*color_key)
        mat_idx = -1
        for i, m in enumerate(doc.Materials):
            if not m.IsDeleted and m.Name == mat_name:
                mat_idx = i
                break
        if mat_idx == -1:
            mat_idx = doc.Materials.Add()
            new_mat = doc.Materials[mat_idx]
            new_mat.Name = mat_name
            new_mat.DiffuseColor = dc
            new_mat.CommitChanges()
        color_mat_cache[color_key] = mat_idx
    clean_mat_idx = color_mat_cache[color_key]

    if otype == "Mesh":
        new_geo = geo.DuplicateMesh()
    else:
        new_geo = geo.Duplicate()

    if new_geo is None:
        skipped += 1
        continue

    oa = Rhino.DocObjects.ObjectAttributes()
    oa.LayerIndex = layer_idx
    oa.Name = obj.Attributes.Name or ""
    oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
    oa.ObjectColor = dc
    oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
    oa.MaterialIndex = clean_mat_idx

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
    "unique_colors_preserved": len(color_mat_cache),
    "note": (
        "Original material colors preserved as MCP_Color materials. "
        "Colors now display correctly in Shaded and Rendered modes. "
        "Use set_object_display_color to change colors if needed."
    ),
}
'''

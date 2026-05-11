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
        show_textures_in_viewport: bool = False,
        post_import_display: str = "auto",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Import a file into the active Rhino document and immediately fix any
        import-baked material overrides so colors and textures work correctly.
        Viewport display mode, background, and grid are configured automatically
        based on the file type so the result looks correct on the first import.

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

        **Texture handling:** When texture image files exist alongside the source
        file (or in ``textures/``, ``maps/``, ``tex/``, ``images/`` subdirs),
        they are automatically resolved and applied to the new clean materials.
        Diffuse color, specular, shine, transparency, bump maps, and bitmap
        textures are all preserved from the original materials.  Textures only
        display in ``Rendered`` viewport mode — set ``show_textures_in_viewport``
        to ``True`` to switch automatically.

        **Automatic display presets (post_import_display="auto"):**

        - ``dwg`` / ``dxf`` / ``svg`` / ``ai`` / ``pdf`` → Wireframe mode,
          black background, grid and axes hidden, black/near-black objects and
          layers flipped to white so AutoCAD layer colours are visible.
        - ``fbx`` / ``obj`` / ``3ds`` / ``stl`` / ``3mf`` / ``ply`` → Shaded mode.
        - ``iges`` / ``igs`` / ``step`` / ``stp`` / ``3dm`` / ``skp`` → Shaded mode.
        - All presets zoom to extents automatically.

        :param path: Absolute path to the file to import.
        :param normalize_materials: When ``True`` (default), automatically
            normalize import-baked materials on newly imported objects.
            Set to ``False`` only if you want to keep raw importer state.
        :param show_textures_in_viewport: Switch the active viewport to
            ``Rendered`` mode after import so texture maps are visible.
            Only meaningful when texture files are present alongside the source.
        :param post_import_display: Display preset applied after import.
            ``"auto"`` (default) picks the preset from the file extension.
            Pass ``"wireframe_dark"``, ``"shaded"``, ``"rendered"``, or
            ``"none"`` to override.
        """
        code = (
            "_mcp_import_path = {}\n"
            "_mcp_normalize = {!r}\n"
            "_mcp_show_textures = {!r}\n"
            "_mcp_display_preset = {!r}\n"
            "{}"
        ).format(
            json.dumps(path),
            normalize_materials,
            show_textures_in_viewport,
            post_import_display,
            _IMPORT_SCRIPT,
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
            "None" if object_ids is None else json.dumps(object_ids),
            "None" if layer_names is None else json.dumps(layer_names),
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
            "None" if layer_names is None else json.dumps(layer_names), _NORMALIZE_SCRIPT
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
# Exclude MCP_ materials — those were already normalized by this tool.
baked_ids = []
for obj in doc.Objects:
    if obj.IsDeleted:
        continue
    if (obj.Attributes.MaterialSource.ToString() == "MaterialFromObject"
            and obj.Attributes.MaterialIndex >= 0):
        mat = doc.Materials[obj.Attributes.MaterialIndex]
        if not mat.IsDeleted and not mat.Name.startswith("MCP_"):
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
import os
import re
import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import System
import System.Drawing

doc = Rhino.RhinoDoc.ActiveDoc

ids_before = set(str(o.Id) for o in doc.Objects if not o.IsDeleted)
cmd = '_-Import "{}" _Enter'.format(_mcp_import_path)
ok = rs.Command(cmd, False)

if not ok:
    result = {"ok": False, "error": "Import command failed for: {}".format(_mcp_import_path)}
else:
    new_objs = [o for o in doc.Objects
                if not o.IsDeleted and str(o.Id) not in ids_before]
    normalized = 0
    skipped = 0
    textures_applied = 0

    if _mcp_normalize:
        _src_dir = os.path.dirname(_mcp_import_path) if _mcp_import_path else ""
        _search_dirs = [_src_dir] + [os.path.join(_src_dir, s)
                        for s in ("textures", "maps", "tex", "images")]

        def _resolve_tex(raw):
            if not raw:
                return ""
            if os.path.isfile(raw):
                return raw
            base = os.path.basename(raw)
            if not base:
                return ""
            for d in _search_dirs:
                c = os.path.join(d, base)
                if os.path.isfile(c):
                    return c
            return ""

        mat_cache = {}

        for obj in new_objs:
            if obj.ObjectType.ToString() == "Light":
                continue
            src = obj.Attributes.MaterialSource.ToString()
            if not (src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0):
                continue

            geo = obj.Geometry
            otype = obj.ObjectType.ToString()
            layer_idx = obj.Attributes.LayerIndex
            obj_name = obj.Attributes.Name or ""

            orig_mat = doc.Materials[obj.Attributes.MaterialIndex]
            dc = orig_mat.DiffuseColor
            shine = orig_mat.Shine
            transparency = orig_mat.Transparency
            specular = orig_mat.SpecularColor
            emission = orig_mat.EmissionColor

            _bt = orig_mat.GetBitmapTexture()
            _nt = orig_mat.GetBumpTexture()
            _et = orig_mat.GetEnvironmentTexture()
            _tt = orig_mat.GetTransparencyTexture()
            bitmap_path = _resolve_tex(_bt.FileReference.FullPath if _bt is not None else "")
            bump_path   = _resolve_tex(_nt.FileReference.FullPath if _nt is not None else "")
            env_path    = _resolve_tex(_et.FileReference.FullPath if _et is not None else "")
            trans_path  = _resolve_tex(_tt.FileReference.FullPath if _tt is not None else "")

            mat_key = (dc.R, dc.G, dc.B, bitmap_path, bump_path, env_path, trans_path)

            if mat_key not in mat_cache:
                _hex = "%02X%02X%02X" % (int(dc.R), int(dc.G), int(dc.B))
                if bitmap_path:
                    _bname = re.sub(r'[^A-Za-z0-9]', '_',
                                    os.path.splitext(os.path.basename(bitmap_path))[0])[:14]
                    mat_name = "MCP_Tex_{}_{}".format(_hex, _bname)
                else:
                    mat_name = "MCP_Color_{}".format(_hex)

                mat_idx = -1
                for i, m in enumerate(doc.Materials):
                    if not m.IsDeleted and m.Name == mat_name:
                        mat_idx = i
                        break
                if mat_idx == -1:
                    mat_idx = doc.Materials.Add()
                    nm = doc.Materials[mat_idx]
                    nm.Name = mat_name
                    nm.DiffuseColor = dc
                    nm.Shine = shine
                    nm.Transparency = transparency
                    nm.SpecularColor = specular
                    nm.EmissionColor = emission
                    for _tex_fn, _tex_path in (
                        ("SetBitmapTexture", bitmap_path),
                        ("SetBumpTexture",   bump_path),
                        ("SetEnvironmentTexture", env_path),
                        ("SetTransparencyTexture", trans_path),
                    ):
                        if _tex_path:
                            try:
                                getattr(nm, _tex_fn)(_tex_path)
                            except Exception:
                                pass
                    nm.CommitChanges()
                mat_cache[mat_key] = mat_idx
            clean_mat_idx = mat_cache[mat_key]

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
            if bitmap_path:
                textures_applied += 1

    # ── Post-import display setup ─────────────────────────────────────────────
    _ext = os.path.splitext(_mcp_import_path)[1].lower().lstrip(".")
    _WIREFRAME_DARK = {"dwg", "dxf", "svg", "ai", "pdf", "eps"}
    _SHADED = {
        "fbx", "obj", "3ds", "stl", "3mf", "ply", "wrl", "vrml",
        "iges", "igs", "step", "stp", "3dm", "skp", "rhp",
    }

    if _mcp_display_preset == "auto":
        _preset = ("wireframe_dark" if _ext in _WIREFRAME_DARK
                   else "shaded" if _ext in _SHADED
                   else None)
    elif _mcp_display_preset in ("none", ""):
        _preset = None
    else:
        _preset = _mcp_display_preset

    # Textures found and explicitly requested → force Rendered
    if _mcp_show_textures and textures_applied > 0:
        _preset = "rendered"

    _display_applied = None
    _flipped_layers = 0
    _flipped_objects = 0

    if _preset == "wireframe_dark":
        # 1. Set Wireframe display mode background to solid black
        _wire_dm = Rhino.Display.DisplayModeDescription.FindByName("Wireframe")
        if _wire_dm:
            _wa = _wire_dm.DisplayAttributes
            _FM = Rhino.Display.DisplayPipelineAttributes.FrameBufferFillMode
            _wa.SetFill(
                System.Drawing.Color.Black,
                System.Drawing.Color.Black,
                System.Drawing.Color.Black,
                System.Drawing.Color.Black,
            )
            _wa.FillMode = _FM.SolidColor
            Rhino.Display.DisplayModeDescription.UpdateDisplayMode(_wire_dm)

        # 2. Switch all viewports to Wireframe, hide grid and axes
        _wm = Rhino.Display.DisplayModeDescription.FindByName("Wireframe")
        for _view in doc.Views:
            _vp = _view.ActiveViewport
            if _wm:
                _vp.DisplayMode = _wm
            _vp.ConstructionAxesVisible = False
            _vp.ConstructionGridVisible = False
            _vp.WorldAxesVisible = False

        # 3. Flip black/near-black layer colours → white
        #    AutoCAD colour 7 (black/white) imports as (0,0,0) on a light theme.
        for _layer in doc.Layers:
            if _layer.IsDeleted:
                continue
            _lc = _layer.Color
            _luma = int(_lc.R) * 299 + int(_lc.G) * 587 + int(_lc.B) * 114
            if _luma < 30000:
                _layer.Color = System.Drawing.Color.White
                _layer.CommitChanges()
                _flipped_layers += 1

        # 4. Flip black/near-black per-object colour overrides → white
        _ids_after = set(str(o.Id) for o in doc.Objects if not o.IsDeleted)
        _new_ids = _ids_after - ids_before
        for _nid in _new_ids:
            try:
                _no = doc.Objects.Find(System.Guid(_nid))
            except Exception:
                continue
            if _no is None or _no.IsDeleted:
                continue
            if _no.Attributes.ColorSource.ToString() != "ColorFromObject":
                continue
            _oc = _no.Attributes.ObjectColor
            _luma = int(_oc.R) * 299 + int(_oc.G) * 587 + int(_oc.B) * 114
            if _luma < 30000:
                _oa2 = _no.Attributes.Duplicate()
                _oa2.ObjectColor = System.Drawing.Color.White
                doc.Objects.ModifyAttributes(_no, _oa2, True)
                _flipped_objects += 1

        _display_applied = "wireframe_dark"

    elif _preset in ("shaded", "rendered"):
        _mode_name = "Rendered" if _preset == "rendered" else "Shaded"
        _dm2 = Rhino.Display.DisplayModeDescription.FindByName(_mode_name)
        if _dm2:
            for _view in doc.Views:
                _view.ActiveViewport.DisplayMode = _dm2
        _display_applied = _preset

    if _preset:
        Rhino.RhinoApp.RunScript("_ZoomExtentsAll", False)

    doc.Views.Redraw()

    _res = {
        "ok": True,
        "path": _mcp_import_path,
        "objects_imported": len(new_objs),
        "materials_normalized": normalized,
        "textures_applied": textures_applied,
        "skipped": skipped,
    }
    if _display_applied:
        _res["display_preset"] = _display_applied
        if _preset == "wireframe_dark":
            _res["flipped_layers"] = _flipped_layers
            _res["flipped_objects"] = _flipped_objects
    if textures_applied > 0 and not _mcp_show_textures:
        _res["tip"] = "Switch viewport to Rendered mode to see texture maps."
    result = _res
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
    _cur_mat_name = (doc.Materials[obj.Attributes.MaterialIndex].Name
                     if src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0
                     else "")
    # Only truly import-baked (non-MCP_) materials need delete+readd to bust
    # the display cache.  Already-normalized MCP_ objects use ModifyAttributes.
    baked = (src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0
             and not _cur_mat_name.startswith("MCP_"))

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
import os
import re
import Rhino
import Rhino.Geometry as rg

doc = Rhino.RhinoDoc.ActiveDoc

# Build texture search dirs from the open document's location (if saved).
_doc_dir = os.path.dirname(doc.Path) if doc.Path else ""
_search_dirs = ([_doc_dir] + [os.path.join(_doc_dir, s)
                for s in ("textures", "maps", "tex", "images")]
                if _doc_dir else [])

def _resolve_tex(raw):
    if not raw:
        return ""
    if os.path.isfile(raw):
        return raw
    base = os.path.basename(raw)
    if not base:
        return ""
    for d in _search_dirs:
        c = os.path.join(d, base)
        if os.path.isfile(c):
            return c
    return ""

# Resolve target layer indices.  None means all layers.
if _mcp_layer_names is None:
    target_layer_indices = None
else:
    target_layer_indices = set()
    for lname in _mcp_layer_names:
        lyr = doc.Layers.FindName(lname)
        if lyr is not None:
            target_layer_indices.add(lyr.Index)

candidates = []
for obj in doc.Objects:
    if obj.IsDeleted or obj.ObjectType.ToString() == "Light":
        continue
    if target_layer_indices is not None:
        if obj.Attributes.LayerIndex not in target_layer_indices:
            continue
    src = obj.Attributes.MaterialSource.ToString()
    if src == "MaterialFromObject" and obj.Attributes.MaterialIndex >= 0:
        mat = doc.Materials[obj.Attributes.MaterialIndex]
        if not mat.IsDeleted and not mat.Name.startswith("MCP_"):
            candidates.append((obj.Id, obj.Attributes.LayerIndex))

normalized = 0
skipped = 0
textures_applied = 0
mat_cache = {}  # (R,G,B,bitmap,bump) -> mat_idx

for obj_id, layer_idx in candidates:
    obj = doc.Objects.Find(obj_id)
    if obj is None or obj.IsDeleted:
        skipped += 1
        continue

    geo = obj.Geometry
    otype = obj.ObjectType.ToString()

    orig_mat = doc.Materials[obj.Attributes.MaterialIndex]
    dc = orig_mat.DiffuseColor
    shine = orig_mat.Shine
    transparency = orig_mat.Transparency
    specular = orig_mat.SpecularColor
    emission = orig_mat.EmissionColor

    _bt = orig_mat.GetBitmapTexture()
    _nt = orig_mat.GetBumpTexture()
    _et = orig_mat.GetEnvironmentTexture()
    _tt = orig_mat.GetTransparencyTexture()
    bitmap_path = _resolve_tex(_bt.FileReference.FullPath if _bt is not None else "")
    bump_path   = _resolve_tex(_nt.FileReference.FullPath if _nt is not None else "")
    env_path    = _resolve_tex(_et.FileReference.FullPath if _et is not None else "")
    trans_path  = _resolve_tex(_tt.FileReference.FullPath if _tt is not None else "")

    mat_key = (dc.R, dc.G, dc.B, bitmap_path, bump_path, env_path, trans_path)

    if mat_key not in mat_cache:
        _hex = "%02X%02X%02X" % (int(dc.R), int(dc.G), int(dc.B))
        if bitmap_path:
            _bname = re.sub(r'[^A-Za-z0-9]', '_',
                            os.path.splitext(os.path.basename(bitmap_path))[0])[:14]
            mat_name = "MCP_Tex_{}_{}".format(_hex, _bname)
        else:
            mat_name = "MCP_Color_{}".format(_hex)

        mat_idx = -1
        for i, m in enumerate(doc.Materials):
            if not m.IsDeleted and m.Name == mat_name:
                mat_idx = i
                break
        if mat_idx == -1:
            mat_idx = doc.Materials.Add()
            nm = doc.Materials[mat_idx]
            nm.Name = mat_name
            nm.DiffuseColor = dc
            nm.Shine = shine
            nm.Transparency = transparency
            nm.SpecularColor = specular
            nm.EmissionColor = emission
            for _tex_fn, _tex_path in (
                ("SetBitmapTexture", bitmap_path),
                ("SetBumpTexture",   bump_path),
                ("SetEnvironmentTexture", env_path),
                ("SetTransparencyTexture", trans_path),
            ):
                if _tex_path:
                    try:
                        getattr(nm, _tex_fn)(_tex_path)
                    except Exception:
                        pass
            nm.CommitChanges()
        mat_cache[mat_key] = mat_idx
    clean_mat_idx = mat_cache[mat_key]

    new_geo = geo.DuplicateMesh() if otype == "Mesh" else geo.Duplicate()
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
    if bitmap_path:
        textures_applied += 1

doc.Views.Redraw()

_res = {
    "ok": True,
    "normalized": normalized,
    "textures_applied": textures_applied,
    "skipped": skipped,
    "unique_materials": len(mat_cache),
}
if textures_applied > 0:
    _res["tip"] = "Switch viewport to Rendered mode to see texture maps."
result = _res
'''

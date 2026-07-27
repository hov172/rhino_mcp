"""
Tools for selecting, transforming, deleting, and editing Rhino objects.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Objects", readOnlyHint=True))
    def get_rhino_objects(
        filters: dict[str, Any] | None = None,
        logic: str = "and",
        limit: int = 100,
        offset: int = 0,
        include_hidden: bool = False,
        include_geometry: bool = True,
        bbox_filter: list[list[float]] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Return object summaries filtered by id, name, layer, type, or color.

        ``offset`` + ``limit`` enable pagination — check ``has_more`` in the
        response and increment ``offset`` by..."""
        err = validate.positive(limit, "limit") or validate.non_negative(offset, "offset")
        if err: return err
        payload = {
            "filters": filters or {}, "logic": logic, "limit": limit, "offset": offset,
            "include_hidden": include_hidden, "include_geometry": include_geometry,
            "bbox_filter": bbox_filter,
        }
        code = "__mcp_get_objects = {!r}\n{}".format(payload, _GET_OBJECTS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Object Info", readOnlyHint=True))
    def get_rhino_object_info(
        object_id: str | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Return detailed information for one object, including user text and groups.

        Pass ``object_id`` to look up by GUID, or ``name`` to look up by exact
        object name (returns the first..."""
        if object_id is not None:
            err = validate.guid(object_id, "object_id")
            if err:
                return err
        payload = {"object_id": object_id, "name": name}
        code = "__mcp_object_info = {!r}\n{}".format(payload, _OBJECT_INFO_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Selected Rhino Objects", readOnlyHint=True))
    def get_selected_rhino_objects(
        limit: int = 100,
        include_attributes: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Return summaries for the current Rhino selection.

        Set ``include_attributes=True`` to include each object's user text
        key-value pairs in the response (equivalent to calling..."""
        payload = {"limit": limit, "include_attributes": include_attributes}
        code = "__mcp_selected = {!r}\n{}".format(payload, _SELECTED_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select Rhino Objects", destructiveHint=True))
    def select_rhino_objects(
        filters: dict[str, Any],
        logic: str = "and",
        deselect: bool = False,
        limit: int | None = None,
        color_tolerance: int = 0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Select or deselect objects using filters.

        Supported filter keys: ``ids``, ``name_contains``, ``exact_name``,
        ``layer``, ``type``, ``color`` (RGB list), ``user_text`` (``{"key":..."""
        payload = {"filters": filters, "logic": logic, "deselect": deselect, "limit": limit, "color_tolerance": color_tolerance}
        code = "__mcp_select = {!r}\n{}".format(payload, _SELECT_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Transform Rhino Objects", destructiveHint=True))
    def transform_rhino_objects(
        ids: list[str] | None = None,
        selected: bool = True,
        move: list[float] | None = None,
        rotate_degrees: float | None = None,
        rotate_axis: list[float] | None = None,
        rotate_center: list[float] | None = None,
        scale: float | list[float] | None = None,
        scale_origin: list[float] | None = None,
        copy: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Move, rotate, or scale objects by ids or the current selection.
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err:
                return err
        if move is not None:
            err = validate.coordinate(move, "move")
            if err:
                return err
        if rotate_axis is not None:
            err = validate.coordinate(rotate_axis, "rotate_axis")
            if err:
                return err
        if rotate_center is not None:
            err = validate.coordinate(rotate_center, "rotate_center")
            if err:
                return err
        if scale_origin is not None:
            err = validate.coordinate(scale_origin, "scale_origin")
            if err:
                return err
        payload = {
            "ids": ids,
            "selected": selected,
            "move": move,
            "rotate_degrees": rotate_degrees,
            "rotate_axis": rotate_axis,
            "rotate_center": rotate_center,
            "scale": scale,
            "scale_origin": scale_origin,
            "copy": copy,
        }
        code = "__mcp_transform = {!r}\n{}".format(payload, _TRANSFORM_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Edit Rhino Object Attributes", destructiveHint=True))
    def edit_rhino_object_attributes(
        ids: list[str] | None = None,
        selected: bool = True,
        apply_to_all: bool = False,
        name: str | None = None,
        layer: str | None = None,
        color: list[int] | None = None,
        visible: bool | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Set object name, layer, display color, or visibility for ids or selected objects.

        ``visible=True`` shows hidden objects; ``visible=False`` hides visible ones.
        When ``apply_to_all``..."""
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err:
                return err
        if color is not None:
            err = validate.color(color, "color")
            if err:
                return err
        payload = {"ids": ids, "selected": selected, "apply_to_all": apply_to_all, "name": name, "layer": layer, "color": color, "visible": visible}
        code = "__mcp_attrs = {!r}\n{}".format(payload, _ATTR_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Rhino Objects", destructiveHint=True))
    def delete_rhino_objects(
        ids: list[str] | None = None,
        selected: bool = True,
        delete_all: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete objects by ids, the current selection, or all objects in the document.

        ``delete_all=True`` clears the entire document regardless of ``ids`` or
        ``selected`` — use with care.
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err:
                return err
        payload = {"ids": ids, "selected": selected, "delete_all": delete_all}
        code = "__mcp_delete = {!r}\n{}".format(payload, _DELETE_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select All Objects", destructiveHint=True))
    def select_all_objects(rhino_id: str | None = None) -> dict[str, object]:
        """
        Select all objects in the document.
        """
        code = "__mcp_selop = 'all'\n" + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Deselect All Objects", destructiveHint=True))
    def deselect_all_objects(rhino_id: str | None = None) -> dict[str, object]:
        """
        Deselect all currently selected objects.
        """
        code = "__mcp_selop = 'none'\n" + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Invert Selection", destructiveHint=True))
    def invert_selection(rhino_id: str | None = None) -> dict[str, object]:
        """
        Invert the current selection — selected objects become deselected and
        vice versa.
        """
        code = "__mcp_selop = 'invert'\n" + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select by Object Type", destructiveHint=True))
    def select_by_type(
        object_type: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Select all objects of a given type.

        ``object_type``: ``point``, ``curve``, ``surface``, ``polysurface``,
        ``mesh``, ``text``, ``annotation``, ``light``, or ``block``.
        """
        code = "__mcp_selop = {!r}\n".format({"op": "by_type", "type": object_type}) + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select by Layer", destructiveHint=True))
    def select_by_layer(
        layer_name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Select all objects on a specific layer.
        """
        code = "__mcp_selop = {!r}\n".format({"op": "by_layer", "layer": layer_name}) + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select by Name", destructiveHint=True))
    def select_by_name(
        name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Select all objects whose name matches ``name`` (exact match).
        """
        code = "__mcp_selop = {!r}\n".format({"op": "by_name", "name": name}) + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Selected Objects", destructiveHint=True))
    def delete_selected_objects(rhino_id: str | None = None) -> dict[str, object]:
        """
        Delete all currently selected objects.
        """
        code = "__mcp_selop = 'delete_selected'\n" + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Last Created Objects", readOnlyHint=True))
    def get_last_created_objects(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return the GUIDs of the most recently added objects in the document.
        """
        code = "__mcp_selop = 'last_created'\n" + _SEL_OPS_SCRIPT
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Align Geometry to Point", destructiveHint=True))
    def align_geometry_to_point(
        source_point: list[float],
        target_point: list[float],
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Move objects so that source_point lands exactly on target_point.

        Useful after tracing a floor plan from a PDF: pick a known reference
        point on the traced geometry (e.g. a column..."""
        # Validate source_point
        if not isinstance(source_point, (list, tuple)) or len(source_point) not in (2, 3):
            return {"ok": False, "error": "source_point must be a list of 2 or 3 numbers"}
        try:
            source_point = [float(v) for v in source_point]
        except (TypeError, ValueError):
            return {"ok": False, "error": "source_point must contain numeric values"}
        if len(source_point) == 2:
            source_point = source_point + [0.0]

        # Validate target_point
        if not isinstance(target_point, (list, tuple)) or len(target_point) not in (2, 3):
            return {"ok": False, "error": "target_point must be a list of 2 or 3 numbers"}
        try:
            target_point = [float(v) for v in target_point]
        except (TypeError, ValueError):
            return {"ok": False, "error": "target_point must contain numeric values"}
        if len(target_point) == 2:
            target_point = target_point + [0.0]

        # Validate object_ids
        if object_ids is not None:
            err = validate.guid_list(object_ids, "object_ids")
            if err:
                return err

        code = (
            "_mcp_source_point = {!r}\n"
            "_mcp_target_point = {!r}\n"
            "_mcp_object_ids = {!r}\n"
            "{}"
        ).format(source_point, target_point, object_ids, _ALIGN_TO_POINT_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SEL_OPS_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

op = __mcp_selop

_TYPE_MAP = {
    "point": rs.filter.point,
    "curve": rs.filter.curve,
    "surface": rs.filter.surface,
    "polysurface": rs.filter.polysurface,
    "mesh": rs.filter.mesh,
    "text": rs.filter.annotation,
    "annotation": rs.filter.annotation,
    "light": rs.filter.light,
    "block": rs.filter.instance,
}

if op == "all":
    ids = rs.AllObjects(select=True) or []
    result = {"selected": [str(i) for i in ids], "count": len(ids)}

elif op == "none":
    rs.UnselectAllObjects()
    result = {"ok": True}

elif op == "invert":
    all_ids  = set(str(o) for o in (rs.AllObjects() or []))
    sel_ids  = set(str(o) for o in (rs.SelectedObjects() or []))
    rs.UnselectAllObjects()
    to_sel = [o for o in (rs.AllObjects() or []) if str(o) not in sel_ids]
    if to_sel: rs.SelectObjects(to_sel)
    result = {"selected": [str(o) for o in to_sel], "count": len(to_sel)}

elif isinstance(op, dict) and op.get("op") == "by_type":
    t    = op["type"].lower()
    filt = _TYPE_MAP.get(t)
    if filt:
        ids = rs.ObjectsByType(filt, select=True) or []
        result = {"selected": [str(i) for i in ids], "count": len(ids)}
    else:
        result = {"ok": False, "error": "Unknown type: {}".format(op["type"])}

elif isinstance(op, dict) and op.get("op") == "by_layer":
    ids = rs.ObjectsByLayer(op["layer"], select=True) or []
    result = {"selected": [str(i) for i in ids], "count": len(ids)}

elif isinstance(op, dict) and op.get("op") == "by_name":
    ids = rs.ObjectsByName(op["name"], select=True) or []
    result = {"selected": [str(i) for i in ids], "count": len(ids)}

elif op == "delete_selected":
    ids = rs.SelectedObjects() or []
    rs.DeleteObjects(ids)
    result = {"deleted": [str(i) for i in ids], "count": len(ids)}

elif op == "last_created":
    doc  = Rhino.RhinoDoc.ActiveDoc
    objs = [o for o in doc.Objects if not o.IsDeleted]
    if objs:
        latest = max(objs, key=lambda o: o.RuntimeSerialNumber)
        result = {"ids": [str(latest.Id)]}
    else:
        result = {"ids": []}
'''


_COMMON = r'''
import math
import rhinoscriptsyntax as rs
import Rhino
import System

def _set_color_with_material(doc, oid, r_val, g_val, b_val):
    """Assign color so it renders correctly in Shaded and Rendered modes.
    For import-baked objects the display cache requires delete+readd."""
    _hex = "{:02X}{:02X}{:02X}".format(r_val, g_val, b_val)
    _mat_name = "MCP_Color_{}".format(_hex)
    _mat_idx = -1
    for _i, _m in enumerate(doc.Materials):
        if not _m.IsDeleted and _m.Name == _mat_name:
            _mat_idx = _i
            break
    if _mat_idx == -1:
        _mat_idx = doc.Materials.Add()
        _nm = doc.Materials[_mat_idx]
        _nm.Name = _mat_name
        _nm.DiffuseColor = System.Drawing.Color.FromArgb(r_val, g_val, b_val)
        _nm.CommitChanges()
    _sys_color = System.Drawing.Color.FromArgb(r_val, g_val, b_val)
    _obj = doc.Objects.FindId(System.Guid(str(oid)))
    if _obj is None:
        return
    _src = _obj.Attributes.MaterialSource.ToString()
    _midx = _obj.Attributes.MaterialIndex
    _baked = (_src == "MaterialFromObject" and _midx >= 0
              and not doc.Materials[_midx].Name.startswith("MCP_"))
    if _baked:
        _geo = _obj.Geometry
        _otype = _obj.ObjectType.ToString()
        _ng = _geo.DuplicateMesh() if _otype == "Mesh" else _geo.Duplicate()
        if _ng is not None:
            _oa = Rhino.DocObjects.ObjectAttributes()
            _oa.LayerIndex = _obj.Attributes.LayerIndex
            _oa.Name = _obj.Attributes.Name or ""
            _oa.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
            _oa.ObjectColor = _sys_color
            _oa.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
            _oa.MaterialIndex = _mat_idx
            doc.Objects.Delete(_obj.Id, True)
            if _otype == "Mesh":
                doc.Objects.AddMesh(_ng, _oa)
            elif _otype == "Brep":
                doc.Objects.AddBrep(_ng, _oa)
            elif _otype == "Surface":
                doc.Objects.AddSurface(_ng, _oa)
            else:
                doc.Objects.Add(_ng, _oa)
    else:
        _attr = _obj.Attributes.Duplicate()
        _attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        _attr.ObjectColor = _sys_color
        _attr.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        _attr.MaterialIndex = _mat_idx
        doc.Objects.ModifyAttributes(_obj, _attr, True)

def _objects(ids, selected):
    if ids:
        return [oid for oid in ids if rs.IsObject(oid)]
    if selected:
        return rs.SelectedObjects() or []
    return []

def _pt(value, default=(0, 0, 0)):
    if value is None:
        value = default
    if len(value) == 2:
        return (value[0], value[1], 0)
    return tuple(value[:3])

def _color(value):
    if value is None:
        return None
    return tuple(int(v) for v in value[:3])

def _summary(oid):
    bbox = rs.BoundingBox(oid) or []
    return {
        "id": str(oid),
        "name": rs.ObjectName(oid),
        "type": str(rs.ObjectType(oid)),
        "layer": rs.ObjectLayer(oid),
        "color": [int(c) for c in rs.ObjectColor(oid)],
        "hidden": rs.IsObjectHidden(oid),
        "locked": rs.IsObjectLocked(oid),
        "bbox": [[p.X, p.Y, p.Z] if hasattr(p, "X") else [p[0], p[1], p[2]] for p in bbox],
    }

def _match_filter(oid, key, expected):
    if key == "ids":
        return str(oid) in {str(item) for item in expected}
    if key == "name_contains":
        return str(expected).lower() in str(rs.ObjectName(oid) or "").lower()
    if key == "exact_name":
        return str(rs.ObjectName(oid) or "") == str(expected)
    if key == "layer":
        return str(rs.ObjectLayer(oid) or "") == str(expected)
    if key == "type":
        return str(expected).lower() in str(rs.ObjectType(oid)).lower()
    if key == "color":
        return tuple(rs.ObjectColor(oid)) == _color(expected)
    if key == "user_text":
        if isinstance(expected, dict):
            for ukey, uval in expected.items():
                if rs.GetUserText(oid, ukey) != str(uval):
                    return False
            return True
        return rs.GetUserText(oid, str(expected)) is not None
    return False

def _user_text_dict(oid):
    keys = rs.GetUserText(oid) or []
    return {k: rs.GetUserText(oid, k) for k in keys}
'''

_GET_OBJECTS_SCRIPT = _COMMON + r'''
filters = __mcp_get_objects.get("filters") or {}
logic = str(__mcp_get_objects.get("logic") or "and").lower()
limit = int(__mcp_get_objects.get("limit") or 100)
offset = int(__mcp_get_objects.get("offset") or 0)
include_hidden = bool(__mcp_get_objects.get("include_hidden", False))
include_geometry = bool(__mcp_get_objects.get("include_geometry", True))
bbox_filter = __mcp_get_objects.get("bbox_filter")

matched = []
for oid in rs.AllObjects() or []:
    if not include_hidden and rs.IsObjectHidden(oid):
        continue
    if bbox_filter is not None:
        bbox = rs.BoundingBox(oid)
        if not bbox:
            continue
        pts = [(p.X, p.Y, p.Z) if hasattr(p, 'X') else tuple(p) for p in bbox]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
        mn, mx = bbox_filter[0], bbox_filter[1]
        if max(xs) < mn[0] or min(xs) > mx[0]: continue
        if max(ys) < mn[1] or min(ys) > mx[1]: continue
        if max(zs) < mn[2] or min(zs) > mx[2]: continue
    if filters:
        tests = [_match_filter(oid, key, expected) for key, expected in filters.items()]
        ok = any(tests) if logic == "or" else all(tests)
        if not ok:
            continue
    matched.append(oid)

total_matching = len(matched)
page = matched[offset:offset + limit]

def _build(oid):
    out = {
        "id": str(oid),
        "name": rs.ObjectName(oid),
        "type": str(rs.ObjectType(oid)),
        "layer": rs.ObjectLayer(oid),
        "color": [int(c) for c in rs.ObjectColor(oid)],
        "hidden": rs.IsObjectHidden(oid),
        "locked": rs.IsObjectLocked(oid),
    }
    if include_geometry:
        bbox = rs.BoundingBox(oid) or []
        out["bbox"] = [[p.X, p.Y, p.Z] if hasattr(p, "X") else [p[0], p[1], p[2]] for p in bbox]
    return out

objects = [_build(oid) for oid in page]
result = {
    "objects": objects,
    "count": len(objects),
    "total_matching": total_matching,
    "offset": offset,
    "has_more": (offset + len(objects)) < total_matching,
}
'''

_OBJECT_INFO_SCRIPT = _COMMON + r'''
oid = __mcp_object_info.get("object_id")
name_lookup = __mcp_object_info.get("name")
if not oid and name_lookup:
    matches = [o for o in (rs.AllObjects() or []) if rs.ObjectName(o) == name_lookup]
    if not matches:
        raise ValueError("No object named: {}".format(name_lookup))
    oid = str(matches[0])
if not oid or not rs.IsObject(oid):
    raise ValueError("Object not found: {}".format(oid))
info = _summary(oid)
info["user_text"] = _user_text_dict(oid)
info["groups"] = rs.ObjectGroups(oid) or []
info["material_index"] = rs.ObjectMaterialIndex(oid)
result = info
'''

_SELECTED_SCRIPT = _COMMON + r'''
limit = int(__mcp_selected.get("limit") or 100)
include_attributes = bool(__mcp_selected.get("include_attributes", False))
selected = rs.SelectedObjects() or []
objects = []
for oid in selected[:limit]:
    obj = _summary(oid)
    if include_attributes:
        obj["user_text"] = _user_text_dict(oid)
    objects.append(obj)
result = {"objects": objects, "count": len(objects)}
'''

_SELECT_SCRIPT = _COMMON + r'''
filters = __mcp_select.get("filters") or {}
logic = str(__mcp_select.get("logic") or "and").lower()
deselect = bool(__mcp_select.get("deselect", False))
limit = __mcp_select.get("limit")
color_tol = int(__mcp_select.get("color_tolerance") or 0)
all_objects = rs.AllObjects() or []

def _match_color_tol(oid, expected):
    if color_tol <= 0:
        return tuple(rs.ObjectColor(oid)) == _color(expected)
    obj_c = tuple(rs.ObjectColor(oid))[:3]
    exp_c = _color(expected)
    return all(abs(a - b) <= color_tol for a, b in zip(obj_c, exp_c))

def _match(oid, key, expected):
    if key == "color":
        return _match_color_tol(oid, expected)
    return _match_filter(oid, key, expected)

matched = []
for oid in all_objects:
    tests = [_match(oid, key, expected) for key, expected in filters.items()]
    ok = any(tests) if logic == "or" else all(tests)
    if ok:
        matched.append(oid)
        if limit and len(matched) >= int(limit):
            break

if deselect:
    if matched:
        rs.UnselectObjects(matched)
else:
    rs.UnselectAllObjects()
    if matched:
        rs.SelectObjects(matched)
result = {"selected": [str(oid) for oid in matched], "count": len(matched), "deselect": deselect}
'''

_TRANSFORM_SCRIPT = _COMMON + r'''
data = __mcp_transform
objects = _objects(data.get("ids"), bool(data.get("selected", True)))
copy = bool(data.get("copy", False))
current = objects

# copy applies to the first operation only: it creates the copies, and the
# remaining operations transform those copies in place (so the returned ids
# are the new copies, transformed once each).
op_copy = copy
if data.get("move") is not None and current:
    moved = rs.CopyObjects(current, _pt(data.get("move"))) if op_copy else rs.MoveObjects(current, _pt(data.get("move")))
    if op_copy and moved:
        op_copy = False
    current = moved or current
if data.get("rotate_degrees") is not None and current:
    axis = _pt(data.get("rotate_axis"), (0, 0, 1))
    center = _pt(data.get("rotate_center"), (0, 0, 0))
    rotated = rs.RotateObjects(current, center, float(data.get("rotate_degrees")), axis, copy=op_copy)
    if op_copy and rotated:
        op_copy = False
    current = rotated or current
if data.get("scale") is not None and current:
    value = data.get("scale")
    factors = (float(value), float(value), float(value)) if isinstance(value, (int, float)) else tuple(float(v) for v in value[:3])
    origin = _pt(data.get("scale_origin"), (0, 0, 0))
    scaled = rs.ScaleObjects(current, origin, factors, copy=op_copy)
    current = scaled or current

rs.Redraw()
result = {"objects": [str(oid) for oid in current], "count": len(current)}
'''

_ATTR_SCRIPT = _COMMON + r'''
data = __mcp_attrs
if __mcp_attrs.get("apply_to_all"):
    objects = rs.AllObjects() or []
else:
    objects = _objects(data.get("ids"), bool(data.get("selected", True)))
layer = data.get("layer")
if layer and not rs.IsLayer(layer):
    rs.AddLayer(layer)
for oid in objects:
    if data.get("name") is not None:
        rs.ObjectName(oid, data.get("name"))
    if layer:
        rs.ObjectLayer(oid, layer)
    if data.get("color") is not None:
        _c = _color(data.get("color"))
        _set_color_with_material(Rhino.RhinoDoc.ActiveDoc, oid, _c[0], _c[1], _c[2])
    if data.get("visible") is True:
        rs.ShowObject(oid)
    elif data.get("visible") is False:
        rs.HideObject(oid)
rs.Redraw()
result = {"objects": [str(oid) for oid in objects], "count": len(objects)}
'''

_DELETE_SCRIPT = _COMMON + r'''
if __mcp_delete.get("delete_all"):
    objects = rs.AllObjects() or []
else:
    objects = _objects(__mcp_delete.get("ids"), bool(__mcp_delete.get("selected", True)))
deleted = rs.DeleteObjects(objects) if objects else 0
rs.Redraw()
result = {"deleted": int(deleted or 0)}
'''

_ALIGN_TO_POINT_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc

src = _mcp_source_point
tgt = _mcp_target_point
dx = tgt[0] - src[0]
dy = tgt[1] - src[1]
dz = tgt[2] - src[2]
translation = (dx, dy, dz)

if _mcp_object_ids is not None:
    ids = _mcp_object_ids
else:
    ids = [str(obj.Id) for obj in doc.Objects if not obj.IsDeleted]

moved = 0
for oid in ids:
    try:
        rs.MoveObject(oid, translation)
        moved += 1
    except Exception:
        pass

result = {
    "ok": True,
    "moved_count": moved,
    "translation": list(translation),
    "source_point": list(src),
    "target_point": list(tgt),
}
'''

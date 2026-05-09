"""
Tools for selecting, transforming, deleting, and editing Rhino objects.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Objects", readOnlyHint=True))
    def get_rhino_objects(
        filters: dict[str, Any] | None = None,
        logic: str = "and",
        limit: int = 100,
        include_hidden: bool = False,
        bbox_filter: list[list[float]] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return object summaries filtered by id, name, layer, type, or color.

        ``bbox_filter`` is an optional spatial bounding-box filter in the form
        ``[[min_x, min_y, min_z], [max_x, max_y, max_z]]``. When provided, only
        objects whose bounding box overlaps or falls within the specified box are
        returned.
        """
        payload = {"filters": filters or {}, "logic": logic, "limit": limit, "include_hidden": include_hidden, "bbox_filter": bbox_filter}
        code = "__mcp_get_objects = {!r}\n{}".format(payload, _GET_OBJECTS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Object Info", readOnlyHint=True))
    def get_rhino_object_info(object_id: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Return detailed information for one object id.
        """
        payload = {"object_id": object_id}
        code = "__mcp_object_info = {!r}\n{}".format(payload, _OBJECT_INFO_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Selected Rhino Objects", readOnlyHint=True))
    def get_selected_rhino_objects(limit: int = 100, rhino_id: str | None = None) -> dict[str, object]:
        """
        Return summaries for the current Rhino selection.
        """
        payload = {"limit": limit}
        code = "__mcp_selected = {!r}\n{}".format(payload, _SELECTED_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select Rhino Objects", destructiveHint=True))
    def select_rhino_objects(filters: dict[str, Any], logic: str = "and", rhino_id: str | None = None) -> dict[str, object]:
        """
        Select objects using filters.

        Supported filters: ids, name_contains, exact_name, layer, type, color.
        ``logic`` can be ``and`` or ``or``.
        """
        payload = {"filters": filters, "logic": logic}
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
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set object name, layer, or display color for ids or selected objects.

        When ``apply_to_all`` is ``True``, the tool targets ALL objects in the
        document regardless of ``ids`` or ``selected``.
        """
        payload = {"ids": ids, "selected": selected, "apply_to_all": apply_to_all, "name": name, "layer": layer, "color": color}
        code = "__mcp_attrs = {!r}\n{}".format(payload, _ATTR_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Rhino Objects", destructiveHint=True))
    def delete_rhino_objects(ids: list[str] | None = None, selected: bool = True, rhino_id: str | None = None) -> dict[str, object]:
        """
        Delete objects by ids or delete the current selection.
        """
        payload = {"ids": ids, "selected": selected}
        code = "__mcp_delete = {!r}\n{}".format(payload, _DELETE_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_COMMON = r'''
import math
import rhinoscriptsyntax as rs
import Rhino

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
    return False
'''

_GET_OBJECTS_SCRIPT = _COMMON + r'''
filters = __mcp_get_objects.get("filters") or {}
logic = str(__mcp_get_objects.get("logic") or "and").lower()
limit = int(__mcp_get_objects.get("limit") or 100)
include_hidden = bool(__mcp_get_objects.get("include_hidden", False))
bbox_filter = __mcp_get_objects.get("bbox_filter")
objects = []
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
    objects.append(_summary(oid))
    if len(objects) >= limit:
        break
result = {"objects": objects, "count": len(objects), "truncated": len(objects) >= limit}
'''

_OBJECT_INFO_SCRIPT = _COMMON + r'''
oid = __mcp_object_info["object_id"]
if not rs.IsObject(oid):
    raise ValueError("Object not found: {}".format(oid))
info = _summary(oid)
info["user_text"] = rs.GetUserText(oid) or []
info["groups"] = rs.ObjectGroups(oid) or []
info["material_index"] = rs.ObjectMaterialIndex(oid)
result = info
'''

_SELECTED_SCRIPT = _COMMON + r'''
limit = int(__mcp_selected.get("limit") or 100)
objects = [_summary(oid) for oid in (rs.SelectedObjects() or [])[:limit]]
result = {"objects": objects, "count": len(objects)}
'''

_SELECT_SCRIPT = _COMMON + r'''
filters = __mcp_select.get("filters") or {}
logic = str(__mcp_select.get("logic") or "and").lower()
all_objects = rs.AllObjects() or []

def _matches(oid, key, expected):
    return _match_filter(oid, key, expected)

matched = []
for oid in all_objects:
    tests = [_matches(oid, key, expected) for key, expected in filters.items()]
    ok = any(tests) if logic == "or" else all(tests)
    if ok:
        matched.append(oid)

rs.UnselectAllObjects()
if matched:
    rs.SelectObjects(matched)
result = {"selected": [str(oid) for oid in matched], "count": len(matched)}
'''

_TRANSFORM_SCRIPT = _COMMON + r'''
data = __mcp_transform
objects = _objects(data.get("ids"), bool(data.get("selected", True)))
copy = bool(data.get("copy", False))
current = objects

if data.get("move") is not None and current:
    moved = rs.CopyObjects(current, _pt(data.get("move"))) if copy else rs.MoveObjects(current, _pt(data.get("move")))
    current = moved or current
if data.get("rotate_degrees") is not None and current:
    axis = _pt(data.get("rotate_axis"), (0, 0, 1))
    center = _pt(data.get("rotate_center"), (0, 0, 0))
    rotated = rs.RotateObjects(current, center, float(data.get("rotate_degrees")), axis, copy=False)
    current = rotated or current
if data.get("scale") is not None and current:
    value = data.get("scale")
    factors = (float(value), float(value), float(value)) if isinstance(value, (int, float)) else tuple(float(v) for v in value[:3])
    origin = _pt(data.get("scale_origin"), (0, 0, 0))
    scaled = rs.ScaleObjects(current, origin, factors, copy=False)
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
        rs.ObjectColor(oid, _color(data.get("color")))
rs.Redraw()
result = {"objects": [str(oid) for oid in objects], "count": len(objects)}
'''

_DELETE_SCRIPT = _COMMON + r'''
objects = _objects(__mcp_delete.get("ids"), bool(__mcp_delete.get("selected", True)))
deleted = rs.DeleteObjects(objects) if objects else 0
rs.Redraw()
result = {"deleted": int(deleted or 0)}
'''

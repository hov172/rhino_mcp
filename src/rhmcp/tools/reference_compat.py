"""
Tool-name compatibility aliases inspired by the public RhinoMCP reference.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Create Object", destructiveHint=True))
    def create_object(
        type: str,
        params: dict[str, Any],
        name: str | None = None,
        color: list[int] | None = None,
        layer: str | None = None,
        translation: list[float] | None = None,
        rotation: list[float] | None = None,
        scale: float | list[float] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reference-compatible alias for creating one object.

        ``rotation`` is a flat ``[rx, ry, rz]`` list of Euler angles in **degrees**
        (X-rotation, Y-rotation, Z-rotation applied in that order around the object
        centre). This matches the C# plugin's ``ApplyEulerRotation`` convention, which
        converts each value with ``RhinoMath.ToRadians()`` internally.  Always pass
        degrees here — passing radians would over-rotate by a factor of ~57x.

        **arc** params — two calling conventions:
          - Center/radius form (C# plugin native): ``center=[x,y,z]``,
            ``radius=<float>``, ``start_angle=<deg, default 0>``,
            ``end_angle=<deg, default 90>``
          - 3-point form: ``start=[x,y,z]``, ``end=[x,y,z]``,
            ``point_on_arc=[x,y,z]``

        **surface** / **surface_from_points** params (C# handler convention):
          ``points=[[x,y,z], ...]`` (flat list, row-major u×v order),
          ``count=[u_count, v_count]``, ``u_degree=<int, default 3>``,
          ``v_degree=<int, default 3>``, ``u_closed=<bool>``,
          ``v_closed=<bool>``
        """
        from rhmcp.tools.geometry import _run_scene

        payload = {
            "type": type,
            "params": params,
            "name": name,
            "color": color,
            "layer": layer,
            "translation": translation,
            "rotation": rotation,
            "scale": scale,
        }
        plugin = _try_plugin("create_object", {key: value for key, value in payload.items() if value is not None})
        if plugin:
            return plugin
        return _run_scene([payload], rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Objects", destructiveHint=True))
    def create_objects(objects: Any, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible alias for creating multiple objects.
        """
        from rhmcp.tools.geometry import _run_scene

        plugin = _try_plugin("create_objects", {"objects": objects})
        if plugin:
            return plugin
        if isinstance(objects, dict):
            items = []
            for key, value in objects.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault("name", str(key))
                    items.append(item)
        else:
            items = objects
        return _run_scene(items, rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Modify Object", destructiveHint=True))
    def modify_object(
        object_id: str | None = None,
        properties: dict[str, Any] | None = None,
        id: str | None = None,
        name: str | None = None,
        new_name: str | None = None,
        new_color: list[int] | None = None,
        translation: list[float] | None = None,
        rotation: list[float] | None = None,
        scale: float | list[float] | None = None,
        visible: bool | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reference-compatible object attribute/transform edit.

        ``rotation`` is a flat ``[rx, ry, rz]`` list of Euler angles in **degrees**
        (X-rotation, Y-rotation, Z-rotation applied in that order around the object
        centre). The C# plugin's ``ApplyTransform`` converts each value internally
        with ``RhinoMath.ToRadians()``.  Always pass degrees here — passing radians
        would over-rotate by a factor of ~57x.
        ``translation`` is a ``[dx, dy, dz]`` offset in model units.
        """
        props = dict(properties or {})
        props.update({key: value for key, value in {
            "id": id or object_id,
            "name": name,
            "new_name": new_name,
            "new_color": new_color,
            "translation": translation,
            "rotation": rotation,
            "scale": scale,
            "visible": visible,
        }.items() if value is not None})
        plugin = _try_plugin("modify_object", props)
        if plugin:
            return plugin
        object_ids = [str(props["id"])] if props.get("id") else []
        return _modify(object_ids, _normalize_modify_props(props), rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Modify Objects", destructiveHint=True))
    def modify_objects(
        object_ids: list[str] | None = None,
        properties: dict[str, Any] | None = None,
        objects: list[dict[str, Any]] | None = None,
        all: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reference-compatible multi-object attribute/transform edit.
        """
        params = {"object_ids": object_ids, "properties": properties, "objects": objects, "all": all}
        plugin = _try_plugin("modify_objects", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return plugin
        if objects:
            results = []
            for obj in objects:
                oid = obj.get("id")
                if oid:
                    results.append(_modify([str(oid)], _normalize_modify_props(obj), rhino_id))
            return {"ok": all_results_ok(results), "results": results}
        return _modify(object_ids or [], _normalize_modify_props(properties or {}), rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Object", destructiveHint=True))
    def delete_object(object_id: str | None = None, id: str | None = None, name: str | None = None, all: bool = False, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible delete by id, name, or all.
        """
        params = {"id": id or object_id, "name": name, "all": all}
        plugin = _try_plugin("delete_object", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return plugin
        code = "__mcp_delete_ref = {!r}\n{}".format(params, _DELETE_REF_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Document Summary", readOnlyHint=True))
    def get_document_summary(rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible alias for document summary.
        """
        from rhmcp.tools.document import _SUMMARY_SCRIPT

        plugin = _try_plugin("get_document_summary", {})
        return plugin or rhino.execute_python(_SUMMARY_SCRIPT, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Object Info", readOnlyHint=True))
    def get_object_info(object_id: str | None = None, id: str | None = None, name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible object info by id or name.
        """
        params = {"id": id or object_id, "name": name}
        plugin = _try_plugin("get_object_info", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return plugin
        code = "__mcp_object_info_ref = {!r}\n{}".format(params, _OBJECT_INFO_REF_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Objects", readOnlyHint=True))
    def get_objects(
        offset: int = 0,
        limit: int = 100,
        layer_filter: str | None = None,
        type_filter: str | None = None,
        bbox_filter: dict[str, Any] | None = None,
        include_geometry: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reference-compatible alias for listing objects.
        """
        params = {
            "offset": offset,
            "limit": limit,
            "layer_filter": layer_filter,
            "type_filter": type_filter,
            "bbox_filter": bbox_filter,
            "include_geometry": include_geometry,
        }
        plugin = _try_plugin("get_objects", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return plugin
        code = "__mcp_get_objects_ref = {!r}\n{}".format(params, _GET_OBJECTS_REF_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Selected Objects Info", readOnlyHint=True))
    def get_selected_objects_info(limit: int = 100, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible alias for current selection info.
        """
        plugin = _try_plugin("get_selected_objects_info", {"limit": limit})
        if plugin:
            return plugin
        code = "__mcp_selected = {'limit': %d}\n%s" % (limit, _SELECTED_REF_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select Objects", destructiveHint=True))
    def select_objects(filters: dict[str, Any], filters_type: str = "and", rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible selection by filters with filters_type `and` or `or`.
        """
        plugin = _try_plugin("select_objects", {"filters": filters, "filters_type": filters_type})
        if plugin:
            return plugin
        from rhmcp.tools.objects import _SELECT_SCRIPT

        code = "__mcp_select = {!s}\n{}".format(__import__("json").dumps({"filters": filters, "logic": filters_type}), _SELECT_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Execute RhinoScript Python Code", destructiveHint=True))
    def execute_rhinoscript_python_code(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible alias for executing Rhino Python.
        """
        plugin = _try_plugin("execute_rhinoscript_python_code", {"code": code})
        return plugin or rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Execute RhinoCommon CSharp Code", destructiveHint=True))
    def execute_rhinocommon_csharp_code(code: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible alias for executing RhinoCommon C#.
        """
        plugin = _try_plugin("execute_rhinocommon_csharp_code", {"code": code})
        return plugin or rhino.execute_script(code, ".cs", rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Capture Viewport", readOnlyHint=True))
    def capture_viewport(
        path: str | None = None,
        viewport: str | None = None,
        width: int = 1200,
        height: int = 900,
        show_grid: bool | None = None,
        show_axes: bool | None = None,
        show_cplane_axes: bool | None = None,
        zoom_to_fit: bool = False,
        rhino_id: str | None = None,
    ) -> list[object]:
        """
        Reference-compatible alias for viewport capture.
        Returns [metadata, Image] so the AI can see the scene inline.
        path is optional; omit for in-memory capture only.
        """
        import base64
        import json
        from mcp.server.fastmcp import Image
        from rhmcp.tools.view import _CAPTURE_SCRIPT

        params = {
            "path": path,
            "viewport": viewport,
            "width": width,
            "height": height,
            "show_grid": show_grid,
            "show_axes": show_axes,
            "show_cplane_axes": show_cplane_axes,
            "zoom_to_fit": zoom_to_fit,
        }
        plugin = _try_plugin("capture_viewport", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return [plugin]

        payload = {"path": path, "width": width, "height": height, "viewport": viewport, "show_grid": show_grid, "show_axes": show_axes, "show_cplane_axes": show_cplane_axes, "zoom_to_fit": zoom_to_fit}
        raw = rhino.execute_python(
            "__mcp_capture = {!s}\n{}".format(json.dumps(payload), _CAPTURE_SCRIPT),
            rhino_id=rhino_id,
        )
        r = raw.get("result") if isinstance(raw, dict) else None
        b64 = r.get("b64") if isinstance(r, dict) else None
        if not b64:
            return [raw]
        meta = {"path": r.get("path"), "saved": r.get("saved", False), "width": width, "height": height}
        return [meta, Image(data=base64.b64decode(b64), format="png")]

    @mcp.tool(annotations=ToolAnnotations(title="Undo", destructiveHint=True))
    def undo(steps: int = 1, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible undo using `steps`.
        """
        plugin = _try_plugin("undo", {"steps": steps})
        if plugin:
            return plugin
        results = [rhino.run_command("_Undo", rhino_id=rhino_id) for _ in range(max(1, steps))]
        return {"ok": all_results_ok(results), "results": results}

    @mcp.tool(annotations=ToolAnnotations(title="Redo", destructiveHint=True))
    def redo(steps: int = 1, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible redo using `steps`.
        """
        plugin = _try_plugin("redo", {"steps": steps})
        if plugin:
            return plugin
        results = [rhino.run_command("_Redo", rhino_id=rhino_id) for _ in range(max(1, steps))]
        return {"ok": all_results_ok(results), "results": results}


def _modify(object_ids: list[str], properties: dict[str, Any], rhino_id: str | None) -> dict[str, object]:
    import json

    payload = {"ids": object_ids, "selected": False}
    payload.update(properties)
    code = "__mcp_attrs = {!s}\n{}".format(json.dumps(payload), _ATTR_COMPAT_SCRIPT)
    return rhino.execute_python(code, rhino_id=rhino_id)


def _try_plugin(command_type: str, params: dict[str, Any]) -> dict[str, object] | None:
    if rhino.preferred_backend() not in {"auto", "plugin"}:
        return None
    try:
        result = rhino.plugin_result(command_type, params)
    except OSError:
        return None
    return result


def _normalize_modify_props(properties: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(properties)
    if "new_name" in normalized:
        normalized["name"] = normalized.pop("new_name")
    if "new_color" in normalized:
        normalized["color"] = normalized.pop("new_color")
    if "translation" in normalized:
        normalized["move"] = normalized["translation"]
    # "rotation" ([rx, ry, rz] in degrees) is forwarded to the C# plugin as-is;
    # the plugin's ApplyTransform calls RhinoMath.ToRadians() internally.
    return normalized


def all_results_ok(results: list[dict[str, Any]]) -> bool:
    return all(bool(item.get("ok")) for item in results)


_ATTR_COMPAT_SCRIPT = r'''
import rhinoscriptsyntax as rs
data = __mcp_attrs
ids = [oid for oid in data.get("ids", []) if rs.IsObject(oid)]
layer = data.get("layer")
if layer and not rs.IsLayer(layer):
    rs.AddLayer(layer)
for oid in ids:
    if data.get("name") is not None:
        rs.ObjectName(oid, data.get("name"))
    if layer:
        rs.ObjectLayer(oid, layer)
    if data.get("color") is not None:
        rs.ObjectColor(oid, tuple(data.get("color")[:3]))
    if data.get("location") is not None:
        bbox = rs.BoundingBox(oid)
        if bbox:
            current = bbox[0]
            target = data.get("location")
            rs.MoveObject(oid, (target[0] - current.X, target[1] - current.Y, target[2] - current.Z))
rs.Redraw()
result = {"objects": [str(oid) for oid in ids], "count": len(ids)}
'''

_DELETE_COMPAT_SCRIPT = r'''
import rhinoscriptsyntax as rs
ids = [oid for oid in __mcp_delete.get("ids", []) if rs.IsObject(oid)]
deleted = rs.DeleteObjects(ids) if ids else 0
rs.Redraw()
result = {"deleted": int(deleted or 0)}
'''

_DELETE_REF_SCRIPT = r'''
import rhinoscriptsyntax as rs
data = __mcp_delete_ref
ids = []
if data.get("all"):
    ids = rs.AllObjects() or []
elif data.get("id"):
    ids = [data.get("id")] if rs.IsObject(data.get("id")) else []
elif data.get("name"):
    ids = [oid for oid in (rs.AllObjects() or []) if rs.ObjectName(oid) == data.get("name")]
deleted = rs.DeleteObjects(ids) if ids else 0
rs.Redraw()
result = {"deleted": int(deleted or 0), "ids": [str(oid) for oid in ids]}
'''

_OBJECT_INFO_COMPAT_SCRIPT = r'''
import rhinoscriptsyntax as rs
oid = __mcp_object_info["object_id"]
if not rs.IsObject(oid):
    raise ValueError("Object not found: {}".format(oid))
bbox = rs.BoundingBox(oid) or []
result = {
    "id": str(oid),
    "name": rs.ObjectName(oid),
    "type": str(rs.ObjectType(oid)),
    "layer": rs.ObjectLayer(oid),
    "color": list(rs.ObjectColor(oid)),
    "bbox": [[p.X, p.Y, p.Z] for p in bbox],
}
'''

_OBJECT_INFO_REF_SCRIPT = r'''
import rhinoscriptsyntax as rs
data = __mcp_object_info_ref
oid = data.get("id")
if not oid and data.get("name"):
    matches = [item for item in (rs.AllObjects() or []) if rs.ObjectName(item) == data.get("name")]
    oid = matches[0] if matches else None
if not oid or not rs.IsObject(oid):
    raise ValueError("Object not found")
bbox = rs.BoundingBox(oid) or []
result = {
    "id": str(oid),
    "name": rs.ObjectName(oid),
    "type": str(rs.ObjectType(oid)),
    "layer": rs.ObjectLayer(oid),
    "color": list(rs.ObjectColor(oid)),
    "bbox": [[p.X, p.Y, p.Z] for p in bbox],
}
'''

_GET_OBJECTS_COMPAT_SCRIPT = r'''
import rhinoscriptsyntax as rs
limit = int(__mcp_get_objects.get("limit") or 100)
objects = []
for oid in (rs.AllObjects() or [])[:limit]:
    bbox = rs.BoundingBox(oid) or []
    objects.append({"id": str(oid), "name": rs.ObjectName(oid), "type": str(rs.ObjectType(oid)), "layer": rs.ObjectLayer(oid), "bbox": [[p.X, p.Y, p.Z] for p in bbox]})
result = {"objects": objects, "count": len(objects)}
'''

_GET_OBJECTS_REF_SCRIPT = r'''
import rhinoscriptsyntax as rs
data = __mcp_get_objects_ref
offset = int(data.get("offset") or 0)
limit = int(data.get("limit") or 100)
layer_filter = data.get("layer_filter")
type_filter = data.get("type_filter")
objects = []
source = rs.AllObjects() or []
filtered = []
for oid in source:
    if layer_filter and rs.ObjectLayer(oid) != layer_filter:
        continue
    if type_filter and type_filter.lower() not in str(rs.ObjectType(oid)).lower():
        continue
    filtered.append(oid)
for oid in filtered[offset:offset + limit]:
    bbox = rs.BoundingBox(oid) or []
    item = {"id": str(oid), "name": rs.ObjectName(oid), "type": str(rs.ObjectType(oid)), "layer": rs.ObjectLayer(oid), "bbox": [[p.X, p.Y, p.Z] for p in bbox]}
    if data.get("include_geometry"):
        item["geometry_note"] = "Detailed geometry serialization is backend-specific; use execute_rhino_python for custom extraction."
    objects.append(item)
result = {"objects": objects, "count": len(objects), "total_filtered": len(filtered), "offset": offset, "limit": limit}
'''

_SELECTED_REF_SCRIPT = r'''
import rhinoscriptsyntax as rs
limit = int(__mcp_selected.get("limit") or 100)
objects = []
for oid in (rs.SelectedObjects() or [])[:limit]:
    bbox = rs.BoundingBox(oid) or []
    objects.append({"id": str(oid), "name": rs.ObjectName(oid), "type": str(rs.ObjectType(oid)), "layer": rs.ObjectLayer(oid), "bbox": [[p.X, p.Y, p.Z] for p in bbox]})
result = {"objects": objects, "count": len(objects)}
'''

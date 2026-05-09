"""
Tools for viewport control and captures.
"""

from __future__ import annotations

import base64
import json

from mcp.server.fastmcp import FastMCP, Image
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Set Rhino View", destructiveHint=True))
    def set_rhino_view(
        view: str = "Perspective",
        camera: list[float] | None = None,
        target: list[float] | None = None,
        lens: float | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the active viewport by named view and optional camera/target.

        Common views include Perspective, Top, Front, Right, and Back.
        """
        payload = {"view": view, "camera": camera, "target": target, "lens": lens}
        code = "__mcp_view = {!s}\n{}".format(json.dumps(payload), _SET_VIEW_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Capture Rhino View", readOnlyHint=True))
    def capture_rhino_view(
        path: str | None = None,
        width: int = 1200,
        height: int = 900,
        viewport: str | None = None,
        show_grid: bool | None = None,
        show_axes: bool | None = None,
        show_cplane_axes: bool | None = None,
        zoom_to_fit: bool = False,
        rhino_id: str | None = None,
    ) -> list[object]:
        """
        Capture a Rhino viewport and return the image so the AI can see the scene.

        viewport: named viewport to capture (e.g. 'Top', 'Perspective'). Omit to
                  use the active viewport.
        path: optional file path to save the PNG on disk.
        width/height: output resolution in pixels (default 1200×900).
        show_grid: temporarily show (True) or hide (False) the construction grid.
        show_axes: temporarily show/hide the world axis widget.
        show_cplane_axes: temporarily show/hide the construction-plane axis lines.
        zoom_to_fit: zoom to extents of all objects before capture.

        Display overrides are restored after capture. Returns metadata + the image.
        """
        payload = {
            "path": path, "width": width, "height": height,
            "viewport": viewport, "show_grid": show_grid,
            "show_axes": show_axes, "show_cplane_axes": show_cplane_axes,
            "zoom_to_fit": zoom_to_fit,
        }
        code = "__mcp_capture = {!s}\n{}".format(json.dumps(payload), _CAPTURE_SCRIPT)
        raw = rhino.execute_python(code, rhino_id=rhino_id)

        r = raw.get("result") if isinstance(raw, dict) else None
        b64 = r.get("b64") if isinstance(r, dict) else None

        if not b64:
            # Rhino didn't return image bytes — surface the raw response so the
            # caller can see what went wrong.
            return [raw]

        img_bytes = base64.b64decode(b64)
        meta = {
            "path": r.get("path"),
            "saved": r.get("saved", False),
            "width": r.get("width", width),
            "height": r.get("height", height),
        }
        # Return metadata first, then the visual image so the AI can see the scene.
        return [meta, Image(data=img_bytes, format="png")]

    @mcp.tool(annotations=ToolAnnotations(title="Zoom Extents", destructiveHint=True))
    def zoom_extents(
        all_views: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Zoom the active viewport to show all objects.
        ``all_views=True`` zooms all open viewports simultaneously.
        """
        code = "__mcp_zoom_all = {!r}\n{}".format(all_views, _VIEW_OPS_SCRIPT)
        code = "__mcp_view_op = 'zoom_extents'\n" + code
        payload = {"op": "zoom_extents", "all_views": all_views}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Zoom Selected", destructiveHint=True))
    def zoom_selected(
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Zoom the active viewport to fit the current selection.
        """
        payload = {"op": "zoom_selected"}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Zoom to Object", destructiveHint=True))
    def zoom_to_object(
        object_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Zoom the active viewport to frame a specific object by GUID.
        McNeel/RhinoMCP ZoomToObjectTool equivalent.
        """
        payload = {"op": "zoom_to_object", "object_id": object_id}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Zoom to Layer", destructiveHint=True))
    def zoom_to_layer(
        layer_name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Zoom the active viewport to frame all objects on a layer.
        McNeel/RhinoMCP ZoomToLayerTool equivalent.
        """
        payload = {"op": "zoom_to_layer", "layer_name": layer_name}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get View Info", readOnlyHint=True))
    def get_view_info(
        viewport: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return camera position, target, lens length, and display mode for a viewport.
        Omit ``viewport`` to query the active viewport.
        """
        payload = {"op": "get_info", "viewport": viewport}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Display Mode", destructiveHint=True))
    def set_display_mode(
        mode: str,
        viewport: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the display mode of a viewport.

        Common modes: ``Wireframe``, ``Shaded``, ``Rendered``, ``Ghosted``,
        ``XRay``, ``Technical``, ``Artistic``, ``Pen``.
        Omit ``viewport`` to apply to the active viewport.
        """
        payload = {"op": "set_display_mode", "mode": mode, "viewport": viewport}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Named View", destructiveHint=True))
    def add_named_view(
        name: str,
        viewport: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Save the current viewport state as a named view.
        """
        payload = {"op": "add_named_view", "name": name, "viewport": viewport}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Restore Named View", destructiveHint=True))
    def restore_named_view(
        name: str,
        viewport: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Restore a previously saved named view.
        """
        payload = {"op": "restore_named_view", "name": name, "viewport": viewport}
        code = "__mcp_view_op = {!r}\n{}".format(payload, _VIEW_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_VIEW_OPS_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import System

data = __mcp_view_op
op   = data["op"]

def _get_vp(name):
    doc = Rhino.RhinoDoc.ActiveDoc
    if name:
        for v in doc.Views:
            if v.ActiveViewport.Name == name:
                return v
    return doc.Views.ActiveView

if op == "zoom_extents":
    if data.get("all_views"):
        rs.ZoomExtents(None, True)
    else:
        rs.ZoomExtents()
    result = {"ok": True}

elif op == "zoom_selected":
    rs.ZoomSelected()
    result = {"ok": True}

elif op == "zoom_to_object":
    doc = Rhino.RhinoDoc.ActiveDoc
    obj = doc.Objects.FindId(System.Guid(str(data["object_id"])))
    if obj is None:
        result = {"ok": False, "error": "Object not found: {}".format(data["object_id"])}
    else:
        bbox = obj.Geometry.GetBoundingBox(True)
        doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(bbox)
        doc.Views.ActiveView.Redraw()
        result = {"ok": True, "object_id": data["object_id"]}

elif op == "zoom_to_layer":
    doc = Rhino.RhinoDoc.ActiveDoc
    import Rhino.Geometry
    lname = data["layer_name"]
    li = doc.Layers.FindByFullPath(lname, Rhino.RhinoMath.UnsetIntIndex)
    if li < 0:
        result = {"ok": False, "error": "Layer not found: {}".format(lname)}
    else:
        bbox = Rhino.Geometry.BoundingBox.Empty
        for obj in doc.Objects:
            if not obj.IsDeleted and obj.Attributes.LayerIndex == li:
                bbox.Union(obj.Geometry.GetBoundingBox(True))
        if bbox.IsValid:
            doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(bbox)
            doc.Views.ActiveView.Redraw()
            result = {"ok": True, "layer": lname}
        else:
            result = {"ok": False, "error": "No objects on layer: {}".format(lname)}

elif op == "get_info":
    vp = _get_vp(data.get("viewport"))
    avp = vp.ActiveViewport if vp else None
    if avp:
        cam    = avp.CameraLocation
        target = avp.CameraTarget
        result = {
            "name": avp.Name,
            "camera": [cam.X, cam.Y, cam.Z],
            "target": [target.X, target.Y, target.Z],
            "lens_length": avp.Camera35mmLensLength,
            "display_mode": str(avp.DisplayMode.EnglishName),
            "projection": str(avp.IsParallelProjection and "Parallel" or "Perspective"),
        }
    else:
        result = {"ok": False, "error": "Viewport not found"}

elif op == "set_display_mode":
    vp = _get_vp(data.get("viewport"))
    if vp:
        mode_id = Rhino.Display.DisplayModeDescription.FindByName(data["mode"])
        if mode_id:
            vp.ActiveViewport.DisplayMode = mode_id
            vp.Redraw()
            result = {"ok": True, "mode": data["mode"]}
        else:
            result = {"ok": False, "error": "Unknown display mode: {}".format(data["mode"])}
    else:
        result = {"ok": False, "error": "Viewport not found"}

elif op == "add_named_view":
    vp = _get_vp(data.get("viewport"))
    if vp:
        doc = Rhino.RhinoDoc.ActiveDoc
        idx = doc.NamedViews.Add(data["name"], vp.ActiveViewport.Id)
        result = {"ok": idx >= 0, "name": data["name"], "index": idx}
    else:
        result = {"ok": False, "error": "Viewport not found"}

elif op == "restore_named_view":
    doc = Rhino.RhinoDoc.ActiveDoc
    idx = doc.NamedViews.FindByName(data["name"])
    if idx >= 0:
        vp = _get_vp(data.get("viewport"))
        if vp:
            doc.NamedViews.Restore(idx, vp.ActiveViewport)
            vp.Redraw()
            result = {"ok": True, "name": data["name"]}
        else:
            result = {"ok": False, "error": "Viewport not found"}
    else:
        result = {"ok": False, "error": "Named view not found: {}".format(data["name"])}
'''


_SET_VIEW_SCRIPT = r'''
import Rhino
from Rhino.Geometry import Point3d

doc = Rhino.RhinoDoc.ActiveDoc
view = doc.Views.Find(__mcp_view.get("view"), False) or doc.Views.ActiveView
if view is None:
    raise RuntimeError("No active Rhino view")
doc.Views.ActiveView = view
viewport = view.ActiveViewport
name = str(__mcp_view.get("view") or "")
if name.lower() in {"top", "front", "right", "back", "left", "bottom", "perspective"}:
    viewport.SetToPlanView(name, True)
camera = __mcp_view.get("camera")
target = __mcp_view.get("target")
if camera and target:
    viewport.SetCameraLocations(Point3d(*camera[:3]), Point3d(*target[:3]))
if __mcp_view.get("lens") is not None:
    viewport.Camera35mmLensLength = float(__mcp_view["lens"])
view.Redraw()
result = {"view": viewport.Name}
'''

_CAPTURE_SCRIPT = r'''
import Rhino
import System.Drawing
import System.Drawing.Imaging
import System.IO
import System.Convert

doc = Rhino.RhinoDoc.ActiveDoc
viewport_name = __mcp_capture.get("viewport")
if viewport_name:
    v = doc.Views.Find(viewport_name, False)
    if v is not None:
        doc.Views.ActiveView = v

view = doc.Views.ActiveView
if view is None:
    raise RuntimeError("No active Rhino view")

vp = view.ActiveViewport
w = int(__mcp_capture["width"])
h = int(__mcp_capture["height"])
path = __mcp_capture.get("path")
zoom_to_fit = bool(__mcp_capture.get("zoom_to_fit", False))
show_grid = __mcp_capture.get("show_grid")
show_cplane_axes = __mcp_capture.get("show_cplane_axes")
if show_cplane_axes is None:
    show_cplane_axes = __mcp_capture.get("show_axes")

# Save original display states
orig_grid = vp.ConstructionGridVisible
orig_axes = vp.ConstructionAxesVisible

try:
    if show_grid is not None:
        vp.ConstructionGridVisible = bool(show_grid)
    if show_cplane_axes is not None:
        vp.ConstructionAxesVisible = bool(show_cplane_axes)
    if zoom_to_fit:
        view.ZoomExtents()
    view.Redraw()
    bitmap = view.CaptureToBitmap(System.Drawing.Size(w, h))
finally:
    vp.ConstructionGridVisible = orig_grid
    vp.ConstructionAxesVisible = orig_axes

ms = System.IO.MemoryStream()
bitmap.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
b64 = System.Convert.ToBase64String(ms.ToArray())
ms.Dispose()

saved = False
if path:
    bitmap.Save(path)
    saved = True

bitmap.Dispose()
result = {"path": path, "b64": b64, "saved": saved, "width": w, "height": h}
'''

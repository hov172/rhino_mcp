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
        rhino_id: str | None = None,
    ) -> list[object]:
        """
        Capture the active Rhino viewport and return the image so the AI can see
        the current state of the scene.

        path: optional file path to save the PNG on disk (e.g. '/tmp/view.png').
              Omit to capture in-memory only.
        width/height: output resolution in pixels (default 1200×900).

        Returns the image as visual content the AI can inspect, plus metadata
        ({path, saved, width, height}).  When path is omitted, saved=false and
        path=null in the metadata.
        """
        payload = {"path": path, "width": width, "height": height}
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

view = Rhino.RhinoDoc.ActiveDoc.Views.ActiveView
if view is None:
    raise RuntimeError("No active Rhino view")

w = int(__mcp_capture["width"])
h = int(__mcp_capture["height"])
path = __mcp_capture.get("path")

bitmap = view.CaptureToBitmap(System.Drawing.Size(w, h))

# Encode PNG to base64 in memory so the MCP server can return it as image content.
ms = System.IO.MemoryStream()
bitmap.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
b64 = System.Convert.ToBase64String(ms.ToArray())
ms.Dispose()

# Save to disk only when a path was requested.
saved = False
if path:
    bitmap.Save(path)
    saved = True

bitmap.Dispose()
result = {"path": path, "b64": b64, "saved": saved, "width": w, "height": h}
'''

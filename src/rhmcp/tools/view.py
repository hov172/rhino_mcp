"""
Tools for viewport control and captures.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
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
    def capture_rhino_view(path: str, width: int = 1200, height: int = 900, rhino_id: str | None = None) -> dict[str, object]:
        """
        Capture the active Rhino viewport to an image file path.
        """
        payload = {"path": path, "width": width, "height": height}
        code = "__mcp_capture = {!s}\n{}".format(json.dumps(payload), _CAPTURE_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


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
from System.Drawing import Size

view = Rhino.RhinoDoc.ActiveDoc.Views.ActiveView
if view is None:
    raise RuntimeError("No active Rhino view")
bitmap = view.CaptureToBitmap(Size(int(__mcp_capture["width"]), int(__mcp_capture["height"])))
ok = bitmap.Save(__mcp_capture["path"])
result = {"path": __mcp_capture["path"], "saved": True}
'''

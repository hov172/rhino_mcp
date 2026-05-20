"""
Annotation tools: text, text dots, and leaders.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Add Text", destructiveHint=True))
    def add_text(
        text: str,
        point: list[float],
        height: float = 1.0,
        font: str = "",
        bold: bool = False,
        italic: bool = False,
        name: str | None = None,
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Add a text annotation object at ``point`` [x, y, z].

        ``height`` controls the text height in model units.
        ``font`` selects a font family (e.g. ``"Arial"``); leave blank for..."""
        err = validate.coordinate(point, "point")
        if err: return err
        payload = {
            "text": text, "point": point, "height": height, "font": font,
            "bold": bold, "italic": italic, "name": name, "layer": layer,
        }
        code = "__mcp_ann = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Text Dot", destructiveHint=True))
    def add_text_dot(
        text: str,
        point: list[float],
        font_height: int = 14,
        name: str | None = None,
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Add a text dot at ``point`` [x, y, z].

        Text dots always face the camera and maintain a constant screen size,
        making them ideal for labels and callouts.
        """
        err = validate.coordinate(point, "point")
        if err: return err
        payload = {
            "text": text, "point": point, "font_height": font_height,
            "name": name, "layer": layer,
        }
        code = "__mcp_ann = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Leader", destructiveHint=True))
    def add_leader(
        points: list[list[float]],
        text: str = "",
        name: str | None = None,
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Add a leader annotation through ``points`` (list of [x, y, z] pts).

        The last segment ends with an arrowhead. ``text`` is appended at the
        tail of the leader.
        """
        payload = {
            "points": points, "text": text, "name": name, "layer": layer,
        }
        code = "__mcp_ann = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

data = __mcp_ann
name  = data.get("name")
layer = data.get("layer")

def _apply(oid):
    if oid:
        if name:  rs.ObjectName(oid, name)
        if layer:
            if not rs.IsLayer(layer): rs.AddLayer(layer)
            rs.ObjectLayer(oid, layer)
    return str(oid) if oid else None

if "font_height" in data:
    # text dot
    pt = data["point"]
    dot = rs.AddTextDot(data["text"], pt)
    if dot and data.get("font_height"):
        obj = Rhino.RhinoDoc.ActiveDoc.Objects.FindId(System.Guid(str(dot)))
        if obj:
            td = obj.Geometry
            td.FontHeight = int(data["font_height"])
            obj.CommitChanges()
    result = {"id": _apply(dot), "type": "text_dot"}

elif "points" in data:
    # leader
    pts = [rs.CreatePoint(p) for p in data["points"]]
    lid = rs.AddLeader(pts, text=data.get("text") or "")
    result = {"id": _apply(lid), "type": "leader"}

else:
    # text
    pt   = data["point"]
    font = data.get("font") or ""
    h    = float(data.get("height", 1.0))
    bold   = bool(data.get("bold"))
    italic = bool(data.get("italic"))
    style  = 0
    if bold:   style |= 1
    if italic: style |= 2
    tid = rs.AddText(data["text"], pt, height=h, font=font, font_style=style)
    result = {"id": _apply(tid), "type": "text"}

rs.Redraw()
'''

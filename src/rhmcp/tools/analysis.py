"""
Measurement and geometric analysis tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Measure Distance", readOnlyHint=True))
    def measure_distance(
        point1: list[float],
        point2: list[float],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the Euclidean distance between two points [x, y, z].
        """
        payload = {"op": "distance", "point1": point1, "point2": point2}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Measure Curve Length", readOnlyHint=True))
    def measure_curve_length(
        curve_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the arc length of a curve.
        """
        payload = {"op": "curve_length", "curve_id": curve_id}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Measure Area", readOnlyHint=True))
    def measure_area(
        object_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the area of a surface, polysurface, or closed planar curve.
        """
        payload = {"op": "area", "object_id": object_id}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Measure Volume", readOnlyHint=True))
    def measure_volume(
        object_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the volume of a closed solid (polysurface or mesh).
        """
        payload = {"op": "volume", "object_id": object_id}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Object Bounding Box", readOnlyHint=True))
    def get_bounding_box(
        object_ids: list[str],
        world_coordinates: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the axis-aligned bounding box of one or more objects.

        Returns ``min``, ``max``, ``center``, ``width``, ``depth``, ``height``.
        """
        payload = {"op": "bbox", "object_ids": object_ids, "world": world_coordinates}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Check Object Solid", readOnlyHint=True))
    def is_object_solid(
        object_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Check whether an object is a closed solid (watertight polysurface or mesh).
        """
        payload = {"op": "is_solid", "object_id": object_id}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import math

data = __mcp_analysis
op   = data["op"]

if op == "distance":
    p1 = data["point1"]
    p2 = data["point2"]
    d  = math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
    result = {"distance": d, "point1": p1, "point2": p2}

elif op == "curve_length":
    length = rs.CurveLength(data["curve_id"])
    result = {"length": length, "curve_id": data["curve_id"]}

elif op == "area":
    oid = data["object_id"]
    area = None
    if rs.IsCurve(oid):
        props = rs.CurveAreaCentroid(oid)
        area = props[0] if props else None
    else:
        props = rs.SurfaceArea(oid)
        area = props[0] if props else None
    result = {"area": area, "object_id": oid}

elif op == "volume":
    props = rs.SurfaceVolume(data["object_id"])
    result = {"volume": props[0] if props else None, "object_id": data["object_id"]}

elif op == "bbox":
    box = rs.BoundingBox(data["object_ids"])
    if box:
        mn = [box[0].X, box[0].Y, box[0].Z]
        mx = [box[6].X, box[6].Y, box[6].Z]
        cx = [(a + b) / 2 for a, b in zip(mn, mx)]
        result = {
            "min": mn, "max": mx, "center": cx,
            "width":  mx[0] - mn[0],
            "depth":  mx[1] - mn[1],
            "height": mx[2] - mn[2],
        }
    else:
        result = {"ok": False, "error": "Could not compute bounding box"}

elif op == "is_solid":
    oid = data["object_id"]
    solid = bool(rs.IsPolysurfaceClosed(oid) or rs.IsMeshClosed(oid))
    result = {"is_solid": solid, "object_id": oid}
'''

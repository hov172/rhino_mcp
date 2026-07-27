"""
Measurement and geometric analysis tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


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
        err = validate.coordinate(point1, "point1") or validate.coordinate(point2, "point2")
        if err: return err
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
        err = validate.guid(curve_id, "curve_id")
        if err: return err
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
        err = validate.guid(object_id, "object_id")
        if err: return err
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
        err = validate.guid(object_id, "object_id")
        if err: return err
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
        err = validate.guid_list(object_ids, "object_ids")
        if err: return err
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
        err = validate.guid(object_id, "object_id")
        if err: return err
        payload = {"op": "is_solid", "object_id": object_id}
        code = "__mcp_analysis = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

data = __mcp_analysis
op   = data["op"]

if op == "distance":
    p1 = data["point1"]
    p2 = data["point2"]
    d  = rs.Distance(p1, p2)
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
    elif rs.IsMesh(oid):
        props = rs.MeshArea(oid)
        area = props[0] if props else None
    else:
        props = rs.SurfaceArea(oid)
        area = props[0] if props else None
    result = {"area": area, "object_id": oid}

elif op == "volume":
    oid = data["object_id"]
    if rs.IsMesh(oid):
        # MeshVolume returns (mesh_count, volume, error_estimate)
        props = rs.MeshVolume(oid)
        volume = props[1] if props else None
    else:
        # SurfaceVolume returns (volume, error_estimate)
        props = rs.SurfaceVolume(oid)
        volume = props[0] if props else None
    result = {"volume": volume, "object_id": oid}

elif op == "bbox":
    if data.get("world", True):
        box = rs.BoundingBox(data["object_ids"])
        coord_system = "world"
    else:
        cplane = rs.ViewCPlane()
        box = rs.BoundingBox(data["object_ids"], cplane, in_world_coords=False)
        coord_system = "cplane"
    if box:
        mn = [box[0].X, box[0].Y, box[0].Z]
        mx = [box[6].X, box[6].Y, box[6].Z]
        cx = [(a + b) / 2 for a, b in zip(mn, mx)]
        result = {
            "min": mn, "max": mx, "center": cx,
            "width":  mx[0] - mn[0],
            "depth":  mx[1] - mn[1],
            "height": mx[2] - mn[2],
            "coordinate_system": coord_system,
        }
    else:
        result = {"ok": False, "error": "Could not compute bounding box", "error_code": "COMPUTATION_FAILED"}

elif op == "is_solid":
    oid = data["object_id"]
    solid = bool(rs.IsPolysurfaceClosed(oid) or rs.IsMeshClosed(oid))
    result = {"is_solid": solid, "object_id": oid}
'''

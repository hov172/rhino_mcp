"""
Curve projection, intersection, and splitting tools.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Project Rhino Curve", destructiveHint=True))
    def project_curve(curve_id: str, target_ids: list[str], direction: list[float], name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Project a curve onto surfaces, polysurfaces, or meshes.
        """
        err = (validate.guid(curve_id, "curve_id") or
               validate.guid_list(target_ids, "target_ids") or
               validate.coordinate(direction, "direction"))
        if err: return err
        return _run("project_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Intersect Rhino Curves", destructiveHint=True))
    def intersect_curves(
        curve_id_a: str,
        curve_id_b: str,
        tolerance: float | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create point objects at intersections between two curves.
        """
        err = validate.guid(curve_id_a, "curve_id_a") or validate.guid(curve_id_b, "curve_id_b")
        if err: return err
        return _run("intersect_curves", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Split Rhino Curve", destructiveHint=True))
    def split_curve(
        curve_id: str,
        parameters: list[float] | None = None,
        point_ids: list[str] | None = None,
        delete_source: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Split a curve at parameters or at closest parameters to point objects.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        if point_ids is not None:
            err = validate.guid_list(point_ids, "point_ids")
            if err: return err
        return _run("split_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Create Rectangle Curve", destructiveHint=True))
    def create_rectangle(
        center: list[float],
        width: float,
        height: float,
        plane_normal: list[float] | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a rectangle curve centred at ``center`` [x, y, z] with ``width`` and ``height``.
        ``plane_normal`` tilts the plane (default Z-up).
        """
        err = validate.coordinate(center, "center")
        if err: return err
        return _run("create_rectangle", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Create Spiral Curve", destructiveHint=True))
    def create_spiral(
        axis_start: list[float],
        axis_end: list[float],
        pitch: float,
        turns: float,
        radius_start: float,
        radius_end: float = -1.0,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a spiral curve along an axis.

        ``pitch`` is rise per revolution. ``turns`` is the number of full turns.
        ``radius_end < 0`` uses ``radius_start`` for a uniform helix.
        """
        err = validate.coordinate(axis_start, "axis_start") or validate.coordinate(axis_end, "axis_end")
        if err: return err
        return _run("create_spiral", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Create NURBS Curve", destructiveHint=True))
    def create_nurbs_curve(
        points: list[list[float]],
        degree: int = 3,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a NURBS curve through ``points`` (list of [x,y,z]) with the given ``degree``.
        """
        return _run("create_nurbs_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Create Blend Curve", destructiveHint=True))
    def create_blend_curve(
        curve1_id: str,
        curve2_id: str,
        continuity: int = 1,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a blend curve between two curves.

        ``continuity``: 0 = position, 1 = tangency (default), 2 = curvature.
        """
        err = validate.guid(curve1_id, "curve1_id") or validate.guid(curve2_id, "curve2_id")
        if err: return err
        return _run("create_blend_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Fillet Curves", destructiveHint=True))
    def fillet_curves(
        curve1_id: str,
        curve2_id: str,
        radius: float,
        trim: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a fillet arc of ``radius`` between two curves and optionally trim them.
        """
        err = validate.guid(curve1_id, "curve1_id") or validate.guid(curve2_id, "curve2_id")
        if err: return err
        return _run("fillet_curves", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Divide Curve by Segments", destructiveHint=True))
    def divide_curve(
        curve_id: str,
        segments: int,
        create_points: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Divide a curve into ``segments`` equal parts.

        ``create_points=True`` adds point objects at each division.
        Returns division parameters and point coordinates.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("divide_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Divide Curve by Length", destructiveHint=True))
    def divide_curve_length(
        curve_id: str,
        length: float,
        create_points: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Divide a curve at equal arc-length intervals of ``length``.

        ``create_points=True`` adds point objects at each division.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("divide_curve_length", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Close Curve", destructiveHint=True))
    def close_curve(
        curve_id: str,
        tolerance: float | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Close an open curve by connecting its endpoints.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("close_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Reverse Curve", destructiveHint=True))
    def reverse_curve(
        curve_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reverse the direction of a curve.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("reverse_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Rebuild Curve", destructiveHint=True))
    def rebuild_curve(
        curve_id: str,
        degree: int = 3,
        point_count: int = 10,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Rebuild a curve with a new ``degree`` and ``point_count``.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("rebuild_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Curve Closest Point", readOnlyHint=True))
    def curve_closest_point(
        curve_id: str,
        point: list[float],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Find the closest point on a curve to a given ``point`` [x, y, z].

        Returns the closest point coordinates and curve parameter.
        """
        err = validate.guid(curve_id, "curve_id") or validate.coordinate(point, "point")
        if err: return err
        return _run("curve_closest_point", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Evaluate Curve at Parameter", readOnlyHint=True))
    def evaluate_curve(
        curve_id: str,
        parameter: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Evaluate a curve at ``parameter`` to return its point and tangent vector.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("evaluate_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Get Curve Start and End Points", readOnlyHint=True))
    def curve_start_end_points(
        curve_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Return the start and end points of a curve.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("curve_start_end_points", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Join Curves", destructiveHint=True))
    def join_curves(
        curve_ids: list[str],
        delete_input: bool = True,
        tolerance: float | None = None,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Join a list of curves into one or more polycurves.
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        return _run("join_curves", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Explode Curves", destructiveHint=True))
    def explode_curves(
        curve_ids: list[str],
        delete_input: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Explode polycurves into their constituent segments.
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        return _run("explode_curves", locals())


def _run(operation: str, payload: dict[str, object]) -> dict[str, object]:
    rhino_id = payload.pop("rhino_id", None)
    plugin_params = {key: value for key, value in payload.items() if value is not None}
    payload["operation"] = operation
    code = "__mcp_curveop = {!s}\n{}".format(json.dumps(payload), _SCRIPT)
    return rhino.run_plugin_or_python(
        operation,
        plugin_params,
        code,
        rhino_id=rhino_id if isinstance(rhino_id, str) else None,
    )


_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs
from Rhino.Geometry import Vector3d
from Rhino.Geometry.Intersect import Intersection

data = __mcp_curveop
operation = data["operation"]
name = data.get("name")

def _name(ids):
    for i, oid in enumerate(ids or []):
        if name:
            rs.ObjectName(oid, name if len(ids) == 1 else "{}_{}".format(name, i + 1))
    return [str(oid) for oid in ids or []]

if operation == "project_curve":
    direction = data["direction"]
    ids = rs.ProjectCurveToSurface(data["curve_id"], data["target_ids"], direction)
    if ids and not isinstance(ids, (list, tuple)):
        ids = [ids]
    result = {"result_ids": _name(ids or []), "message": "Curve projected"}
elif operation == "intersect_curves":
    events = rs.CurveCurveIntersection(data["curve_id_a"], data["curve_id_b"], tolerance=data.get("tolerance"))
    points = []
    point_ids = []
    curve_ids = []
    for event in events or []:
        if event[0] == 1:
            pt = event[1]
            points.append([pt[0], pt[1], pt[2]])
            point_ids.append(rs.AddPoint(pt))
        elif event[0] == 2:
            curve_id = rs.AddLine(event[1], event[2])
            curve_ids.append(curve_id)
    result = {"point_ids": _name(point_ids), "curve_ids": _name(curve_ids), "points": points}
elif operation == "split_curve":
    params = list(data.get("parameters") or [])
    for point_id in data.get("point_ids") or []:
        point = rs.PointCoordinates(point_id)
        if point:
            param = rs.CurveClosestPoint(data["curve_id"], point)
            if param is not None:
                params.append(param)
    if not params:
        raise ValueError("No split parameters resolved")
    ids = rs.SplitCurve(data["curve_id"], sorted(params), delete_input=bool(data.get("delete_source", True)))
    result = {"result_ids": _name(ids or []), "message": "Curve split"}
elif operation == "create_rectangle":
    import math
    c = data["center"]
    w = float(data["width"]) / 2
    h = float(data["height"]) / 2
    n = data.get("plane_normal") or [0, 0, 1]
    plane = rs.PlaneFromNormal(c, n)
    pts = [
        rs.PlaneClosestPoint(plane, [c[0]-w, c[1]-h, c[2]]) or [c[0]-w, c[1]-h, c[2]],
        rs.PlaneClosestPoint(plane, [c[0]+w, c[1]-h, c[2]]) or [c[0]+w, c[1]-h, c[2]],
        rs.PlaneClosestPoint(plane, [c[0]+w, c[1]+h, c[2]]) or [c[0]+w, c[1]+h, c[2]],
        rs.PlaneClosestPoint(plane, [c[0]-w, c[1]+h, c[2]]) or [c[0]-w, c[1]+h, c[2]],
    ]
    oid = rs.AddPolyline(pts + [pts[0]])
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "create_spiral":
    p1    = data["axis_start"]
    p2    = data["axis_end"]
    pitch = float(data["pitch"])
    turns = float(data["turns"])
    r0    = float(data["radius_start"])
    r1    = float(data["radius_end"]) if data.get("radius_end", -1) >= 0 else r0
    oid   = rs.AddSpiral(p1, p2, pitch, turns, r0, r1)
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "create_nurbs_curve":
    pts = data["points"]
    deg = int(data.get("degree", 3))
    oid = rs.AddCurve(pts, deg)
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "create_blend_curve":
    oid = rs.AddBlendCurve(
        data["curve1_id"], data["curve2_id"],
        continuity=int(data.get("continuity", 1)))
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "fillet_curves":
    ids = rs.FilletCurves(data["curve1_id"], data["curve2_id"],
                          float(data["radius"]), trim=bool(data.get("trim", True)))
    result = {"result_ids": _name(ids or [])}

elif operation == "divide_curve":
    pts = rs.DivideCurve(data["curve_id"], int(data["segments"]),
                         create_points=bool(data.get("create_points", True)),
                         return_points=True)
    point_ids = []
    if data.get("create_points", True):
        for pt in (pts or []):
            point_ids.append(str(rs.AddPoint(pt)))
    result = {"points": [[p.X, p.Y, p.Z] for p in (pts or [])],
              "point_ids": point_ids,
              "count": len(pts or [])}

elif operation == "divide_curve_length":
    pts = rs.DivideCurveLength(data["curve_id"], float(data["length"]),
                               create_points=bool(data.get("create_points", True)),
                               return_points=True)
    point_ids = []
    if data.get("create_points", True):
        for pt in (pts or []):
            point_ids.append(str(rs.AddPoint(pt)))
    result = {"points": [[p.X, p.Y, p.Z] for p in (pts or [])],
              "point_ids": point_ids,
              "count": len(pts or [])}

elif operation == "close_curve":
    tol = data.get("tolerance")
    oid = rs.CloseCurve(data["curve_id"], tol) if tol else rs.CloseCurve(data["curve_id"])
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "reverse_curve":
    ok = rs.ReverseCurve(data["curve_id"])
    result = {"ok": bool(ok), "curve_id": data["curve_id"]}

elif operation == "rebuild_curve":
    oid = rs.RebuildCurve(data["curve_id"],
                          degree=int(data.get("degree", 3)),
                          pointcount=int(data.get("point_count", 10)))
    result = {"result_ids": _name([oid] if oid else [])}

elif operation == "curve_closest_point":
    pt    = data["point"]
    param = rs.CurveClosestPoint(data["curve_id"], pt)
    if param is not None:
        closest = rs.EvaluateCurve(data["curve_id"], param)
        result = {"parameter": param,
                  "point": [closest.X, closest.Y, closest.Z]}
    else:
        result = {"ok": False, "error": "Could not find closest point"}

elif operation == "evaluate_curve":
    pt  = rs.EvaluateCurve(data["curve_id"], float(data["parameter"]))
    tan = rs.CurveTangent(data["curve_id"], float(data["parameter"]))
    result = {"point": [pt.X, pt.Y, pt.Z] if pt else None,
              "tangent": [tan.X, tan.Y, tan.Z] if tan else None,
              "parameter": data["parameter"]}

elif operation == "curve_start_end_points":
    sp = rs.CurveStartPoint(data["curve_id"])
    ep = rs.CurveEndPoint(data["curve_id"])
    result = {"start": [sp.X, sp.Y, sp.Z] if sp else None,
              "end": [ep.X, ep.Y, ep.Z] if ep else None}

elif operation == "join_curves":
    tol = data.get("tolerance")
    ids = rs.JoinCurves(data["curve_ids"],
                        delete_input=bool(data.get("delete_input", True)),
                        tolerance=tol)
    result = {"result_ids": _name(ids or []), "count": len(ids or [])}

elif operation == "explode_curves":
    all_ids = []
    for cid in data["curve_ids"]:
        segs = rs.ExplodeCurves(cid, delete_input=bool(data.get("delete_input", True)))
        all_ids.extend(segs or [cid])
    result = {"result_ids": _name(all_ids), "count": len(all_ids)}

else:
    raise ValueError("Unsupported curve operation: {}".format(operation))

rs.Redraw()
'''

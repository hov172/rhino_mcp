"""
Curve projection, intersection, and splitting tools.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Project Rhino Curve", destructiveHint=True))
    def project_curve(curve_id: str, target_ids: list[str], direction: list[float], name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Project a curve onto surfaces, polysurfaces, or meshes.
        """
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
        return _run("split_curve", locals())


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
else:
    raise ValueError("Unsupported curve operation: {}".format(operation))

rs.Redraw()
'''

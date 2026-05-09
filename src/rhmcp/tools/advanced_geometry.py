"""
Advanced geometry operations for Rhino objects.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Loft Rhino Curves", destructiveHint=True))
    def loft(curve_ids: list[str], name: str | None = None, closed: bool = False, loft_type: int = 0, rhino_id: str | None = None) -> dict[str, object]:
        """
        Create a loft surface through multiple curve ids.

        ``loft_type`` maps to RhinoScriptSyntax AddLoftSrf loft_type values.
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        return _run("loft", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Extrude Rhino Curve", destructiveHint=True))
    def extrude_curve(curve_id: str, direction: list[float], name: str | None = None, cap: bool = True, rhino_id: str | None = None) -> dict[str, object]:
        """
        Extrude a curve along a vector. Closed curves can be capped into solids.
        """
        err = validate.guid(curve_id, "curve_id") or validate.coordinate(direction, "direction")
        if err: return err
        return _run("extrude_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Sweep One Rail", destructiveHint=True))
    def sweep1(rail_id: str, profile_ids: list[str], name: str | None = None, closed: bool = False, rhino_id: str | None = None) -> dict[str, object]:
        """
        Sweep one or more profile curves along a rail curve.
        """
        err = validate.guid(rail_id, "rail_id") or validate.guid_list(profile_ids, "profile_ids")
        if err: return err
        return _run("sweep1", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Offset Rhino Curve", destructiveHint=True))
    def offset_curve(
        curve_id: str,
        distance: float,
        name: str | None = None,
        plane_normal: list[float] | None = None,
        corner_style: int = 1,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Offset a curve by distance. ``corner_style`` follows RhinoScriptSyntax.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("offset_curve", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Pipe Along Curve", destructiveHint=True))
    def pipe(
        curve_id: str,
        radius: float,
        name: str | None = None,
        cap: bool = True,
        fit_rail: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a pipe along a curve.
        """
        err = validate.guid(curve_id, "curve_id")
        if err: return err
        return _run("pipe", locals())


def _run(operation: str, payload: dict[str, object]) -> dict[str, object]:
    rhino_id = payload.pop("rhino_id", None)
    payload.pop("err", None)
    plugin_params = {key: value for key, value in payload.items() if value is not None}
    payload["operation"] = operation
    code = "__mcp_advanced = {!s}\n{}".format(json.dumps(payload), _SCRIPT)
    return rhino.run_plugin_or_python(
        operation,
        plugin_params,
        code,
        rhino_id=rhino_id if isinstance(rhino_id, str) else None,
    )


_SCRIPT = r'''
import Rhino
import rhinoscriptsyntax as rs
from Rhino.Geometry import Point3d, Vector3d

data = __mcp_advanced
operation = data["operation"]

def _name(ids, name):
    if name:
        for i, oid in enumerate(ids):
            if oid:
                rs.ObjectName(oid, name if len(ids) == 1 else "{}_{}".format(name, i + 1))
    return [str(oid) for oid in ids if oid]

if operation == "loft":
    ids = rs.AddLoftSrf(data["curve_ids"], start=None, end=None, loft_type=int(data.get("loft_type", 0)), simplify_method=0, value=0, closed=bool(data.get("closed", False)))
    result = {"result_ids": _name(ids or [], data.get("name")), "message": "Loft created"}
elif operation == "extrude_curve":
    direction = data["direction"]
    vector = Vector3d(float(direction[0]), float(direction[1]), float(direction[2]))
    start = Point3d(0, 0, 0)
    end = start + vector
    oid = rs.ExtrudeCurveStraight(data["curve_id"], start, end)
    capped_ok = False
    if oid and data.get("cap") and rs.IsCurveClosed(data["curve_id"]):
        capped = rs.CapPlanarHoles(oid)
        if capped:
            oid = capped
            capped_ok = True
    result = {"result_id": _name([oid], data.get("name"))[0] if oid else None, "capped": capped_ok, "message": "Curve extruded"}
elif operation == "sweep1":
    ids = rs.AddSweep1(data["rail_id"], data["profile_ids"], closed=bool(data.get("closed", False)))
    result = {"result_ids": _name(ids or [], data.get("name")), "message": "Sweep created"}
elif operation == "offset_curve":
    normal = data.get("plane_normal") or [0, 0, 1]
    plane = rs.PlaneFromNormal((0, 0, 0), normal)
    ids = rs.OffsetCurve(data["curve_id"], plane, float(data["distance"]), normal=normal, style=int(data.get("corner_style", 1)))
    if ids and not isinstance(ids, (list, tuple)):
        ids = [ids]
    result = {"result_ids": _name(ids or [], data.get("name")), "message": "Curve offset"}
elif operation == "pipe":
    ids = rs.AddPipe(data["curve_id"], 0, float(data["radius"]), cap=int(bool(data.get("cap", True))) + 1)
    if ids and not isinstance(ids, (list, tuple)):
        ids = [ids]
    result = {"result_ids": _name(ids or [], data.get("name")), "message": "Pipe created"}
else:
    raise ValueError("Unsupported advanced operation: {}".format(operation))

rs.Redraw()
'''

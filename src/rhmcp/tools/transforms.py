"""
Additional transformation tools: mirror, copy, array, orient.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Mirror Objects", destructiveHint=True))
    def mirror_objects(
        ids: list[str] | None = None,
        selected: bool = True,
        plane_origin: list[float] = (0, 0, 0),
        plane_normal: list[float] = (1, 0, 0),
        copy: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Mirror objects across a plane defined by ``plane_origin`` and ``plane_normal``.

        ``copy=True`` keeps the originals. Uses selected objects when ``ids`` is omitted.
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err: return err
        err = validate.coordinate(plane_origin, "plane_origin") or validate.coordinate(plane_normal, "plane_normal")
        if err: return err
        payload = {"op": "mirror", "ids": ids, "selected": selected,
                   "plane_origin": list(plane_origin), "plane_normal": list(plane_normal),
                   "copy": copy}
        code = "__mcp_xf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Copy Objects", destructiveHint=True))
    def copy_objects(
        ids: list[str] | None = None,
        selected: bool = True,
        translation: list[float] = (0, 0, 0),
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Copy objects and move the copies by ``translation`` [dx, dy, dz].
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err: return err
        err = validate.coordinate(translation, "translation")
        if err: return err
        payload = {"op": "copy", "ids": ids, "selected": selected, "translation": list(translation)}
        code = "__mcp_xf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Linear Array", destructiveHint=True))
    def array_linear(
        ids: list[str] | None = None,
        selected: bool = True,
        direction: list[float] = (1, 0, 0),
        count: int = 3,
        spacing: float | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a linear array of ``count`` copies along ``direction``.

        ``spacing`` sets the distance between copies. If omitted, ``direction``
        magnitude is used as spacing.
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err: return err
        err = validate.coordinate(direction, "direction") or validate.positive(count, "count")
        if err: return err
        payload = {"op": "array_linear", "ids": ids, "selected": selected,
                   "direction": list(direction), "count": count, "spacing": spacing}
        code = "__mcp_xf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Polar Array", destructiveHint=True))
    def array_polar(
        ids: list[str] | None = None,
        selected: bool = True,
        center: list[float] = (0, 0, 0),
        count: int = 4,
        angle: float = 360.0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a polar array of ``count`` copies around ``center``.

        ``angle`` is the total sweep in degrees (default 360 = full circle).
        """
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err: return err
        err = validate.coordinate(center, "center") or validate.positive(count, "count")
        if err: return err
        payload = {"op": "array_polar", "ids": ids, "selected": selected,
                   "center": list(center), "count": count, "angle": angle}
        code = "__mcp_xf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Orient Objects", destructiveHint=True))
    def orient_objects(
        ids: list[str] | None = None,
        selected: bool = True,
        reference_point1: list[float] = (0, 0, 0),
        reference_point2: list[float] = (1, 0, 0),
        target_point1: list[float] = (0, 0, 0),
        target_point2: list[float] = (0, 1, 0),
        copy: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Orient objects by aligning a reference vector to a target vector.

        The transformation rotates objects so that the vector from
        ``reference_point1`` → ``reference_point2`` aligns..."""
        if ids is not None:
            err = validate.guid_list(ids, "ids")
            if err: return err
        err = (validate.coordinate(list(reference_point1), "reference_point1") or
               validate.coordinate(list(reference_point2), "reference_point2") or
               validate.coordinate(list(target_point1), "target_point1") or
               validate.coordinate(list(target_point2), "target_point2"))
        if err: return err
        payload = {"op": "orient", "ids": ids, "selected": selected,
                   "ref1": list(reference_point1), "ref2": list(reference_point2),
                   "tgt1": list(target_point1), "tgt2": list(target_point2), "copy": copy}
        code = "__mcp_xf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import math

data = __mcp_xf
op   = data["op"]

def _resolve(ids, selected):
    if ids: return [o for o in ids if rs.IsObject(o)]
    if selected: return rs.SelectedObjects() or []
    return []

objs = _resolve(data.get("ids"), data.get("selected", True))

if op == "mirror":
    origin = Rhino.Geometry.Point3d(*data["plane_origin"])
    normal = Rhino.Geometry.Vector3d(*data["plane_normal"])
    plane  = Rhino.Geometry.Plane(origin, normal)
    xf     = Rhino.Geometry.Transform.Mirror(plane)
    if data.get("copy"):
        new_ids = [rs.CopyObject(o, [0,0,0]) for o in objs]
        for o in new_ids: rs.TransformObject(o, xf)
        result_ids = [str(o) for o in new_ids]
    else:
        for o in objs: rs.TransformObject(o, xf)
        result_ids = [str(o) for o in objs]
    rs.Redraw()
    result = {"ids": result_ids, "count": len(result_ids)}

elif op == "copy":
    t = data["translation"]
    new_ids = rs.CopyObjects(objs, t) or []
    rs.Redraw()
    result = {"ids": [str(o) for o in new_ids], "count": len(new_ids)}

elif op == "array_linear":
    import math
    d = data["direction"]
    spacing = data.get("spacing")
    if spacing is None:
        spacing = math.sqrt(d[0]**2 + d[1]**2 + d[2]**2)
    if spacing == 0: spacing = 1.0
    mag = math.sqrt(d[0]**2 + d[1]**2 + d[2]**2)
    if mag > 0:
        unit = [x/mag for x in d]
    else:
        unit = [1, 0, 0]
    new_ids = []
    for i in range(1, int(data["count"])):
        t = [unit[j] * spacing * i for j in range(3)]
        copies = rs.CopyObjects(objs, t) or []
        new_ids.extend(copies)
    rs.Redraw()
    result = {"ids": [str(o) for o in new_ids], "count": len(new_ids)}

elif op == "array_polar":
    center = Rhino.Geometry.Point3d(*data["center"])
    count  = int(data["count"])
    total_angle = float(data.get("angle", 360))
    step = math.radians(total_angle / count)
    new_ids = []
    for i in range(1, count):
        angle_i = step * i
        xf = Rhino.Geometry.Transform.Rotation(angle_i, Rhino.Geometry.Vector3d.ZAxis, center)
        copies = [rs.CopyObject(o, [0,0,0]) for o in objs]
        for c in copies:
            rs.TransformObject(c, xf)
        new_ids.extend(copies)
    rs.Redraw()
    result = {"ids": [str(o) for o in new_ids], "count": len(new_ids)}

elif op == "orient":
    ref1 = Rhino.Geometry.Point3d(*data["ref1"])
    tgt1 = Rhino.Geometry.Point3d(*data["tgt1"])
    ref_vec = Rhino.Geometry.Vector3d(
        data["ref2"][0]-data["ref1"][0],
        data["ref2"][1]-data["ref1"][1],
        data["ref2"][2]-data["ref1"][2])
    tgt_vec = Rhino.Geometry.Vector3d(
        data["tgt2"][0]-data["tgt1"][0],
        data["tgt2"][1]-data["tgt1"][1],
        data["tgt2"][2]-data["tgt1"][2])
    move = Rhino.Geometry.Transform.Translation(tgt1 - ref1)
    rot  = Rhino.Geometry.Transform.Rotation(ref_vec, tgt_vec, tgt1)
    xf = rot * move
    if data.get("copy"):
        work = [rs.CopyObject(o, [0,0,0]) for o in objs]
    else:
        work = list(objs)
    for o in work:
        rs.TransformObject(o, xf)
    rs.Redraw()
    result = {"ids": [str(o) for o in work], "count": len(work)}
'''

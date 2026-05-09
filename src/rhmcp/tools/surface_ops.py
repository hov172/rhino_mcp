"""
Advanced surface and polysurface creation and editing tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Revolve Curve", destructiveHint=True))
    def revolve_curve(
        curve_id: str,
        axis_start: list[float],
        axis_end: list[float],
        angle: float = 360.0,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Revolve ``curve_id`` around an axis defined by ``axis_start`` → ``axis_end``.

        ``angle`` is in degrees (default 360 = full revolution).
        """
        err = (validate.guid(curve_id, "curve_id") or
               validate.coordinate(axis_start, "axis_start") or
               validate.coordinate(axis_end, "axis_end"))
        if err: return err
        payload = {"op": "revolve", "curve_id": curve_id, "axis_start": axis_start,
                   "axis_end": axis_end, "angle": angle, "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Sweep 2 Rails", destructiveHint=True))
    def sweep2(
        rail1_id: str,
        rail2_id: str,
        profile_ids: list[str],
        closed: bool = False,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Sweep ``profile_ids`` cross-sections along two rails.
        """
        err = (validate.guid(rail1_id, "rail1_id") or
               validate.guid(rail2_id, "rail2_id") or
               validate.guid_list(profile_ids, "profile_ids"))
        if err: return err
        payload = {"op": "sweep2", "rail1_id": rail1_id, "rail2_id": rail2_id,
                   "profile_ids": profile_ids, "closed": closed,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Planar Surface", destructiveHint=True))
    def create_planar_surface(
        curve_ids: list[str],
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Fill a closed planar curve (or curves) with a planar surface.
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        payload = {"op": "planar_srf", "curve_ids": curve_ids, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Edge Surface", destructiveHint=True))
    def create_edge_surface(
        curve_ids: list[str],
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a surface from 2, 3, or 4 edge curves (EdgeSrf).
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        payload = {"op": "edge_srf", "curve_ids": curve_ids, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Network Surface", destructiveHint=True))
    def create_network_surface(
        curve_ids: list[str],
        continuity: int = 1,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Fit a surface through a network of curves.

        ``continuity``: 0 = position, 1 = tangency (default), 2 = curvature.
        """
        err = validate.guid_list(curve_ids, "curve_ids")
        if err: return err
        payload = {"op": "network_srf", "curve_ids": curve_ids,
                   "continuity": continuity, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Patch Surface", destructiveHint=True))
    def create_patch(
        object_ids: list[str],
        u_spans: int = 10,
        v_spans: int = 10,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Fit a patch surface to curves or point clouds.

        ``u_spans`` / ``v_spans`` control the resolution of the patch.
        """
        err = validate.guid_list(object_ids, "object_ids") or validate.positive(u_spans, "u_spans") or validate.positive(v_spans, "v_spans")
        if err: return err
        payload = {"op": "patch", "object_ids": object_ids,
                   "u_spans": u_spans, "v_spans": v_spans, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Offset Surface", destructiveHint=True))
    def offset_surface(
        surface_id: str,
        distance: float,
        both_sides: bool = False,
        solid: bool = False,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Offset a surface by ``distance`` along its normals.
        """
        err = validate.guid(surface_id, "surface_id")
        if err: return err
        payload = {"op": "offset_srf", "surface_id": surface_id, "distance": distance,
                   "both_sides": both_sides, "solid": solid,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Split Brep", destructiveHint=True))
    def split_brep(
        brep_id: str,
        cutter_id: str,
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Split ``brep_id`` with ``cutter_id`` (another brep or surface).
        """
        err = validate.guid(brep_id, "brep_id") or validate.guid(cutter_id, "cutter_id")
        if err: return err
        payload = {"op": "split_brep", "brep_id": brep_id, "cutter_id": cutter_id,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Fillet Surfaces", destructiveHint=True))
    def fillet_surfaces(
        surface1_id: str,
        surface2_id: str,
        radius: float,
        trim: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a fillet surface of ``radius`` between two surfaces.
        """
        err = validate.guid(surface1_id, "surface1_id") or validate.guid(surface2_id, "surface2_id")
        if err: return err
        payload = {"op": "fillet_srf", "surface1_id": surface1_id,
                   "surface2_id": surface2_id, "radius": radius,
                   "trim": trim, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Cap Planar Holes", destructiveHint=True))
    def cap_planar_holes(
        brep_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Cap all planar holes in a polysurface, making it a closed solid.
        """
        err = validate.guid(brep_id, "brep_id")
        if err: return err
        payload = {"op": "cap_holes", "brep_id": brep_id}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Extrude Curve Along Curve", destructiveHint=True))
    def extrude_curve_along_curve(
        curve_id: str,
        path_id: str,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Extrude ``curve_id`` along ``path_id`` (a path curve).
        """
        err = validate.guid(curve_id, "curve_id") or validate.guid(path_id, "path_id")
        if err: return err
        payload = {"op": "extrude_along", "curve_id": curve_id, "path_id": path_id,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Extrude Curve to Point", destructiveHint=True))
    def extrude_curve_to_point(
        curve_id: str,
        point: list[float],
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Extrude ``curve_id`` to a single apex ``point``, creating a cone-like surface.
        """
        err = validate.guid(curve_id, "curve_id") or validate.coordinate(point, "point")
        if err: return err
        payload = {"op": "extrude_to_point", "curve_id": curve_id, "point": point,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Duplicate Edge Curves", destructiveHint=True))
    def duplicate_edge_curves(
        brep_id: str,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Extract all edge curves of a brep/polysurface as new curve objects.
        """
        err = validate.guid(brep_id, "brep_id")
        if err: return err
        payload = {"op": "dup_edges", "brep_id": brep_id, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Duplicate Surface Border", destructiveHint=True))
    def duplicate_surface_border(
        surface_id: str,
        border_type: int = 0,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Duplicate the border curves of a surface.

        ``border_type``: 0 = outer loop, 1 = inner loops, 2 = all.
        """
        err = validate.guid(surface_id, "surface_id")
        if err: return err
        payload = {"op": "dup_border", "surface_id": surface_id,
                   "border_type": border_type, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Join Surfaces", destructiveHint=True))
    def join_surfaces(
        surface_ids: list[str],
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Join multiple surfaces into a single polysurface.
        """
        err = validate.guid_list(surface_ids, "surface_ids")
        if err: return err
        payload = {"op": "join_srfs", "surface_ids": surface_ids,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Explode Polysurface", destructiveHint=True))
    def explode_polysurface(
        brep_id: str,
        delete_input: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Explode a polysurface into its individual surface faces.
        """
        err = validate.guid(brep_id, "brep_id")
        if err: return err
        payload = {"op": "explode_brep", "brep_id": brep_id, "delete_input": delete_input}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Unroll Surface", destructiveHint=True))
    def unroll_surface(
        surface_id: str,
        explode: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Unroll a developable surface flat onto the construction plane.
        """
        err = validate.guid(surface_id, "surface_id")
        if err: return err
        payload = {"op": "unroll", "surface_id": surface_id, "explode": explode, "name": name}
        code = "__mcp_surf = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import math

data = __mcp_surf
op   = data["op"]
name = data.get("name")

def _n(ids):
    out = []
    for i, oid in enumerate(ids or []):
        if name:
            rs.ObjectName(oid, name if len(ids) == 1 else "{}_{}".format(name, i + 1))
        out.append(str(oid))
    return out

def _s(oid):
    if oid and name: rs.ObjectName(oid, name)
    return str(oid) if oid else None

if op == "revolve":
    import math
    p1  = Rhino.Geometry.Point3d(*data["axis_start"])
    p2  = Rhino.Geometry.Point3d(*data["axis_end"])
    ang = math.radians(float(data.get("angle", 360)))
    oid = rs.AddRevSrf(data["curve_id"], (p1, p2), ang, 0)
    if data.get("delete_input"): rs.DeleteObject(data["curve_id"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "sweep2":
    ids = rs.AddSweep2(data["rail1_id"], data["rail2_id"],
                       data["profile_ids"], data.get("closed", False))
    if data.get("delete_input"):
        for oid in [data["rail1_id"], data["rail2_id"]] + list(data["profile_ids"]):
            rs.DeleteObject(oid)
    rs.Redraw()
    result = {"ids": _n(ids)}

elif op == "planar_srf":
    ids = rs.AddPlanarSrf(data["curve_ids"])
    rs.Redraw()
    result = {"ids": _n(ids)}

elif op == "edge_srf":
    oid = rs.AddEdgeSrf(data["curve_ids"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "network_srf":
    oid = rs.AddNetworkSrf(data["curve_ids"], data.get("continuity", 1))
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "patch":
    oid = rs.AddPatch(data["object_ids"], data.get("u_spans", 10), data.get("v_spans", 10))
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "offset_srf":
    oid = rs.OffsetSurface(data["surface_id"], float(data["distance"]),
                           both_sides=data.get("both_sides", False),
                           create_solid=data.get("solid", False))
    if data.get("delete_input"): rs.DeleteObject(data["surface_id"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "split_brep":
    ids = rs.SplitBrep(data["brep_id"], data["cutter_id"],
                       delete_input=data.get("delete_input", True))
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "fillet_srf":
    ids = rs.FilletSurface(data["surface1_id"], data["surface2_id"],
                           float(data["radius"]), trim=data.get("trim", True))
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "cap_holes":
    oid = rs.CapPlanarHoles(data["brep_id"])
    rs.Redraw()
    result = {"id": _s(oid), "is_solid": bool(oid and rs.IsPolysurfaceClosed(oid))}

elif op == "extrude_along":
    oid = rs.ExtrudeCurveAlongCurve(data["curve_id"], data["path_id"])
    if data.get("delete_input"):
        rs.DeleteObject(data["curve_id"]); rs.DeleteObject(data["path_id"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "extrude_to_point":
    pt  = Rhino.Geometry.Point3d(*data["point"])
    oid = rs.ExtrudeCurvePoint(data["curve_id"], pt)
    if data.get("delete_input"): rs.DeleteObject(data["curve_id"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "dup_edges":
    ids = rs.DuplicateEdgeCurves(data["brep_id"])
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "dup_border":
    ids = rs.DuplicateSurfaceBorder(data["surface_id"], data.get("border_type", 0))
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "join_srfs":
    oid = rs.JoinSurfaces(data["surface_ids"],
                          delete_input=data.get("delete_input", True))
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "explode_brep":
    ids = rs.ExplodePolysurfaces(data["brep_id"],
                                  delete_input=data.get("delete_input", True))
    rs.Redraw()
    result = {"ids": _n(ids or []), "count": len(ids or [])}

elif op == "unroll":
    ids = rs.UnrollSurface(data["surface_id"], explode=data.get("explode", False))
    rs.Redraw()
    result = {"ids": _n(ids or [])}
'''

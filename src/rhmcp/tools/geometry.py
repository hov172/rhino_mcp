"""
Structured Rhino geometry creation tools.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


_GEOMETRY_SCRIPT = r'''
import math
import rhinoscriptsyntax as rs
import Rhino
import System

def _pt(value, default=(0, 0, 0)):
    if value is None:
        value = default
    if len(value) == 2:
        return (value[0], value[1], 0)
    return tuple(value)

def _color(value):
    if value is None:
        return None
    return tuple(int(v) for v in value[:3])

def _ensure_layer(name, color=None):
    if not name:
        return None
    if not rs.IsLayer(name):
        rs.AddLayer(name, color=_color(color) or (200, 200, 200))
    return name

def _assign_color_material(doc, object_id, r_val, g_val, b_val):
    """Create/find MCP_Color material and assign to object so it shows in Shaded mode."""
    _hex = "{:02X}{:02X}{:02X}".format(r_val, g_val, b_val)
    _mat_name = "MCP_Color_{}".format(_hex)
    _mat_idx = -1
    for _i, _m in enumerate(doc.Materials):
        if not _m.IsDeleted and _m.Name == _mat_name:
            _mat_idx = _i
            break
    if _mat_idx == -1:
        _mat_idx = doc.Materials.Add()
        _nm = doc.Materials[_mat_idx]
        _nm.Name = _mat_name
        _nm.DiffuseColor = System.Drawing.Color.FromArgb(r_val, g_val, b_val)
        _nm.CommitChanges()
    _sys_color = System.Drawing.Color.FromArgb(r_val, g_val, b_val)
    _obj = doc.Objects.FindId(object_id)
    if _obj:
        _attr = _obj.Attributes.Duplicate()
        _attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromObject
        _attr.ObjectColor = _sys_color
        _attr.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        _attr.MaterialIndex = _mat_idx
        doc.Objects.ModifyAttributes(_obj, _attr, True)

def _apply_common(object_id, spec):
    if not object_id:
        return None
    name = spec.get("name")
    if name:
        rs.ObjectName(object_id, name)
    layer = _ensure_layer(spec.get("layer"), spec.get("layer_color"))
    if layer:
        rs.ObjectLayer(object_id, layer)
    color = _color(spec.get("color"))
    if color:
        _doc = Rhino.RhinoDoc.ActiveDoc
        _assign_color_material(_doc, object_id, color[0], color[1], color[2])
    return str(object_id)

def _box_corners(center, size):
    cx, cy, cz = _pt(center)
    sx, sy, sz = size
    x0, x1 = cx - sx / 2.0, cx + sx / 2.0
    y0, y1 = cy - sy / 2.0, cy + sy / 2.0
    z0, z1 = cz - sz / 2.0, cz + sz / 2.0
    return [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]

def _create(spec):
    kind = str(spec.get("type", "")).lower()
    params = spec.get("params") or {}
    object_id = None

    if kind == "point":
        object_id = rs.AddPoint(_pt(params.get("point") or params.get("location")))
    elif kind == "line":
        object_id = rs.AddLine(_pt(params.get("start")), _pt(params.get("end"), (1, 0, 0)))
    elif kind == "polyline":
        object_id = rs.AddPolyline([_pt(p) for p in params.get("points", [])])
    elif kind in {"curve", "nurbs_curve", "interpolated_curve"}:
        object_id = rs.AddCurve([_pt(p) for p in params.get("points", [])], int(params.get("degree", 3)))
    elif kind == "circle":
        object_id = rs.AddCircle(_pt(params.get("center")), float(params.get("radius", 1)))
    elif kind == "ellipse":
        plane = rs.MovePlane(rs.WorldXYPlane(), _pt(params.get("center")))
        object_id = rs.AddEllipse(
            plane,
            float(params.get("radius_x", params.get("x_radius", 1))),
            float(params.get("radius_y", params.get("y_radius", 0.5))),
        )
    elif kind == "arc":
        if params.get("center") is not None and params.get("radius") is not None:
            # Center/radius/angle form (matches C# plugin convention)
            cx, cy, cz = _pt(params.get("center"))
            r = float(params.get("radius", 1))
            start_angle = math.radians(float(params.get("start_angle", 0)))
            end_angle = math.radians(float(params.get("end_angle", 90)))
            start_pt = [cx + r*math.cos(start_angle), cy + r*math.sin(start_angle), cz]
            mid_angle = (start_angle + end_angle) / 2
            mid_pt = [cx + r*math.cos(mid_angle), cy + r*math.sin(mid_angle), cz]
            end_pt = [cx + r*math.cos(end_angle), cy + r*math.sin(end_angle), cz]
            object_id = rs.AddArc3Pt(start_pt, end_pt, mid_pt)
        else:
            # 3-point form
            object_id = rs.AddArc3Pt(_pt(params.get("start")), _pt(params.get("end")), _pt(params.get("point_on_arc")))
    elif kind == "sphere":
        object_id = rs.AddSphere(_pt(params.get("center")), float(params.get("radius", 1)))
    elif kind == "ellipsoid":
        object_id = rs.AddEllipsoid(_pt(params.get("center")), params.get("radius_x", 1), params.get("radius_y", 1), params.get("radius_z", 1))
    elif kind == "box":
        object_id = rs.AddBox(_box_corners(params.get("center"), params.get("size", (1, 1, 1))))
    elif kind == "cylinder":
        object_id = rs.AddCylinder(_pt(params.get("base")), float(params.get("height", 1)), float(params.get("radius", 1)), cap=bool(params.get("cap", True)))
    elif kind == "cone":
        object_id = rs.AddCone(_pt(params.get("base")), float(params.get("height", 1)), float(params.get("radius", 1)), cap=bool(params.get("cap", True)))
    elif kind == "torus":
        object_id = rs.AddTorus(_pt(params.get("center")), float(params.get("major_radius", 2)), float(params.get("minor_radius", 0.5)))
    elif kind == "plane_surface":
        object_id = rs.AddPlaneSurface(rs.WorldXYPlane(), float(params.get("width", 1)), float(params.get("height", 1)))
        if params.get("center"):
            rs.MoveObject(object_id, _pt(params.get("center")))
    elif kind in {"plane", "plane_surface_oriented"}:
        center = _pt(params.get("center", [0, 0, 0]))
        width = float(params.get("width", 1.0))
        height = float(params.get("height", 1.0))
        normal = params.get("normal", [0, 0, 1])
        nx, ny, nz = float(normal[0]), float(normal[1]), float(normal[2])
        # find x_axis perpendicular to normal
        if abs(nx) < 0.9:
            x_axis = [1, 0, 0]
        else:
            x_axis = [0, 1, 0]
        # cross product: y_axis = normal x x_axis
        yx = ny*x_axis[2] - nz*x_axis[1]
        yy = nz*x_axis[0] - nx*x_axis[2]
        yz = nx*x_axis[1] - ny*x_axis[0]
        # re-orthogonalize x_axis = y_axis x normal
        xx = yy*nz - yz*ny
        xy = yz*nx - yx*nz
        xz = yx*ny - yy*nx
        # normalize
        xl = math.sqrt(xx**2 + xy**2 + xz**2)
        yl = math.sqrt(yx**2 + yy**2 + yz**2)
        xx, xy, xz = xx/xl, xy/xl, xz/xl
        yx, yy, yz = yx/yl, yy/yl, yz/yl
        cx, cy, cz = center
        hw, hh = width/2, height/2
        p0 = [cx - hw*xx - hh*yx, cy - hw*xy - hh*yy, cz - hw*xz - hh*yz]
        p1 = [cx + hw*xx - hh*yx, cy + hw*xy - hh*yy, cz + hw*xz - hh*yz]
        p2 = [cx + hw*xx + hh*yx, cy + hw*xy + hh*yy, cz + hw*xz + hh*yz]
        p3 = [cx - hw*xx + hh*yx, cy - hw*xy + hh*yy, cz - hw*xz + hh*yz]
        object_id = rs.AddSrfPt([p0, p1, p2, p3])
    elif kind in {"surface", "surface_from_points"}:
        points_raw = params.get("points", [])
        count = params.get("count", None)
        if count and len(points_raw) >= count[0] * count[1]:
            # Grid-based NurbsSurface matching the C# handler convention
            u_count, v_count = int(count[0]), int(count[1])
            degree_param = params.get("degree", [3, 3])
            if isinstance(degree_param, list):
                default_ud, default_vd = degree_param[0], degree_param[1]
            else:
                default_ud = default_vd = degree_param
            u_degree = int(params.get("u_degree", default_ud))
            v_degree = int(params.get("v_degree", default_vd))
            u_closed = bool(params.get("u_closed", False))
            v_closed = bool(params.get("v_closed", False))
            import Rhino.Geometry as rg
            import scriptcontext as sc
            import System
            pt_list = [rg.Point3d(*p) for p in points_raw[:u_count * v_count]]
            srf = rg.NurbsSurface.CreateThroughPoints(
                pt_list, u_count, v_count,
                min(u_degree, u_count - 1), min(v_degree, v_count - 1),
                u_closed, v_closed
            )
            if srf is not None:
                guid = sc.doc.Objects.AddSurface(srf)
                object_id = guid if guid != System.Guid.Empty else None
            else:
                object_id = None
        else:
            # Fallback: simple AddSrfPt for 3–4 corner points
            object_id = rs.AddSrfPt([_pt(p) for p in points_raw])
    elif kind == "mesh":
        object_id = rs.AddMesh([_pt(p) for p in params.get("vertices", [])], params.get("faces", []))
    elif kind == "text":
        object_id = rs.AddText(str(params.get("text", "")), _pt(params.get("point")), float(params.get("height", 1)))
    elif kind in {"pointcloud", "point_cloud"}:
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        cloud = rg.PointCloud([rg.Point3d(*_pt(pp)) for pp in params.get("points", [])])
        guid = sc.doc.Objects.AddPointCloud(cloud)
        object_id = guid if guid != System.Guid.Empty else None
    elif kind == "textdot":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        dot = rg.TextDot(str(params.get("text", "•")), rg.Point3d(*_pt(params.get("point") or params.get("location"))))
        fs = params.get("font_size", 0)
        if fs: dot.FontHeight = int(fs)
        guid = sc.doc.Objects.AddTextDot(dot)
        object_id = guid if guid != System.Guid.Empty else None
    elif kind == "light":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        light = rg.Light()
        style = str(params.get("light_style", "point")).lower()
        light.LightStyle = {
            "directional": rg.LightStyle.WorldDirectional,
            "spot": rg.LightStyle.WorldSpot,
            "linear": rg.LightStyle.WorldLinear,
            "rectangular": rg.LightStyle.WorldRectangular,
            "area": rg.LightStyle.WorldRectangular,
        }.get(style, rg.LightStyle.WorldPoint)
        loc = params.get("location") or params.get("position") or [0, 0, 10]
        light.Location = rg.Point3d(*_pt(loc))
        light.Intensity = float(params.get("intensity", 1.0))
        dc = params.get("diffuse_color")
        if dc and len(dc) >= 3:
            import System.Drawing as sd
            light.Diffuse = sd.Color.FromArgb(int(dc[0]), int(dc[1]), int(dc[2]))
        d = params.get("direction")
        if d and len(d) >= 3:
            light.Direction = rg.Vector3d(float(d[0]), float(d[1]), float(d[2]))
        idx = sc.doc.Lights.Add(light)
        object_id = sc.doc.Lights[idx].Id if idx >= 0 else None
    elif kind == "extrusion":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        profile = None
        pid = params.get("profile_id") or params.get("curve_id")
        if pid:
            try:
                obj = sc.doc.Objects.FindId(System.Guid(pid))
                if obj: profile = obj.Geometry
            except Exception:
                pass
        if profile is None:
            pts = params.get("points", [])
            if len(pts) >= 3:
                pl = rg.Polyline([rg.Point3d(*_pt(pp)) for pp in pts])
                pl.Add(pl[0])
                profile = pl.ToNurbsCurve()
        if profile:
            ext = rg.Extrusion.Create(profile, float(params.get("height", 1)), bool(params.get("cap", True)))
            if ext:
                guid = sc.doc.Objects.AddExtrusion(ext)
                object_id = guid if guid != System.Guid.Empty else None
    elif kind in {"block_insert", "instance", "instance_reference"}:
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        block_name = params.get("block_name") or params.get("definition_name") or ""
        defn = sc.doc.InstanceDefinitions.Find(block_name, True)
        if defn:
            pos = _pt(params.get("position") or params.get("location"))
            xf = rg.Transform.Translation(pos[0], pos[1], pos[2])
            guid = sc.doc.Objects.AddInstanceObject(defn.Index, xf)
            object_id = guid if guid != System.Guid.Empty else None
    elif kind == "dimension_linear":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        start = _pt(params.get("start"))
        end   = _pt(params.get("end", (1, 0, 0)))
        offset = float(params.get("offset", 0.5))
        plane  = rg.Plane(rg.Point3d(0, 0, start[2]), rg.Vector3d.XAxis, rg.Vector3d.YAxis)
        ext1   = rg.Point2d(start[0], start[1])
        ext2   = rg.Point2d(end[0],   end[1])
        mid_x  = (start[0] + end[0]) / 2.0
        dim_pt = rg.Point2d(mid_x, max(start[1], end[1]) + offset)
        dim    = rg.LinearDimension(plane, ext1, ext2, dim_pt)
        guid   = sc.doc.Objects.Add(dim, sc.doc.CreateDefaultAttributes())
        object_id = guid if guid != System.Guid.Empty else None
    elif kind == "leader":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        raw_pts = params.get("points", [])
        if len(raw_pts) >= 2:
            text   = str(params.get("text", ""))
            pt3ds  = [rg.Point3d(*_pt(pp)) for pp in raw_pts]
            # AddLeader(string text, IEnumerable<Point3d>) auto-derives annotation plane
            guid   = sc.doc.Objects.AddLeader(text, pt3ds)
            object_id = guid if guid != System.Guid.Empty else None
    elif kind == "cage":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        c = _pt(params.get("center", (0, 0, 0)))
        w, d, h = float(params.get("width", 2)), float(params.get("depth", 2)), float(params.get("height", 2))
        plane = rg.Plane(rg.Point3d(*c), rg.Vector3d.ZAxis)
        box   = rg.Box(plane, rg.Interval(-w/2, w/2), rg.Interval(-d/2, d/2), rg.Interval(-h/2, h/2))
        guid  = sc.doc.Objects.AddBrep(box.ToBrep())
        object_id = guid if guid != System.Guid.Empty else None
    elif kind in {"morphcontrol", "morph_control"}:
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        src_id = params.get("source_curve_id") or params.get("source_id")
        tgt_id = params.get("target_curve_id") or params.get("target_id")
        if src_id and tgt_id:
            try:
                src_obj = sc.doc.Objects.FindId(System.Guid(src_id))
                tgt_obj = sc.doc.Objects.FindId(System.Guid(tgt_id))
                if src_obj and tgt_obj:
                    src_nurbs = src_obj.Geometry.ToNurbsCurve()
                    tgt_nurbs = tgt_obj.Geometry.ToNurbsCurve()
                    mc   = rg.MorphControl(src_nurbs, tgt_nurbs)
                    guid = sc.doc.Objects.AddMorphControl(mc)
                    object_id = guid if guid != System.Guid.Empty else None
            except Exception:
                pass
    elif kind == "subd":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        mesh_id = params.get("mesh_id")
        opts = rg.SubDCreationOptions()
        opts.InterpolateMeshVertices = False
        if mesh_id:
            try:
                mesh_obj = sc.doc.Objects.FindId(System.Guid(mesh_id))
                if mesh_obj and isinstance(mesh_obj.Geometry, rg.Mesh):
                    subd = rg.SubD.CreateFromMesh(mesh_obj.Geometry, opts)
                    if subd:
                        guid = sc.doc.Objects.AddSubD(subd)
                        object_id = guid if guid != System.Guid.Empty else None
            except Exception:
                pass
        else:
            c  = _pt(params.get("center", (0, 0, 0)))
            sx = float(params.get("width",  2.0))
            sy = float(params.get("depth",  2.0))
            sz = float(params.get("height", 2.0))
            seg = max(1, int(params.get("segments", 1)))
            plane = rg.Plane(rg.Point3d(*c), rg.Vector3d.ZAxis)
            box   = rg.Box(plane, rg.Interval(-sx/2, sx/2), rg.Interval(-sy/2, sy/2), rg.Interval(-sz/2, sz/2))
            mesh  = rg.Mesh.CreateFromBox(box, seg, seg, seg)
            subd  = rg.SubD.CreateFromMesh(mesh, opts)
            if subd:
                guid = sc.doc.Objects.AddSubD(subd)
                object_id = guid if guid != System.Guid.Empty else None
    elif kind == "hatch":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        boundary = None
        curve_id = params.get("curve_id")
        if curve_id:
            try:
                c_obj = sc.doc.Objects.FindId(System.Guid(curve_id))
                if c_obj:
                    boundary = c_obj.Geometry
            except Exception:
                pass
        if boundary is None:
            c = _pt(params.get("center", (0, 0, 0)))
            w = float(params.get("width", 2.0))
            h = float(params.get("height", 2.0))
            rect = rg.Rectangle3d(rg.Plane(rg.Point3d(*c), rg.Vector3d.ZAxis),
                                   rg.Interval(-w/2, w/2), rg.Interval(-h/2, h/2))
            boundary = rect.ToNurbsCurve()
        pat_name  = params.get("pattern", "Solid")
        pat_idx   = sc.doc.HatchPatterns.Find(pat_name, True)
        if pat_idx < 0:
            pat_idx = sc.doc.HatchPatterns.CurrentHatchPatternIndex
        import math
        rotation = float(params.get("rotation", 0.0)) * math.pi / 180.0
        scale    = float(params.get("scale", 1.0))
        hatches  = rg.Hatch.Create(boundary, pat_idx, rotation, scale)
        if hatches and len(hatches) > 0:
            guid = sc.doc.Objects.AddHatch(hatches[0])
            object_id = guid if guid != System.Guid.Empty else None
    elif kind in {"clipping_plane", "clippingplane"}:
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        origin = _pt(params.get("origin") or params.get("center", (0, 0, 0)))
        n = params.get("normal")
        if n:
            normal = rg.Vector3d(*[float(x) for x in n])
        else:
            normal = rg.Vector3d.ZAxis
        normal.Unitize()
        plane  = rg.Plane(rg.Point3d(*origin), normal)
        w      = float(params.get("width",  10.0))
        h      = float(params.get("height", 10.0))
        vp_ids = [v.ActiveViewportID for v in sc.doc.Views]
        if not vp_ids:
            vp_ids = [sc.doc.Views.ActiveView.ActiveViewportID]
        guid = sc.doc.Objects.AddClippingPlane(plane, w, h, vp_ids)
        object_id = guid if guid != System.Guid.Empty else None
    elif kind == "dimension_radial":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        import math
        c      = _pt(params.get("center", (0, 0, 0)))
        radius = float(params.get("radius", 1.0))
        angle  = float(params.get("angle", 45.0)) * math.pi / 180.0
        offset = float(params.get("offset", radius * 0.5))
        is_dia = bool(params.get("is_diameter", False))
        center_pt = rg.Point3d(*c)
        rad_pt    = center_pt + rg.Vector3d(math.cos(angle)*radius, math.sin(angle)*radius, 0)
        dim_pt    = center_pt + rg.Vector3d(math.cos(angle)*(radius+offset), math.sin(angle)*(radius+offset), 0)
        plane     = rg.Plane(center_pt, rg.Vector3d.ZAxis)
        ann_type  = rg.AnnotationType.Diameter if is_dia else rg.AnnotationType.Radius
        dim       = rg.RadialDimension(ann_type, plane, center_pt, rad_pt, dim_pt)
        guid      = sc.doc.Objects.Add(dim, sc.doc.CreateDefaultAttributes())
        object_id = guid if guid != System.Guid.Empty else None
    elif kind == "dimension_angular":
        import Rhino.Geometry as rg
        import scriptcontext as sc
        import System
        import math
        c         = _pt(params.get("center", (0, 0, 0)))
        radius    = float(params.get("radius", 2.0))
        start_deg = float(params.get("start_angle", 0.0))
        end_deg   = float(params.get("end_angle", 90.0))
        offset    = float(params.get("offset", radius * 0.3))
        start_rad = start_deg * math.pi / 180.0
        end_rad   = end_deg   * math.pi / 180.0
        plane     = rg.Plane(rg.Point3d(*c), rg.Vector3d.ZAxis)
        arc       = rg.Arc(plane, radius, rg.Interval(start_rad, end_rad))
        dim       = rg.AngularDimension(arc, offset)
        guid      = sc.doc.Objects.Add(dim, sc.doc.CreateDefaultAttributes())
        object_id = guid if guid != System.Guid.Empty else None
    else:
        raise ValueError("Unsupported geometry type: {}".format(kind))

    return _apply_common(object_id, spec)

created = []
for item in __mcp_scene_items:
    created.append(_create(item))

rs.Redraw()
result = {"created": created, "count": len([item for item in created if item])}
'''


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Create Rhino Geometry", destructiveHint=True))
    def create_rhino_geometry(
        geometry_type: str,
        params: dict[str, Any],
        name: str | None = None,
        layer: str | None = None,
        color: list[int] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create one Rhino object from structured parameters.

        Supported types: point, line, polyline, curve, nurbs_curve, circle,
        ellipse, arc, sphere, ellipsoid, box, cylinder, cone, torus,
        plane_surface, plane, surface, surface_from_points, mesh, text,
        pointcloud, textdot, light, extrusion, block_insert,
        dimension_linear, dimension_radial, dimension_angular, leader, cage,
        morphcontrol, subd, hatch, clipping_plane.

        **arc** — two calling conventions:
          - 3-point form: ``start=[x,y,z]``, ``end=[x,y,z]``,
            ``point_on_arc=[x,y,z]``
          - Center/radius form (matches C# plugin): ``center=[x,y,z]``,
            ``radius=<float>``, ``start_angle=<deg, default 0>``,
            ``end_angle=<deg, default 90>``

        **plane** (alias: ``plane_surface_oriented``) — flat oriented surface:
          ``center=[x,y,z]``, ``width=<float>``, ``height=<float>``,
          ``normal=[nx,ny,nz]`` (default ``[0,0,1]``)

        **surface** / **surface_from_points** — grid-based NurbsSurface when
        ``count=[u,v]`` is supplied (matches C# handler); falls back to
        ``AddSrfPt`` for 3–4 corner points without a count:
          ``points=[[x,y,z], ...]``, ``count=[u_count, v_count]``,
          ``u_degree=<int, default 3>``, ``v_degree=<int, default 3>``,
          ``u_closed=<bool>``, ``v_closed=<bool>``
        """
        if color is not None:
            err = validate.color(color, "color")
            if err:
                return err
        item = {
            "type": geometry_type,
            "params": params,
            "name": name,
            "layer": layer,
            "color": color,
        }
        return _run_scene([item], rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Rhino Scene", destructiveHint=True))
    def create_rhino_scene(items: list[dict[str, Any]], rhino_id: str | None = None) -> dict[str, object]:
        """
        Create multiple Rhino objects from a list of structured item specs.

        Each item accepts ``type``, ``params``, and optional ``name``, ``layer``,
        ``layer_color``, and ``color`` keys.
        """
        return _run_scene(items, rhino_id)


def _run_scene(items: list[dict[str, Any]], rhino_id: str | None) -> dict[str, object]:
    code = "__mcp_scene_items = {!s}\n{}".format(json.dumps(items), _GEOMETRY_SCRIPT)
    result = rhino.execute_python(code, rhino_id=rhino_id)
    if result.get("ok"):
        return result

    command_results = []
    unsupported = []
    for item in items:
        command = _command_for_item(item)
        if command is None:
            unsupported.append(item.get("type"))
            continue
        command_results.append(rhino.run_command(command, rhino_id=rhino_id))
    return {
        "ok": bool(command_results) and all(item["ok"] for item in command_results),
        "backend": "rhino-command",
        "created": len(command_results),
        "unsupported": unsupported,
        "commands": command_results,
        "python_attempt": result,
    }


def _command_for_item(item: dict[str, Any]) -> str | None:
    kind = str(item.get("type", "")).lower()
    params = item.get("params") or {}

    def pt(value: Any, default: tuple[float, float, float] = (0, 0, 0)) -> str:
        if value is None:
            value = default
        if len(value) == 2:
            value = [value[0], value[1], 0]
        return "{},{},{}".format(value[0], value[1], value[2])

    if kind == "point":
        return "_Point {}".format(pt(params.get("point") or params.get("location")))
    if kind == "line":
        return "_Line {} {}".format(pt(params.get("start")), pt(params.get("end"), (1, 0, 0)))
    if kind == "circle":
        return "_Circle {} {}".format(pt(params.get("center")), float(params.get("radius", 1)))
    if kind == "sphere":
        return "_Sphere {} {}".format(pt(params.get("center")), float(params.get("radius", 1)))
    if kind == "cylinder":
        base = params.get("base") or [0, 0, 0]
        height = float(params.get("height", 1))
        top = [base[0], base[1], (base[2] if len(base) > 2 else 0) + height]
        return "_Cylinder {} {} {}".format(pt(base), pt(top), float(params.get("radius", 1)))
    if kind == "cone":
        base = params.get("base") or [0, 0, 0]
        height = float(params.get("height", 1))
        top = [base[0], base[1], (base[2] if len(base) > 2 else 0) + height]
        return "_Cone {} {} {}".format(pt(base), pt(top), float(params.get("radius", 1)))
    if kind == "text":
        text = str(params.get("text", "")).replace('"', "'")
        return '_TextObject "{}" {} {}'.format(text, pt(params.get("point")), float(params.get("height", 1)))
    return None

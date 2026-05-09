"""
Mesh creation and editing tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Create Mesh", destructiveHint=True))
    def create_mesh(
        vertices: list[list[float]],
        faces: list[list[int]],
        name: str | None = None,
        layer: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a mesh from explicit ``vertices`` (list of [x,y,z]) and ``faces``
        (list of [i,j,k] or [i,j,k,l] index lists). Triangles and quads supported.
        """
        payload = {"op": "create", "vertices": vertices, "faces": faces,
                   "name": name, "layer": layer}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Planar Mesh", destructiveHint=True))
    def create_planar_mesh(
        curve_id: str,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a planar mesh from a closed planar curve.
        """
        payload = {"op": "planar", "curve_id": curve_id, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Mesh from Surface", destructiveHint=True))
    def mesh_from_surface(
        object_ids: list[str],
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Convert brep/surface objects to meshes using Rhino's default meshing.
        """
        payload = {"op": "from_srf", "object_ids": object_ids, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Mesh Boolean Union", destructiveHint=True))
    def mesh_boolean_union(
        mesh_ids: list[str],
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Boolean union of two or more meshes.
        """
        payload = {"op": "bool_union", "mesh_ids": mesh_ids,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Mesh Boolean Difference", destructiveHint=True))
    def mesh_boolean_difference(
        input_ids: list[str],
        subtract_ids: list[str],
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Subtract ``subtract_ids`` meshes from ``input_ids`` meshes.
        """
        payload = {"op": "bool_diff", "input_ids": input_ids,
                   "subtract_ids": subtract_ids, "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Mesh Boolean Intersection", destructiveHint=True))
    def mesh_boolean_intersection(
        mesh_ids1: list[str],
        mesh_ids2: list[str],
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Boolean intersection of two sets of meshes.
        """
        payload = {"op": "bool_intersect", "mesh_ids1": mesh_ids1,
                   "mesh_ids2": mesh_ids2, "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Join Meshes", destructiveHint=True))
    def join_meshes(
        mesh_ids: list[str],
        delete_input: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Join multiple meshes into a single mesh object.
        """
        payload = {"op": "join", "mesh_ids": mesh_ids,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Mesh to NURBS", destructiveHint=True))
    def mesh_to_nurbs(
        mesh_id: str,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Convert a mesh to a NURBS polysurface (one face per mesh polygon).
        """
        payload = {"op": "to_nurbs", "mesh_id": mesh_id,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Offset Mesh", destructiveHint=True))
    def mesh_offset(
        mesh_id: str,
        distance: float,
        delete_input: bool = False,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Offset a mesh by ``distance`` along its face normals.
        """
        payload = {"op": "offset", "mesh_id": mesh_id, "distance": distance,
                   "delete_input": delete_input, "name": name}
        code = "__mcp_mesh = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

data = __mcp_mesh
op   = data["op"]
name = data.get("name")

def _s(oid):
    if oid and name: rs.ObjectName(oid, name)
    if oid and data.get("layer"):
        lyr = data["layer"]
        if not rs.IsLayer(lyr): rs.AddLayer(lyr)
        rs.ObjectLayer(oid, lyr)
    return str(oid) if oid else None

def _n(ids):
    out = []
    for i, oid in enumerate(ids or []):
        if name:
            rs.ObjectName(oid, name if len(ids) == 1 else "{}_{}".format(name, i + 1))
        out.append(str(oid))
    return out

if op == "create":
    mesh = Rhino.Geometry.Mesh()
    for v in data["vertices"]:
        mesh.Vertices.Add(float(v[0]), float(v[1]), float(v[2]))
    for f in data["faces"]:
        if len(f) == 3:
            mesh.Faces.AddFace(int(f[0]), int(f[1]), int(f[2]))
        else:
            mesh.Faces.AddFace(int(f[0]), int(f[1]), int(f[2]), int(f[3]))
    mesh.Normals.ComputeNormals()
    mesh.Compact()
    oid = Rhino.RhinoDoc.ActiveDoc.Objects.AddMesh(mesh)
    rs.Redraw()
    result = {"id": _s(oid), "vertex_count": len(data["vertices"]), "face_count": len(data["faces"])}

elif op == "planar":
    srf_ids = rs.AddPlanarSrf([data["curve_id"]])
    if srf_ids:
        oid = rs.MeshBrep(srf_ids[0])
        rs.DeleteObject(srf_ids[0])
        rs.Redraw()
        result = {"id": _s(oid[0] if oid else None)}
    else:
        result = {"ok": False, "error": "Could not create planar surface from curve"}

elif op == "from_srf":
    ids = []
    for sid in data["object_ids"]:
        meshes = rs.MeshBrep(sid)
        ids.extend(meshes or [])
    rs.Redraw()
    result = {"ids": _n(ids), "count": len(ids)}

elif op == "bool_union":
    ids = rs.MeshBooleanUnion(data["mesh_ids"])
    if data.get("delete_input"):
        for mid in data["mesh_ids"]: rs.DeleteObject(mid)
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "bool_diff":
    ids = rs.MeshBooleanDifference(data["input_ids"], data["subtract_ids"])
    if data.get("delete_input"):
        for mid in data["input_ids"] + data["subtract_ids"]: rs.DeleteObject(mid)
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "bool_intersect":
    ids = rs.MeshBooleanIntersection(data["mesh_ids1"], data["mesh_ids2"])
    if data.get("delete_input"):
        for mid in data["mesh_ids1"] + data["mesh_ids2"]: rs.DeleteObject(mid)
    rs.Redraw()
    result = {"ids": _n(ids or [])}

elif op == "join":
    oid = rs.JoinMeshes(data["mesh_ids"],
                        delete_input=data.get("delete_input", True))
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "to_nurbs":
    oid = rs.MeshToNurb(data["mesh_id"])
    if data.get("delete_input"): rs.DeleteObject(data["mesh_id"])
    rs.Redraw()
    result = {"id": _s(oid)}

elif op == "offset":
    oid = rs.OffsetMesh(data["mesh_id"], float(data["distance"]))
    if data.get("delete_input"): rs.DeleteObject(data["mesh_id"])
    rs.Redraw()
    result = {"id": _s(oid)}
'''

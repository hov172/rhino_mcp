"""
Tools for Rhino material management.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Get Rhino Materials", readOnlyHint=True))
    def get_materials(rhino_id: str | None = None) -> dict[str, object]:
        """
        Return all non-deleted materials in the document.

        Each material entry includes: index, name, diffuse, specular, emission,
        shininess (0-255), and transparency (0.0-1.0).
        """
        plugin = _try_plugin("get_materials", {})
        if plugin:
            return plugin
        return rhino.execute_python(_GET_MATERIALS_SCRIPT, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Rhino Material", destructiveHint=True))
    def create_material(
        name: str,
        diffuse: list[int] | None = None,
        color: list[int] | None = None,
        specular: list[int] | None = None,
        emission: list[int] | None = None,
        shininess: int = 0,
        transparency: float = 0.0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a new Rhino material with the specified properties.

        ``diffuse`` (or ``color``) — RGB list [r, g, b] with values 0-255.
        ``specular`` — RGB list [r, g, b] with values 0-255.
        ``emission`` — RGB list [r, g, b] with values 0-255.
        ``shininess`` — integer 0-255; higher values produce a sharper highlight.
        ``transparency`` — float 0.0 (opaque) to 1.0 (fully transparent).
        """
        # Resolve diffuse vs color alias; diffuse wins if both provided.
        resolved_diffuse = diffuse if diffuse is not None else color

        # Validate color arrays.
        for label, arr in [("diffuse/color", resolved_diffuse), ("specular", specular), ("emission", emission)]:
            if arr is not None and len(arr) != 3:
                return {"ok": False, "error": "Parameter '{}' must be a list of exactly 3 integers [r, g, b].".format(label)}

        # Clamp numeric ranges.
        shininess = max(0, min(255, int(shininess)))
        transparency = max(0.0, min(1.0, float(transparency)))

        params: dict[str, object] = {
            "name": name,
            "shininess": shininess,
            "transparency": transparency,
        }
        if resolved_diffuse is not None:
            params["diffuse"] = [max(0, min(255, int(v))) for v in resolved_diffuse]
        if specular is not None:
            params["specular"] = [max(0, min(255, int(v))) for v in specular]
        if emission is not None:
            params["emission"] = [max(0, min(255, int(v))) for v in emission]

        plugin = _try_plugin("create_material", params)
        if plugin:
            return plugin

        code = "__mcp_material = {!s}\n{}".format(json.dumps(params), _CREATE_MATERIAL_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Object Material", destructiveHint=True))
    def set_object_material(
        id: str,
        material_index: int | None = None,
        material_name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Assign a material to a Rhino object by its GUID.

        Provide either ``material_index`` (integer index into the document
        material table) or ``material_name`` (string) to look up the material.
        At least one of the two must be supplied.
        """
        err = validate.guid(id, "id")
        if err: return err
        if material_index is None and material_name is None:
            return {"ok": False, "error": "Provide either 'material_index' or 'material_name'."}

        params: dict[str, object] = {"id": id}
        if material_index is not None:
            params["material_index"] = int(material_index)
        if material_name is not None:
            params["material_name"] = material_name

        plugin = _try_plugin("set_object_material", params)
        if plugin:
            return plugin

        code = "__mcp_set_mat = {!s}\n{}".format(json.dumps(params), _SET_OBJECT_MATERIAL_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Rhino Material", destructiveHint=True))
    def delete_material(
        material_index: int | None = None,
        material_name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete a material from the document material table.

        Provide either ``material_index`` (integer) or ``material_name``
        (string).  At least one of the two must be supplied.
        """
        if material_index is None and material_name is None:
            return {"ok": False, "error": "Provide either 'material_index' or 'material_name'."}

        params: dict[str, object] = {}
        if material_index is not None:
            params["material_index"] = int(material_index)
        if material_name is not None:
            params["material_name"] = material_name

        plugin = _try_plugin("delete_material", params)
        if plugin:
            return plugin

        code = "__mcp_del_mat = {!s}\n{}".format(json.dumps(params), _DELETE_MATERIAL_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


    @mcp.tool(annotations=ToolAnnotations(title="Set Material Color", destructiveHint=True))
    def set_material_color(
        object_id: str,
        color: list[int],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the diffuse color of an object's material using RGB [r, g, b] (0-255).

        Creates a new material if the object uses the default material.
        """
        payload = {"op": "set_color", "object_id": object_id, "color": color}
        code = "__mcp_mat_op = {!r}\n{}".format(payload, _MAT_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Material Transparency", destructiveHint=True))
    def set_material_transparency(
        object_id: str,
        transparency: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the transparency of an object's material.

        ``transparency``: 0.0 = fully opaque, 1.0 = fully transparent.
        """
        payload = {"op": "set_transparency", "object_id": object_id,
                   "transparency": max(0.0, min(1.0, float(transparency)))}
        code = "__mcp_mat_op = {!r}\n{}".format(payload, _MAT_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Material Shine", destructiveHint=True))
    def set_material_shine(
        object_id: str,
        shine: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set the shininess of an object's material.

        ``shine``: 0.0 = matte, 255.0 = glossy.
        """
        payload = {"op": "set_shine", "object_id": object_id,
                   "shine": max(0.0, min(255.0, float(shine)))}
        code = "__mcp_mat_op = {!r}\n{}".format(payload, _MAT_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Material to Layer", destructiveHint=True))
    def add_material_to_layer(
        layer_name: str,
        color: list[int] | None = None,
        transparency: float = 0.0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a material and assign it to a layer.

        ``color`` is an RGB list [r, g, b] (0-255). All objects on the layer
        that use layer material will inherit this appearance.
        """
        payload = {"op": "layer_material", "layer_name": layer_name,
                   "color": color, "transparency": transparency}
        code = "__mcp_mat_op = {!r}\n{}".format(payload, _MAT_OPS_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


def _try_plugin(command_type: str, params: dict[str, object]) -> dict[str, object] | None:
    if rhino.preferred_backend() not in {"auto", "plugin"}:
        return None
    try:
        return rhino.plugin_result(command_type, params)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# RhinoScript fallback implementations (used when plugin socket is unavailable)
# ---------------------------------------------------------------------------

_GET_MATERIALS_SCRIPT = r'''
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc
materials = []
for i, mat in enumerate(doc.Materials):
    if mat.IsDeleted:
        continue
    d = mat.DiffuseColor
    s = mat.SpecularColor
    e = mat.EmissionColor
    materials.append({
        "index": i,
        "name": mat.Name,
        "diffuse": [d.R, d.G, d.B],
        "specular": [s.R, s.G, s.B],
        "emission": [e.R, e.G, e.B],
        "shininess": int(mat.Shine),
        "transparency": float(mat.Transparency),
    })
result = {"materials": materials, "count": len(materials)}
'''

_CREATE_MATERIAL_SCRIPT = r'''
import Rhino
import System.Drawing

doc = Rhino.RhinoDoc.ActiveDoc
data = __mcp_material

mat = Rhino.DocObjects.Material()
mat.Name = str(data.get("name") or "")

def _color(key):
    v = data.get(key)
    if v is None:
        return None
    return System.Drawing.Color.FromArgb(int(v[0]), int(v[1]), int(v[2]))

if data.get("diffuse") is not None:
    mat.DiffuseColor = _color("diffuse")
if data.get("specular") is not None:
    mat.SpecularColor = _color("specular")
if data.get("emission") is not None:
    mat.EmissionColor = _color("emission")
if data.get("shininess") is not None:
    mat.Shine = float(data["shininess"])
if data.get("transparency") is not None:
    mat.Transparency = float(data["transparency"])

index = doc.Materials.Add(mat)
doc.Materials.Modify(mat, index, True)
result = {"index": index, "name": mat.Name}
'''

_SET_OBJECT_MATERIAL_SCRIPT = r'''
import Rhino
import System

doc = Rhino.RhinoDoc.ActiveDoc
data = __mcp_set_mat

obj_id = System.Guid(str(data["id"]))
obj = doc.Objects.FindId(obj_id)
if obj is None:
    raise ValueError("Object not found: {}".format(data["id"]))

mat_index = data.get("material_index")
if mat_index is None:
    name = str(data["material_name"])
    mat_index = next(
        (i for i, m in enumerate(doc.Materials) if not m.IsDeleted and m.Name == name),
        None,
    )
    if mat_index is None:
        raise ValueError("Material not found: {}".format(name))

obj.Attributes.MaterialIndex = int(mat_index)
obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
obj.CommitChanges()
result = {"object_id": str(data["id"]), "material_index": int(mat_index)}
'''

_DELETE_MATERIAL_SCRIPT = r'''
import Rhino

doc = Rhino.RhinoDoc.ActiveDoc
data = __mcp_del_mat

mat_index = data.get("material_index")
if mat_index is None:
    name = str(data["material_name"])
    mat_index = next(
        (i for i, m in enumerate(doc.Materials) if not m.IsDeleted and m.Name == name),
        None,
    )
    if mat_index is None:
        raise ValueError("Material not found: {}".format(name))

mat_index = int(mat_index)
ok = doc.Materials.Delete(mat_index, True)
result = {"deleted": bool(ok), "material_index": mat_index}
'''

_MAT_OPS_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import System

data = __mcp_mat_op
op   = data["op"]

def _get_or_create_material(oid):
    """Return the material index for oid, creating one if needed."""
    doc = Rhino.RhinoDoc.ActiveDoc
    obj = doc.Objects.FindId(System.Guid(str(oid)))
    if obj is None:
        raise ValueError("Object not found: {}".format(oid))
    if obj.Attributes.MaterialSource == Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject:
        return obj, obj.Attributes.MaterialIndex
    # Duplicate default material to object-level
    mat  = Rhino.DocObjects.Material()
    idx  = doc.Materials.Add(mat)
    obj.Attributes.MaterialIndex = idx
    obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
    obj.CommitChanges()
    return obj, idx

if op == "set_color":
    doc = Rhino.RhinoDoc.ActiveDoc
    obj, idx = _get_or_create_material(data["object_id"])
    mat = doc.Materials[idx]
    c = data["color"]
    mat.DiffuseColor = System.Drawing.Color.FromArgb(int(c[0]), int(c[1]), int(c[2]))
    doc.Materials.Modify(mat, idx, True)
    result = {"ok": True, "material_index": idx, "color": c}

elif op == "set_transparency":
    doc = Rhino.RhinoDoc.ActiveDoc
    obj, idx = _get_or_create_material(data["object_id"])
    mat = doc.Materials[idx]
    mat.Transparency = float(data["transparency"])
    doc.Materials.Modify(mat, idx, True)
    result = {"ok": True, "material_index": idx, "transparency": data["transparency"]}

elif op == "set_shine":
    doc = Rhino.RhinoDoc.ActiveDoc
    obj, idx = _get_or_create_material(data["object_id"])
    mat = doc.Materials[idx]
    mat.Shine = float(data["shine"])
    doc.Materials.Modify(mat, idx, True)
    result = {"ok": True, "material_index": idx, "shine": data["shine"]}

elif op == "layer_material":
    doc   = Rhino.RhinoDoc.ActiveDoc
    lname = data["layer_name"]
    if not rs.IsLayer(lname):
        rs.AddLayer(lname)
    li  = doc.Layers.FindByFullPath(lname, Rhino.RhinoMath.UnsetIntIndex)
    mat = Rhino.DocObjects.Material()
    if data.get("color"):
        c = data["color"]
        mat.DiffuseColor = System.Drawing.Color.FromArgb(int(c[0]), int(c[1]), int(c[2]))
    mat.Transparency = float(data.get("transparency", 0.0))
    idx = doc.Materials.Add(mat)
    layer = doc.Layers[li]
    layer.RenderMaterialIndex = idx
    layer.CommitChanges()
    result = {"ok": True, "layer": lname, "material_index": idx}
'''

"""
Block (instance definition) management tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Create Block", destructiveHint=True))
    def create_block(
        object_ids: list[str],
        base_point: list[float],
        name: str,
        delete_input: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Create a block definition from ``object_ids`` with ``base_point`` [x, y, z].

        ``delete_input=True`` (default) removes the source objects after creating
        the block. Returns the block..."""
        err = validate.guid_list(object_ids, "object_ids") or validate.coordinate(base_point, "base_point")
        if err: return err
        payload = {"object_ids": object_ids, "base_point": base_point, "name": name, "delete_input": delete_input}
        code = "__mcp_block = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Insert Block", destructiveHint=True))
    def insert_block(
        name: str,
        point: list[float],
        scale: float = 1.0,
        rotation: float = 0.0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Insert an instance of block ``name`` at ``point`` [x, y, z].

        ``scale`` scales uniformly. ``rotation`` is in degrees around the Z axis.
        """
        err = validate.coordinate(point, "point")
        if err: return err
        payload = {"op": "insert", "name": name, "point": point, "scale": scale, "rotation": rotation}
        code = "__mcp_block = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Explode Block", destructiveHint=True))
    def explode_block(
        block_id: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Explode a block instance into its constituent objects.
        Returns the ids of the resulting objects.
        """
        payload = {"op": "explode", "block_id": block_id}
        code = "__mcp_block = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Block Definition", destructiveHint=True))
    def delete_block(
        name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete a block definition by name.

        All instances of the block are also removed.
        """
        payload = {"op": "delete", "name": name}
        code = "__mcp_block = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="List Blocks", readOnlyHint=True))
    def list_blocks(rhino_id: str | None = None) -> dict[str, object]:
        """
        List all block definitions in the document.

        Returns each block's name, instance count, and object count.
        """
        payload = {"op": "list"}
        code = "__mcp_block = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

data  = __mcp_block
op    = data.get("op", "create")

if op == "create":
    oid = rs.AddBlock(data["object_ids"], data["base_point"], data["name"],
                      delete_input=bool(data.get("delete_input", True)))
    result = {"name": oid, "ok": bool(oid)}

elif op == "insert":
    import math
    angle = math.radians(float(data.get("rotation", 0)))
    s     = float(data.get("scale", 1.0))
    xf    = Rhino.Geometry.Transform.Scale(
                Rhino.Geometry.Point3d(*data["point"]), s)
    xf    = xf * Rhino.Geometry.Transform.Rotation(
                angle, Rhino.Geometry.Vector3d.ZAxis,
                Rhino.Geometry.Point3d(*data["point"]))
    oid   = rs.InsertBlock2(data["name"], xf)
    rs.Redraw()
    result = {"id": str(oid) if oid else None, "ok": bool(oid)}

elif op == "explode":
    ids = rs.ExplodeBlockInstance(data["block_id"])
    rs.Redraw()
    result = {"ids": [str(i) for i in ids or []], "count": len(ids or [])}

elif op == "delete":
    ok = rs.DeleteBlock(data["name"])
    result = {"ok": bool(ok)}

elif op == "list":
    names = rs.BlockNames() or []
    blocks = []
    for n in names:
        instances = rs.BlockInstanceCount(n) or 0
        obj_count = rs.BlockObjectCount(n) or 0
        blocks.append({"name": n, "instance_count": instances, "object_count": obj_count})
    result = {"blocks": blocks, "count": len(blocks)}
'''

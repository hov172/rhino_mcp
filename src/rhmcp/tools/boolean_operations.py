"""
Boolean operations for Rhino solid objects.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Boolean Union", destructiveHint=True))
    def boolean_union(object_ids: list[str], delete_sources: bool = True, name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Union multiple closed solid objects.
        """
        err = validate.guid_list(object_ids, "object_ids")
        if err: return err
        return _run("union", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Boolean Difference", destructiveHint=True))
    def boolean_difference(
        base_id: str,
        subtract_ids: list[str],
        delete_sources: bool = True,
        name: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Subtract solids from a base solid.
        """
        err = validate.guid(base_id, "base_id") or validate.guid_list(subtract_ids, "subtract_ids")
        if err: return err
        return _run("difference", locals())

    @mcp.tool(annotations=ToolAnnotations(title="Boolean Intersection", destructiveHint=True))
    def boolean_intersection(object_ids: list[str], delete_sources: bool = True, name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Keep only the overlapping volume of multiple solids.
        """
        err = validate.guid_list(object_ids, "object_ids")
        if err: return err
        return _run("intersection", locals())


def _run(operation: str, payload: dict[str, object]) -> dict[str, object]:
    rhino_id = payload.pop("rhino_id", None)
    command_type = "boolean_" + operation
    plugin_params = {key: value for key, value in payload.items() if value is not None}
    payload["operation"] = operation
    code = "__mcp_boolean = {!s}\n{}".format(json.dumps(payload), _SCRIPT)
    return rhino.run_plugin_or_python(
        command_type,
        plugin_params,
        code,
        rhino_id=rhino_id if isinstance(rhino_id, str) else None,
    )


_SCRIPT = r'''
import rhinoscriptsyntax as rs

data = __mcp_boolean
operation = data["operation"]
delete_sources = bool(data.get("delete_sources", True))
name = data.get("name")

if operation == "union":
    ids = rs.BooleanUnion(data["object_ids"], delete_input=delete_sources)
elif operation == "difference":
    ids = rs.BooleanDifference(data["base_id"], data["subtract_ids"], delete_input=delete_sources)
elif operation == "intersection":
    obj_list = list(data["object_ids"])
    if len(obj_list) < 2:
        raise ValueError("boolean_intersection requires at least 2 objects")
    ids = rs.BooleanIntersection([obj_list[0]], [obj_list[1]], delete_input=delete_sources)
    for oid in obj_list[2:]:
        if ids:
            ids = rs.BooleanIntersection(ids, [oid], delete_input=True)
else:
    raise ValueError("Unsupported boolean operation: {}".format(operation))

if ids and not isinstance(ids, (list, tuple)):
    ids = [ids]
for i, oid in enumerate(ids or []):
    if name:
        rs.ObjectName(oid, name if len(ids) == 1 else "{}_{}".format(name, i + 1))
rs.Redraw()
result = {"result_ids": [str(oid) for oid in ids or []], "count": len(ids or [])}
'''

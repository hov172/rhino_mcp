"""
Object group management tools.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Create Group", destructiveHint=True))
    def create_group(
        name: str | None = None,
        object_ids: list[str] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a new group, optionally pre-populating it with ``object_ids``.

        If ``name`` is omitted Rhino auto-generates one. Returns the group name.
        """
        if object_ids is not None:
            err = validate.guid_list(object_ids, "object_ids")
            if err: return err
        payload = {"op": "create", "name": name, "object_ids": object_ids}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Group", destructiveHint=True))
    def delete_group(
        name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete a group by name. The objects remain in the document.
        """
        payload = {"op": "delete", "name": name}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Add Objects to Group", destructiveHint=True))
    def add_to_group(
        name: str,
        object_ids: list[str],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Add ``object_ids`` to an existing group.
        """
        err = validate.guid_list(object_ids, "object_ids")
        if err: return err
        payload = {"op": "add", "name": name, "object_ids": object_ids}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Remove Objects from Group", destructiveHint=True))
    def remove_from_group(
        name: str,
        object_ids: list[str],
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Remove ``object_ids`` from a group.
        """
        err = validate.guid_list(object_ids, "object_ids")
        if err: return err
        payload = {"op": "remove", "name": name, "object_ids": object_ids}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="List Groups", readOnlyHint=True))
    def list_groups(rhino_id: str | None = None) -> dict[str, object]:
        """
        List all groups in the document with their member object counts.
        """
        payload = {"op": "list"}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Select by Group", destructiveHint=True))
    def select_by_group(
        name: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Select all objects that belong to the named group.
        """
        payload = {"op": "select", "name": name}
        code = "__mcp_grp = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs

data = __mcp_grp
op   = data.get("op", "list")

if op == "create":
    name = data.get("name")
    ids  = data.get("object_ids") or []
    gname = rs.AddGroup(name) if name else rs.AddGroup()
    if ids and gname:
        rs.AddObjectsToGroup(ids, gname)
    result = {"name": gname, "ok": bool(gname)}

elif op == "delete":
    ok = rs.DeleteGroup(data["name"])
    result = {"ok": bool(ok)}

elif op == "add":
    n = rs.AddObjectsToGroup(data["object_ids"], data["name"])
    result = {"added": n, "ok": n > 0}

elif op == "remove":
    rs.RemoveObjectsFromGroup(data["object_ids"], data["name"])
    result = {"ok": True}

elif op == "select":
    ids = rs.ObjectsByGroup(data["name"]) or []
    rs.SelectObjects(ids)
    result = {"selected": [str(i) for i in ids], "count": len(ids)}

elif op == "list":
    names = rs.GroupNames() or []
    groups = []
    for n in names:
        members = rs.ObjectsByGroup(n) or []
        groups.append({"name": n, "member_count": len(members)})
    result = {"groups": groups, "count": len(groups)}
'''

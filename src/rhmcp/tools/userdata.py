"""
User text (key-value metadata) tools for objects and the document.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Set Object User Text", destructiveHint=True))
    def set_user_text(
        object_id: str,
        key: str,
        value: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set a key-value metadata string on an object.

        Use ``get_user_text`` to read it back or filter by it via
        ``select_rhino_objects`` / ``get_rhino_objects``.
        """
        err = validate.guid(object_id, "object_id")
        if err: return err
        payload = {"op": "set_obj", "object_id": object_id, "key": key, "value": value}
        code = "__mcp_ud = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Object User Text", readOnlyHint=True))
    def get_user_text(
        object_id: str,
        key: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Get user text from an object.

        If ``key`` is provided returns just that value; omit it to return all
        key-value pairs as a dict.
        """
        err = validate.guid(object_id, "object_id")
        if err: return err
        payload = {"op": "get_obj", "object_id": object_id, "key": key}
        code = "__mcp_ud = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Object User Text", destructiveHint=True))
    def delete_user_text(
        object_id: str,
        key: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete a single user text key from an object.
        """
        err = validate.guid(object_id, "object_id")
        if err: return err
        payload = {"op": "del_obj", "object_id": object_id, "key": key}
        code = "__mcp_ud = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Set Document User Text", destructiveHint=True))
    def set_document_user_text(
        key: str,
        value: str,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Set a document-level key-value metadata string.

        Document user text persists inside the .3dm file.
        """
        payload = {"op": "set_doc", "key": key, "value": value}
        code = "__mcp_ud = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Document User Text", readOnlyHint=True))
    def get_document_user_text(
        key: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Get document-level user text.

        Omit ``key`` to return all key-value pairs.
        """
        payload = {"op": "get_doc", "key": key}
        code = "__mcp_ud = {!r}\n{}".format(payload, _SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino

data = __mcp_ud
op   = data["op"]

if op == "set_obj":
    rs.SetUserText(data["object_id"], data["key"], data["value"])
    result = {"ok": True, "object_id": data["object_id"], "key": data["key"]}

elif op == "get_obj":
    oid = data["object_id"]
    key = data.get("key")
    if key:
        val = rs.GetUserText(oid, key)
        result = {"value": val, "key": key, "object_id": oid}
    else:
        keys = rs.GetUserText(oid) or []
        kv   = {k: rs.GetUserText(oid, k) for k in keys}
        result = {"user_text": kv, "object_id": oid}

elif op == "del_obj":
    rs.SetUserText(data["object_id"], data["key"])   # no value = delete
    result = {"ok": True}

elif op == "set_doc":
    rs.SetDocumentUserText(data["key"], data["value"])
    result = {"ok": True, "key": data["key"]}

elif op == "get_doc":
    key = data.get("key")
    if key:
        val = rs.GetDocumentUserText(key)
        result = {"value": val, "key": key}
    else:
        keys = rs.GetDocumentUserText() or []
        kv = {}
        for k in keys:
            kv[k] = rs.GetDocumentUserText(k)
        result = {"user_text": kv}
'''

"""
Tools for Rhino layer management.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools_helpers import validate


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Manage Rhino Layer", destructiveHint=True))
    def manage_rhino_layer(
        action: str,
        name: str | None = None,
        color: list[int] | None = None,
        visible: bool | None = None,
        locked: bool | None = None,
        current: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create, update, delete, set current, or list Rhino layers.

        ``action`` is one of: list, create, update, delete, current.
        """
        _valid_actions = {"list", "create", "update", "delete", "current"}
        if action not in _valid_actions:
            return {"ok": False, "error": "action must be one of {}, got: {!r}".format(sorted(_valid_actions), action), "error_code": "INVALID_VALUE"}
        if action in ("create", "update", "delete", "current") and name is not None:
            err = validate.layer_name(name, "name")
            if err:
                return err
        if color is not None:
            err = validate.color(color, "color")
            if err:
                return err
        payload = {
            "action": action,
            "name": name,
            "color": color,
            "visible": visible,
            "locked": locked,
            "current": current,
        }
        code = "__mcp_layer = {!r}\n{}".format(payload, _LAYER_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Create Layer", destructiveHint=True))
    def create_layer(
        name: str,
        color: list[int] | None = None,
        visible: bool = True,
        locked: bool = False,
        current: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reference-compatible layer creation tool.
        """
        err = validate.layer_name(name, "name") or (validate.color(color, "color") if color is not None else None)
        if err:
            return err
        params = {"name": name, "color": color, "visible": visible, "locked": locked, "current": current}
        plugin = _try_plugin("create_layer", {key: value for key, value in params.items() if value is not None})
        if plugin:
            return plugin
        code = "__mcp_layer = {!r}\n{}".format({"action": "create", **params}, _LAYER_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Delete Layer", destructiveHint=True))
    def delete_layer(name: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible layer deletion tool.
        """
        plugin = _try_plugin("delete_layer", {"name": name})
        if plugin:
            return plugin
        code = "__mcp_layer = {!r}\n{}".format({"action": "delete", "name": name}, _LAYER_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Get Or Set Current Layer", destructiveHint=True))
    def get_or_set_current_layer(name: str | None = None, rhino_id: str | None = None) -> dict[str, object]:
        """
        Reference-compatible current layer getter/setter.
        """
        plugin = _try_plugin("get_or_set_current_layer", {"name": name} if name else {})
        if plugin:
            return plugin
        code = "__mcp_layer = {!r}\n{}".format({"action": "current", "name": name}, _LAYER_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


def _try_plugin(command_type: str, params: dict[str, object]) -> dict[str, object] | None:
    if rhino.preferred_backend() not in {"auto", "plugin"}:
        return None
    try:
        return rhino.plugin_result(command_type, params)
    except OSError:
        return None


_LAYER_SCRIPT = r'''
import rhinoscriptsyntax as rs

data = __mcp_layer
action = str(data.get("action") or "list").lower()
name = data.get("name")

def _color(value):
    if value is None:
        return None
    return tuple(int(v) for v in value[:3])

if action == "list":
    result = {
        "current": rs.CurrentLayer(),
        "layers": [
            {
                "name": layer,
                "visible": rs.LayerVisible(layer),
                "locked": rs.LayerLocked(layer),
                "color": list(rs.LayerColor(layer)),
            }
            for layer in rs.LayerNames() or []
        ],
    }
elif action in {"create", "update"}:
    if not name:
        raise ValueError("Layer name is required")
    if not rs.IsLayer(name):
        rs.AddLayer(name, color=_color(data.get("color")) or (200, 200, 200), visible=True, locked=False)
    if data.get("color") is not None:
        rs.LayerColor(name, _color(data.get("color")))
    if data.get("visible") is not None:
        rs.LayerVisible(name, bool(data.get("visible")))
    if data.get("locked") is not None:
        rs.LayerLocked(name, bool(data.get("locked")))
    if data.get("current"):
        rs.CurrentLayer(name)
    result = {"layer": name, "exists": rs.IsLayer(name), "current": rs.CurrentLayer()}
elif action == "delete":
    if not name:
        raise ValueError("Layer name is required")
    result = {"layer": name, "deleted": bool(rs.DeleteLayer(name))}
elif action == "current":
    if name:
        if not rs.IsLayer(name):
            rs.AddLayer(name)
        rs.CurrentLayer(name)
    result = {"current": rs.CurrentLayer()}
else:
    raise ValueError("Unsupported layer action: {}".format(action))
'''

"""
Backend router for Rhino 7/8 control paths.
"""

from __future__ import annotations

import json
import os
from typing import Any

from rhmcp.tools_helpers import plugin_client, rhinocode

BACKEND_AUTO = "auto"
BACKEND_RHINOCODE = "rhinocode"
BACKEND_PLUGIN = "plugin"
BACKEND_COMMAND = "command"


def preferred_backend(explicit: str | None = None) -> str:
    value = (explicit or os.environ.get("RHINO_MCP_BACKEND", BACKEND_AUTO)).lower()
    if value not in {BACKEND_AUTO, BACKEND_RHINOCODE, BACKEND_PLUGIN, BACKEND_COMMAND}:
        return BACKEND_AUTO
    return value


def status(rhino_id: str | None = None) -> dict[str, Any]:
    """
    Return observed status for available Rhino backends.
    """
    plugin = plugin_client.probe()
    try:
        instances = rhinocode.list_instances()
    except Exception as ex:  # noqa: BLE001 - status must report failures.
        instances = {"ok": False, "message": str(ex), "instances": []}
    return {
        "preferred_backend": preferred_backend(),
        "plugin_socket": plugin,
        "rhinocode": instances,
        "rhino_id": rhino_id,
    }


def list_instances() -> dict[str, Any]:
    """
    List Rhino instances for the active backend family.
    """
    mode = preferred_backend()
    if mode == BACKEND_PLUGIN:
        probe = plugin_client.probe()
        return {"ok": bool(probe.get("ok")), "backend": BACKEND_PLUGIN, "instances": [probe] if probe.get("ok") else [], "plugin_socket": probe}
    return rhinocode.list_instances()


def plugin_result(command_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = plugin_client.send_command(command_type, params)
    if response.get("status") == "error":
        return {"ok": False, "backend": BACKEND_PLUGIN, **response}
    if "result" in response:
        return {"ok": True, "backend": BACKEND_PLUGIN, "result": response.get("result"), "raw": response}
    return {"ok": True, "backend": BACKEND_PLUGIN, "result": response, "raw": response}


_RESULT_SENTINEL = "__MCP_RESULT__:"
_RESULT_SERIALIZER = (
    "\ntry:\n"
    "    import json as _mj\n"
    "    print('" + _RESULT_SENTINEL + "' + _mj.dumps(result))\n"
    "except:\n"
    "    pass\n"
)


def execute_python(code: str, rhino_id: str | None = None, backend_name: str | None = None) -> dict[str, Any]:
    """
    Execute Rhino Python through the best available script-capable backend.
    Appends a serialization snippet so the ``result`` variable is returned.
    """
    resp = run_plugin_or_python(
        "execute_rhinoscript_python_code",
        {"code": code + _RESULT_SERIALIZER},
        code + _RESULT_SERIALIZER,
        rhino_id=rhino_id,
        backend_name=backend_name,
    )
    # Extract script result from sentinel line in output
    inner = resp.get("result")
    if isinstance(inner, dict):
        output = inner.get("output") or ""
        for line in output.splitlines():
            if line.startswith(_RESULT_SENTINEL):
                payload = line[len(_RESULT_SENTINEL):]
                try:
                    resp["script_result"] = json.loads(payload)
                except Exception:
                    resp["script_result"] = payload
                # Strip sentinel line from output so callers don't see it
                inner["output"] = "\n".join(
                    l for l in output.splitlines() if not l.startswith(_RESULT_SENTINEL)
                )
                break
    return resp


def execute_script(
    code: str,
    suffix: str,
    rhino_id: str | None = None,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """
    Execute Rhino script code through the best available backend.
    """
    if suffix == ".py":
        return execute_python(code, rhino_id=rhino_id, backend_name=backend_name)
    if suffix == ".cs":
        return run_plugin_or_csharp(
            "execute_rhinocommon_csharp_code",
            {"code": code},
            code,
            rhino_id=rhino_id,
            backend_name=backend_name,
        )
    mode = preferred_backend(backend_name)
    if mode == BACKEND_PLUGIN:
        return {"ok": False, "backend": BACKEND_PLUGIN, "status": "unsupported", "message": "Plug-in backend only supports known script types."}
    result = rhinocode.execute_script(code, suffix, rhino_id=rhino_id)
    return {"backend": BACKEND_RHINOCODE, **result}


def run_plugin_or_python(
    command_type: str,
    params: dict[str, Any],
    python_code: str,
    rhino_id: str | None = None,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """
    Prefer plug-in socket for script-heavy operations; fall back to rhinocode.
    """
    mode = preferred_backend(backend_name)
    if mode in {BACKEND_AUTO, BACKEND_PLUGIN}:
        try:
            return plugin_result(command_type, params)
        except OSError as ex:
            if mode == BACKEND_PLUGIN:
                return {"ok": False, "backend": BACKEND_PLUGIN, "message": str(ex)}
    if mode == BACKEND_PLUGIN:
        return {"ok": False, "backend": BACKEND_PLUGIN, "message": "Plug-in backend unavailable."}
    result = rhinocode.execute_python(python_code, rhino_id=rhino_id)
    return {"backend": BACKEND_RHINOCODE, **result}


def run_plugin_or_csharp(
    command_type: str,
    params: dict[str, Any],
    csharp_code: str,
    rhino_id: str | None = None,
    backend_name: str | None = None,
) -> dict[str, Any]:
    mode = preferred_backend(backend_name)
    if mode in {BACKEND_AUTO, BACKEND_PLUGIN}:
        try:
            return plugin_result(command_type, params)
        except OSError as ex:
            if mode == BACKEND_PLUGIN:
                return {"ok": False, "backend": BACKEND_PLUGIN, "message": str(ex)}
    if mode == BACKEND_PLUGIN:
        return {"ok": False, "backend": BACKEND_PLUGIN, "message": "Plug-in backend unavailable."}
    result = rhinocode.execute_script(csharp_code, ".cs", rhino_id=rhino_id)
    return {"backend": BACKEND_RHINOCODE, **result}


def run_command(command: str, rhino_id: str | None = None, backend_name: str | None = None) -> dict[str, Any]:
    """
    Run a Rhino command. RhinoMCP plug-in does not expose a universal command
    runner, so commands use rhinocode.
    """
    mode = preferred_backend(backend_name)
    if mode == BACKEND_PLUGIN:
        return {"ok": False, "backend": BACKEND_PLUGIN, "message": "Raw Rhino commands require rhinocode backend."}
    result = rhinocode.run_command(command, rhino_id=rhino_id)
    return {"backend": BACKEND_RHINOCODE, **result}

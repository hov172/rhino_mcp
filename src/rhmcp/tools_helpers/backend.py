"""
Backend router for Rhino 7/8 control paths.
"""

from __future__ import annotations

import json
import os
from typing import Any

from rhmcp.tools_helpers import plugin_client, rhinocode
from rhmcp.tools_helpers.errors import normalize

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


def _slot_registry_enabled() -> bool:
    return os.environ.get("RHINO_MCP_USE_SLOT_REGISTRY", "").strip() == "1"


def plugin_result(
    command_type: str,
    params: dict[str, Any] | None = None,
    rhino_id: str | None = None,
) -> dict[str, Any]:
    # Resolve connection target via slot registry when requested
    host: str | None = None
    port: int | None = None
    if rhino_id is not None or _slot_registry_enabled():
        try:
            from rhmcp.tools_helpers import slot_registry
            slot = slot_registry.get(rhino_id)
            host, port = slot.host, slot.port
        except RuntimeError as ex:
            if rhino_id is not None:
                raise RuntimeError(
                    f"Cannot route to Rhino instance {rhino_id!r}: {ex}. "
                    "Use get_rhino_instances to list available instances."
                ) from ex
            pass  # auto-select failure → env-var default is acceptable
    response = plugin_client.send_command(command_type, params, host=host, port=port)
    if response.get("status") == "error":
        msg = response.get("message") or response.get("error") or "Plugin returned status=error with no message"
        return normalize({"ok": False, "backend": BACKEND_PLUGIN, "error": msg, **response})
    if "result" in response:
        out = {"ok": True, "backend": BACKEND_PLUGIN, "result": response.get("result"), "raw": response}
        inner = response.get("result") or {}
        if isinstance(inner, dict):
            # The plugin wraps handler results in status="ok" even when the
            # handler itself failed (e.g. a script error) — surface that.
            if inner.get("success") is False or inner.get("ok") is False:
                out["ok"] = False
                out["error"] = (
                    inner.get("error") or inner.get("message")
                    or "Plugin command reported failure"
                )
            # Promote script_result from nested result when present.
            if "script_result" in response:
                out["script_result"] = response["script_result"]
        return normalize(out)
    return normalize({"ok": True, "backend": BACKEND_PLUGIN, "result": response, "raw": response})


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
    if "script_result" not in resp:
        # rhinocode fallback: the sentinel print lands in captured stdout, and
        # the wrapper also reports the ``result`` variable directly.
        stdout = resp.get("stdout") or ""
        if _RESULT_SENTINEL in stdout:
            for line in stdout.splitlines():
                if line.startswith(_RESULT_SENTINEL):
                    payload = line[len(_RESULT_SENTINEL):]
                    try:
                        resp["script_result"] = json.loads(payload)
                    except Exception:
                        resp["script_result"] = payload
                    break
            resp["stdout"] = "\n".join(
                l for l in stdout.splitlines() if not l.startswith(_RESULT_SENTINEL)
            )
        elif resp.get("backend") == BACKEND_RHINOCODE and resp.get("status") == "ok":
            resp["script_result"] = resp.get("result")
    sr = resp.get("script_result")
    if isinstance(sr, dict) and sr.get("ok") is False:
        resp["ok"] = False
        resp.setdefault("error", sr.get("error", "Script returned ok: false"))
        if "error_code" not in resp and "error_code" in sr:
            resp["error_code"] = sr["error_code"]
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
    _plugin_error: str | None = None
    if mode in {BACKEND_AUTO, BACKEND_PLUGIN}:
        try:
            resp = plugin_result(command_type, params, rhino_id=rhino_id)
            # In auto mode, a plugin that doesn't implement this command is not
            # a failure — run the supplied Python fallback instead.
            unsupported = (
                mode == BACKEND_AUTO
                and resp.get("ok") is False
                and "Unsupported command type" in str(resp.get("error", ""))
            )
            if not unsupported:
                return resp
            _plugin_error = str(resp.get("error"))
        except OSError as ex:
            if mode == BACKEND_PLUGIN:
                host, port, _ = plugin_client.connection_settings()
                return normalize({
                    "ok": False,
                    "backend": BACKEND_PLUGIN,
                    "error": str(ex),
                    "error_code": "SOCKET_UNAVAILABLE",
                    "hint": f"Verify Rhino is running and MCPStart is active at {host}:{port}.",
                })
            _plugin_error = str(ex)
    result = rhinocode.execute_python(python_code, rhino_id=rhino_id)
    resp = normalize({"backend": BACKEND_RHINOCODE, **result})
    if _plugin_error:
        resp["plugin_error"] = _plugin_error
    if not resp.get("ok") and result.get("status") == "unknown":
        resp["error_code"] = "RHINOCODE_DISPATCH_FAILED"
        resp.setdefault("error", "Rhino did not execute the script. Ensure MCPStart is running or set RHINO_MCP_BACKEND=rhinocode.")
    return resp


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
            return plugin_result(command_type, params, rhino_id=rhino_id)
        except OSError as ex:
            if mode == BACKEND_PLUGIN:
                host, port, _ = plugin_client.connection_settings()
                return normalize({
                    "ok": False,
                    "backend": BACKEND_PLUGIN,
                    "error": str(ex),
                    "error_code": "SOCKET_UNAVAILABLE",
                    "hint": f"Verify Rhino is running and MCPStart is active at {host}:{port}.",
                })
    if mode == BACKEND_PLUGIN:
        host, port, _ = plugin_client.connection_settings()
        return normalize({
            "ok": False,
            "backend": BACKEND_PLUGIN,
            "error": f"Plug-in backend unavailable at {host}:{port}.",
            "error_code": "SOCKET_UNAVAILABLE",
        })
    result = rhinocode.execute_script(csharp_code, ".cs", rhino_id=rhino_id)
    return normalize({"backend": BACKEND_RHINOCODE, **result})


def run_command(command: str, echo: bool = False, rhino_id: str | None = None, backend_name: str | None = None) -> dict[str, Any]:
    """
    Run a Rhino command. Tries the plugin socket first (supports echo + output
    capture), falls back to rhinocode when the plugin is unavailable.
    """
    mode = preferred_backend(backend_name)
    if mode in {BACKEND_AUTO, BACKEND_PLUGIN}:
        try:
            return plugin_result("run_command", {"command": command, "echo": echo}, rhino_id=rhino_id)
        except OSError as ex:
            if mode == BACKEND_PLUGIN:
                host, port, _ = plugin_client.connection_settings()
                return normalize({
                    "ok": False,
                    "backend": BACKEND_PLUGIN,
                    "error": str(ex),
                    "error_code": "SOCKET_UNAVAILABLE",
                    "hint": f"Verify Rhino is running and MCPStart is active at {host}:{port}.",
                })
    result = rhinocode.run_command(command, rhino_id=rhino_id)
    return normalize({"backend": BACKEND_RHINOCODE, **result})

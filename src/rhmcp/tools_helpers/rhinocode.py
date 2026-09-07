"""
Utilities for invoking McNeel's ``rhinocode`` command line tool.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Sequence
from typing import Any

import sys

_TIMEOUT = float(os.environ.get("RHINO_MCP_TIMEOUT", "300"))
_TEMP_DIR = os.environ.get("RHINO_MCP_TEMP_DIR", tempfile.gettempdir())
_POLL_INTERVAL = float(os.environ.get("RHINO_MCP_POLL_INTERVAL", "0.25"))
_RUNPYTHON_FALLBACK = os.environ.get("RHINO_MCP_RUNPYTHON_FALLBACK", "").lower() in {"1", "true", "yes"}


def find_rhinocode() -> str:
    """
    Return the ``rhinocode`` executable path.

    ``RHINOCODE`` can point at a custom executable. Otherwise PATH is checked,
    followed by platform-specific default install locations.
    """
    configured = os.environ.get("RHINOCODE")
    if configured:
        if os.path.isfile(configured) and os.access(configured, os.X_OK):
            return configured
        # Env var set but not executable — fall through to auto-detect

    found = shutil.which("rhinocode")
    if found:
        return found

    if sys.platform == "darwin":
        macos_default = "/Applications/Rhino 8.app/Contents/Resources/bin/rhinocode"
        if os.path.exists(macos_default):
            return macos_default
    elif sys.platform == "win32":
        import winreg  # type: ignore[import]
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r"SOFTWARE\McNeel\Rhinoceros\8.0") as key:
                    install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    candidate = os.path.join(install_path, "System", "rhinocode.exe")
                    if os.path.exists(candidate):
                        return candidate
            except OSError:
                pass
        # Common default path
        candidate = r"C:\Program Files\Rhino 8\System\rhinocode.exe"
        if os.path.exists(candidate):
            return candidate

    return "rhinocode"


def _base_args(rhino_id: str | None = None) -> list[str]:
    from rhmcp.tools_helpers.workflow_state import rhino_id as scoped_rhino_id
    rhino_id = rhino_id or scoped_rhino_id()
    args = [find_rhinocode()]
    if rhino_id:
        args.extend(["--rhino", rhino_id])
    return args


def run_rhinocode(args: Sequence[str], rhino_id: str | None = None) -> dict[str, Any]:
    """
    Run ``rhinocode`` with *args* and return process details.
    """
    command = [*_base_args(rhino_id), *args]
    try:
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except FileNotFoundError as ex:
        raise RuntimeError(
            "Cannot find rhinocode. Install Rhino 8.11+, add rhinocode to PATH, "
            "or set RHINOCODE to the full executable path."
        ) from ex
    except subprocess.TimeoutExpired as ex:
        raise RuntimeError("rhinocode timed out after {:.0f}s".format(_TIMEOUT)) from ex

    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def list_instances() -> dict[str, Any]:
    """
    Return running Rhino instances reported by ``rhinocode list --json``.
    """
    proc = run_rhinocode(["list", "--json"])
    instances: list[dict[str, Any]] = []
    if proc["ok"] and str(proc["stdout"]).strip():
        try:
            parsed = json.loads(str(proc["stdout"]))
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            instances = [item for item in parsed if isinstance(item, dict)]
    return {**proc, "instances": instances}


def run_command(command_text: str, rhino_id: str | None = None) -> dict[str, Any]:
    """
    Run a Rhino command string in a running Rhino instance.
    """
    from rhmcp.tools_helpers.security import command_execution_gate
    error = command_execution_gate("run_command", {"command": command_text})
    if error:
        return error
    return run_rhinocode(["command", command_text], rhino_id=rhino_id)


def execute_script(code: str, suffix: str, rhino_id: str | None = None) -> dict[str, Any]:
    """
    Execute a non-Python RhinoCode script and return process details.
    """
    if suffix == ".py":
        return execute_python(code, rhino_id=rhino_id)

    from rhmcp.tools_helpers.security import command_execution_gate
    error = command_execution_gate("execute_rhinocommon_csharp_code", {"code": code})
    if error:
        return error
    with tempfile.TemporaryDirectory(prefix="rhino_mcp_", dir=_TEMP_DIR) as temp_dir:
        script_path = os.path.join(temp_dir, "script" + suffix)
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(code)
        proc = run_rhinocode(["script", script_path], rhino_id=rhino_id)
        return {
            "ok": proc["ok"],
            "rhinocode": proc,
            "status": "ok" if proc["ok"] else "error",
            "result": {"stdout": proc["stdout"], "stderr": proc["stderr"]},
            "message": None if proc["ok"] else proc["stderr"] or proc["stdout"],
            "stdout": proc["stdout"],
            "stderr": proc["stderr"],
        }


def execute_python(code: str, rhino_id: str | None = None) -> dict[str, Any]:
    """
    Execute Python inside Rhino and return a structured result.

    User code can assign a JSON-serialisable value to ``result``. The wrapper
    captures stdout/stderr and writes an execution report to a temp file because
    ``rhinocode script`` is not a structured RPC channel.
    """
    from rhmcp.tools_helpers.security import command_execution_gate
    error = command_execution_gate("execute_rhinoscript_python_code", {"code": code})
    if error:
        return error
    with tempfile.TemporaryDirectory(prefix="rhino_mcp_", dir=_TEMP_DIR) as temp_dir:
        script_path = os.path.join(temp_dir, "script.py")
        result_path = os.path.join(temp_dir, "result.json")

        wrapper = _script_wrapper(code, result_path)
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(wrapper)

        proc = run_rhinocode(["script", script_path], rhino_id=rhino_id)
        report = _read_result_when_ready(result_path, wait_seconds=2.0)

        # An accepted CLI dispatch with no result is ambiguous. Never issue a
        # second RunPythonScript command: the first may still be queued.

        if report is None:
            report = {
                "status": "error" if not proc["ok"] else "unknown",
                "message": "Rhino execution outcome unknown; inspect the document before retrying.",
                "error_code": "EXECUTION_OUTCOME_UNKNOWN",
                "retry_safe": False,
            }

        return {
            "ok": proc["ok"] and report.get("status") == "ok",
            "rhinocode": proc,
            "error_code": report.get("error_code"),
            "retry_safe": report.get("retry_safe", False),
            "status": report.get("status"),
            "result": report.get("result"),
            "message": report.get("message"),
            "stdout": report.get("stdout", ""),
            "stderr": report.get("stderr", ""),
        }


def _read_result_when_ready(result_path: str, wait_seconds: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + wait_seconds
    last_error: str | None = None
    while time.monotonic() <= deadline:
        if os.path.exists(result_path):
            with open(result_path, encoding="utf-8") as fh:
                try:
                    loaded = json.load(fh)
                except json.JSONDecodeError as ex:
                    # File may be mid-write — keep polling until the deadline.
                    last_error = str(ex)
                    time.sleep(_POLL_INTERVAL)
                    continue
                if isinstance(loaded, dict):
                    return loaded
                return {"status": "error", "message": "Result payload was not a JSON object."}
        time.sleep(_POLL_INTERVAL)
    if last_error is not None:
        return {"status": "error", "message": "Invalid result JSON: {:s}".format(last_error)}
    return None


def _script_wrapper(code: str, result_path: str) -> str:
    # The user code is embedded as a string literal and exec'd unmodified —
    # indenting it into the try-block would corrupt multi-line string literals.
    code_literal = repr(code)
    result_path_literal = repr(result_path)
    return """\
import contextlib
import io
import json
import os
import traceback

__mcp_stdout = io.StringIO()
__mcp_stderr = io.StringIO()
__mcp_payload = None
__mcp_doc = None
__mcp_undo = 0

def __mcp_json_default(value):
    try:
        return str(value)
    except Exception:
        return repr(value)

try:
    with contextlib.redirect_stdout(__mcp_stdout), contextlib.redirect_stderr(__mcp_stderr):
        import Rhino
        __mcp_doc = Rhino.RhinoDoc.ActiveDoc
        if __mcp_doc is not None:
            __mcp_undo = __mcp_doc.BeginUndoRecord("MCP Python")
            if not __mcp_undo:
                raise RuntimeError("Cannot start an isolated undo record")
            __mcp_doc.AddCustomUndoEvent("MCP transaction", lambda sender, event: None)
        result = None
        exec(compile({code}, "<rhino_mcp_script>", "exec"))
        __mcp_payload = {{
            "status": "ok",
            "result": result,
            "stdout": __mcp_stdout.getvalue(),
            "stderr": __mcp_stderr.getvalue(),
        }}
except Exception as ex:
    restored = False
    if __mcp_doc is not None and __mcp_undo:
        __mcp_doc.EndUndoRecord(__mcp_undo)
        __mcp_undo = 0
        restored = __mcp_doc.Undo()
    __mcp_payload = {{
        "rollback": {{"scope": "Rhino document undo", "restored": restored}},
        "status": "error",
        "message": str(ex),
        "traceback": traceback.format_exc(),
        "stdout": __mcp_stdout.getvalue(),
        "stderr": __mcp_stderr.getvalue(),
    }}

finally:
    if __mcp_doc is not None and __mcp_undo:
        __mcp_doc.EndUndoRecord(__mcp_undo)

__mcp_tmp = {result_path} + ".tmp"
with open(__mcp_tmp, "w", encoding="utf-8") as __mcp_fh:
    json.dump(__mcp_payload, __mcp_fh, default=__mcp_json_default)
os.replace(__mcp_tmp, {result_path})
""".format(code=code_literal, result_path=result_path_literal)

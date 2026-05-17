from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

# Ordered by preference (newest first)
_RHINO_PATHS: dict[str, list[str]] = {
    "darwin": [
        "/Applications/Rhino 8.app/Contents/MacOS/Rhino",
        "/Applications/Rhino 7.app/Contents/MacOS/Rhino",
    ],
    "win32": [
        r"C:\Program Files\Rhino 8\System\Rhino.exe",
        r"C:\Program Files\Rhino 7\System\Rhino.exe",
    ],
    "linux": [],  # RhinoInside/Compute only
}


def find_rhino() -> Path | None:
    """Return path to Rhino executable, or None if not found."""
    override = os.environ.get("RHINO_MCP_RHINO_PATH")
    if override:
        p = Path(override)
        return p if p.exists() else None
    for candidate in _RHINO_PATHS.get(sys.platform, []):
        p = Path(candidate)
        if p.exists():
            return p
    return None


def launch(rhino_path: Path | None = None, timeout: float = 60.0) -> int:
    """
    Launch Rhino and wait for its MCP plugin to announce itself.
    Returns the PID of the new Rhino process.
    Raises RuntimeError if Rhino not found; TimeoutError if plugin doesn't start.
    """
    from rhmcp.tools_helpers import slot_registry

    exe = rhino_path or find_rhino()
    if exe is None:
        raise RuntimeError(
            "Rhino executable not found. "
            "Set RHINO_MCP_RHINO_PATH or install Rhino to a standard location."
        )

    proc = subprocess.Popen(
        [str(exe)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    slot_registry.wait_for_slot(proc.pid, timeout=timeout)
    return proc.pid

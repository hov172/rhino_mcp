from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SlotInfo:
    pid: int
    host: str
    port: int
    version: str
    rhino_version: str
    started_at: str

    @property
    def rhino_id(self) -> str:
        return str(self.pid)


def _slots_dir() -> Path:
    import tempfile
    return Path(tempfile.gettempdir()) / "rhino-mcp-slots"


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)   # signal 0 = existence check
        return True
    except PermissionError:
        return True   # process exists but caller lacks access
    except OSError:
        return False  # ESRCH or no such process


def discover() -> dict[str, SlotInfo]:
    """Return all live slots keyed by rhino_id (str(pid))."""
    slots: dict[str, SlotInfo] = {}
    d = _slots_dir()
    if not d.exists():
        return slots
    for f in d.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            pid = int(data["pid"])
            if not _is_alive(pid):
                f.unlink(missing_ok=True)   # prune stale
                continue
            info = SlotInfo(
                pid=pid,
                host=data["host"],
                port=int(data["port"]),
                version=data.get("version", ""),
                rhino_version=data.get("rhino_version", ""),
                started_at=data.get("started_at", ""),
            )
            slots[str(pid)] = info
        except Exception:
            continue
    return slots


def get(rhino_id: str | None = None) -> SlotInfo:
    """
    Resolve rhino_id to a SlotInfo.
    None → first available slot (backward compat with single-instance setups).
    Raises RuntimeError if no matching slot found.
    """
    slots = discover()
    if not slots:
        raise RuntimeError(
            "No live Rhino MCP plugin slots found. "
            "Start Rhino and run MCPStart, or call launch_rhino first."
        )
    if rhino_id is None:
        return next(iter(slots.values()))
    if rhino_id not in slots:
        raise RuntimeError(
            f"Rhino slot '{rhino_id}' not found. "
            f"Available: {list(slots.keys())}"
        )
    return slots[rhino_id]


def wait_for_slot(pid: int, timeout: float = 30.0, poll: float = 0.5) -> SlotInfo:
    """Poll until the given PID appears in the slot registry."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_alive(pid):
            raise RuntimeError(f"Rhino process {pid} exited before announcing in the slot registry")
        slots = discover()
        if str(pid) in slots:
            return slots[str(pid)]
        time.sleep(poll)
    raise TimeoutError(f"Rhino process {pid} did not announce within {timeout}s")

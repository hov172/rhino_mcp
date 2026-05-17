"""Unit tests for slot_registry — no live Rhino required."""
from __future__ import annotations
import dataclasses
import json
import os
import subprocess
import sys
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def slots_dir(tmp_path, monkeypatch):
    """Isolated slot directory for each test."""
    d = tmp_path / "rhino-mcp-slots"
    d.mkdir()
    import rhmcp.tools_helpers.slot_registry as reg
    monkeypatch.setattr(reg, "_slots_dir", lambda: d)
    return d


def _write_slot(slots_dir: Path, pid: int, port: int = 1999) -> Path:
    f = slots_dir / f"{pid}.json"
    f.write_text(json.dumps({
        "pid": pid,
        "host": "127.0.0.1",
        "port": port,
        "version": "0.11.0",
        "rhino_version": "8.0",
        "started_at": "2026-05-17T00:00:00Z",
    }))
    return f


# ---------------------------------------------------------------------------
# discover() tests
# ---------------------------------------------------------------------------

def test_discover_empty(slots_dir):
    """No slot files → empty dict."""
    from rhmcp.tools_helpers.slot_registry import discover
    assert discover() == {}


def test_discover_live(slots_dir):
    """Slot file with the current process PID → appears in discovery."""
    from rhmcp.tools_helpers.slot_registry import discover
    pid = os.getpid()
    _write_slot(slots_dir, pid)
    result = discover()
    assert str(pid) in result
    info = result[str(pid)]
    assert info.pid == pid
    assert info.host == "127.0.0.1"
    assert info.port == 1999
    assert info.version == "0.11.0"
    assert info.rhino_version == "8.0"


def test_discover_live_rhino_id_is_str_pid(slots_dir):
    """SlotInfo.rhino_id is str(pid)."""
    from rhmcp.tools_helpers.slot_registry import discover
    pid = os.getpid()
    _write_slot(slots_dir, pid)
    result = discover()
    info = result[str(pid)]
    assert info.rhino_id == str(pid)


def test_discover_prunes_stale(slots_dir):
    """Slot file with a non-existent PID is pruned and the file deleted."""
    from rhmcp.tools_helpers.slot_registry import discover

    # Spawn and reap a real child process to get a guaranteed-dead PID.
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    stale_pid = p.pid
    slot_file = _write_slot(slots_dir, stale_pid)

    # Verify the file exists before discovery.
    assert slot_file.exists()

    result = discover()

    # The stale entry must not appear in results.
    assert str(stale_pid) not in result
    # The file must have been removed.
    assert not slot_file.exists()


def test_discover_returns_correct_port(slots_dir):
    """Non-default port is preserved in the returned SlotInfo."""
    from rhmcp.tools_helpers.slot_registry import discover
    pid = os.getpid()
    _write_slot(slots_dir, pid, port=2999)
    result = discover()
    assert result[str(pid)].port == 2999


def test_discover_skips_malformed_json(slots_dir):
    """A file with invalid JSON is silently skipped."""
    from rhmcp.tools_helpers.slot_registry import discover
    bad = slots_dir / "bad.json"
    bad.write_text("not json {{{")
    result = discover()
    assert result == {}


def test_discover_slots_dir_missing(tmp_path, monkeypatch):
    """If the slots directory doesn't exist at all, discover returns {}."""
    import rhmcp.tools_helpers.slot_registry as reg
    nonexistent = tmp_path / "no-such-dir"
    monkeypatch.setattr(reg, "_slots_dir", lambda: nonexistent)
    result = reg.discover()
    assert result == {}


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------

def test_get_default(slots_dir):
    """None rhino_id returns the first available slot."""
    from rhmcp.tools_helpers.slot_registry import get
    pid = os.getpid()
    _write_slot(slots_dir, pid)
    info = get(None)
    assert info.pid == pid


def test_get_by_id(slots_dir):
    """Specific rhino_id returns the correct slot."""
    from rhmcp.tools_helpers.slot_registry import get
    pid = os.getpid()
    _write_slot(slots_dir, pid)
    info = get(str(pid))
    assert info.pid == pid


def test_get_missing_raises(slots_dir):
    """Unknown rhino_id raises RuntimeError mentioning the missing id."""
    from rhmcp.tools_helpers.slot_registry import get
    pid = os.getpid()
    _write_slot(slots_dir, pid)
    with pytest.raises(RuntimeError, match="not found"):
        get("000")


def test_get_empty_raises(slots_dir):
    """No slots at all raises RuntimeError."""
    from rhmcp.tools_helpers.slot_registry import get
    with pytest.raises(RuntimeError, match="No live Rhino"):
        get(None)


def test_get_none_raises_when_no_slots(slots_dir):
    """get() with explicit None and empty registry raises RuntimeError."""
    from rhmcp.tools_helpers.slot_registry import get
    with pytest.raises(RuntimeError):
        get()


# ---------------------------------------------------------------------------
# wait_for_slot() tests
# ---------------------------------------------------------------------------

def test_wait_for_slot_timeout(slots_dir):
    """wait_for_slot raises TimeoutError when PID is alive but slot never appears."""
    from rhmcp.tools_helpers.slot_registry import wait_for_slot

    # Use current process PID so _is_alive returns True (process exists),
    # but don't write the slot file, so the slot is never found.
    pid = os.getpid()
    with pytest.raises(TimeoutError):
        wait_for_slot(pid, timeout=0.1, poll=0.05)


def test_wait_for_slot_finds_slot(slots_dir):
    """wait_for_slot returns SlotInfo when slot already exists."""
    from rhmcp.tools_helpers.slot_registry import wait_for_slot

    pid = os.getpid()
    _write_slot(slots_dir, pid)
    info = wait_for_slot(pid, timeout=1.0, poll=0.05)
    assert info.pid == pid


def test_wait_for_slot_dead_process_raises(slots_dir):
    """wait_for_slot raises RuntimeError immediately if PID is not alive."""
    from rhmcp.tools_helpers.slot_registry import wait_for_slot

    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    dead_pid = p.pid
    with pytest.raises(RuntimeError, match="exited"):
        wait_for_slot(dead_pid, timeout=5.0, poll=0.05)


# ---------------------------------------------------------------------------
# _is_alive() tests
# ---------------------------------------------------------------------------

def test_is_alive_current_process():
    """Current process PID is alive."""
    from rhmcp.tools_helpers.slot_registry import _is_alive
    assert _is_alive(os.getpid()) is True


def test_is_alive_nonexistent_pid():
    """A guaranteed-dead child PID returns False."""
    from rhmcp.tools_helpers.slot_registry import _is_alive
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert _is_alive(p.pid) is False


# ---------------------------------------------------------------------------
# _slots_dir() structural tests
# ---------------------------------------------------------------------------

def test_slots_dir_uses_tempdir():
    """_slots_dir() is rooted in tempfile.gettempdir()."""
    import tempfile
    # Import fresh without monkeypatch — test the real implementation.
    import importlib
    reg = importlib.import_module("rhmcp.tools_helpers.slot_registry")
    result = reg._slots_dir()
    assert str(result).startswith(tempfile.gettempdir())


def test_slots_dir_name():
    """_slots_dir() directory is named 'rhino-mcp-slots'."""
    import importlib
    reg = importlib.import_module("rhmcp.tools_helpers.slot_registry")
    assert reg._slots_dir().name == "rhino-mcp-slots"


# ---------------------------------------------------------------------------
# SlotInfo dataclass tests
# ---------------------------------------------------------------------------

def test_slot_info_frozen():
    """SlotInfo is frozen — attribute assignment raises FrozenInstanceError."""
    from rhmcp.tools_helpers.slot_registry import SlotInfo
    info = SlotInfo(
        pid=1,
        host="127.0.0.1",
        port=1999,
        version="0.11.0",
        rhino_version="8.0",
        started_at="2026-05-17T00:00:00Z",
    )
    _FrozenError = getattr(dataclasses, "FrozenInstanceError", AttributeError)
    with pytest.raises(_FrozenError):
        info.pid = 2  # type: ignore[misc]


def test_slot_info_rhino_id_is_str_pid():
    """rhino_id property returns str(pid)."""
    from rhmcp.tools_helpers.slot_registry import SlotInfo
    info = SlotInfo(
        pid=42,
        host="127.0.0.1",
        port=1999,
        version="0.11.0",
        rhino_version="8.0",
        started_at="2026-05-17T00:00:00Z",
    )
    assert info.rhino_id == "42"

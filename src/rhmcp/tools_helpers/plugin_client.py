"""
Client for RhinoMCP-style plug-in socket servers.

Keep-alive mode (default) reuses a single persistent TCP connection across
calls, eliminating per-call TCP handshake overhead.  If the connection drops
(Rhino restart, MCPStop), the client reconnects transparently on the next call.

Set RHINO_MCP_KEEPALIVE=0 to fall back to a new connection per call.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1999
DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2        # extra attempts after the first (total = retries + 1)
DEFAULT_RETRY_DELAY = 0.05  # seconds before first retry; doubles each attempt


def connection_settings(
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> tuple[str, int, float]:
    from rhmcp.tools_helpers.security import check_remote_allowed
    resolved_host = host or os.environ.get("RHINO_MCP_HOST", DEFAULT_HOST)
    check_remote_allowed(resolved_host)
    return (
        resolved_host,
        port or int(os.environ.get("RHINO_MCP_PORT", str(DEFAULT_PORT))),
        timeout or float(os.environ.get("RHINO_MCP_SOCKET_TIMEOUT", str(DEFAULT_TIMEOUT))),
    )


_MAX_RAW_DISPLAY = 200  # chars of raw response shown in error messages


class PluginResponseTimeout(OSError):
    """
    Timed out waiting for a response *after* the request was delivered.

    The command may still be executing inside Rhino, so this must never be
    retried — a retry would execute the command a second time.
    """


def _decode_chunks(chunks: list[bytes]) -> str | None:
    """
    Decode accumulated chunks as UTF-8.

    Returns None when the buffer ends mid-way through a multi-byte character
    (more data is needed); raises ValueError on genuinely non-UTF-8 data.
    """
    raw = b"".join(chunks)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        if ex.end == len(raw) and ex.start >= len(raw) - 4:
            return None  # multi-byte char split across recv() boundary
        raise ValueError(
            f"Plugin response contains non-UTF-8 bytes at position {ex.start} — "
            f"this usually means a binary protocol mismatch or corrupted data. "
            f"First {_MAX_RAW_DISPLAY} bytes: {raw[:_MAX_RAW_DISPLAY]!r}"
        ) from ex


def _recv_one(sock: socket.socket) -> dict[str, Any]:
    """Read exactly one JSON object from *sock* and return it as a dict."""
    chunks: list[bytes] = []
    decoder = json.JSONDecoder()
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            raise OSError("Connection closed by plugin before response was received")
        chunks.append(chunk)
        text = _decode_chunks(chunks)
        if text is None:
            continue
        try:
            parsed, _end = decoder.raw_decode(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        snippet = repr(parsed)[:_MAX_RAW_DISPLAY]
        return {
            "status": "error",
            "message": f"Plug-in returned non-object JSON (got {type(parsed).__name__}): {snippet}",
            "raw": parsed,
        }


def _build_payload(command_type: str, params: dict[str, Any]) -> bytes:
    payload: dict = {"type": command_type, "params": params}
    _secret = os.environ.get("RHINO_MCP_PLUGIN_SECRET")
    if _secret:
        payload["secret"] = _secret
    return json.dumps(payload).encode("utf-8")


def _response_timeout_error(timeout: float) -> PluginResponseTimeout:
    return PluginResponseTimeout(
        f"Timed out after {timeout}s waiting for the Rhino plugin to respond. "
        "The command may still be running inside Rhino — it was NOT retried to avoid "
        "duplicate execution. Increase RHINO_MCP_SOCKET_TIMEOUT (or pass a larger "
        "timeout) for long-running operations."
    )


def _attempt(
    command_type: str,
    params: dict[str, Any],
    target_host: str,
    target_port: int,
    target_timeout: float,
) -> dict[str, Any]:
    """One-shot: open connection, send, receive, close."""
    request = _build_payload(command_type, params)
    with socket.create_connection((target_host, target_port), timeout=target_timeout) as sock:
        sock.settimeout(target_timeout)
        sock.sendall(request)
        try:
            return _recv_one(sock)
        except TimeoutError as ex:
            raise _response_timeout_error(target_timeout) from ex


# ---------------------------------------------------------------------------
# Keep-alive connection
# ---------------------------------------------------------------------------

class _KeepAliveConnection:
    """
    Persistent TCP connection to the Rhino plugin.

    A single connection is reused across calls.  If the connection is found to
    be stale (Rhino restarted, MCPStop ran), it is closed and a fresh one is
    opened for that call — transparently to the caller.

    Thread-safe: a lock serialises all send/recv cycles, which also matches
    the Rhino plugin's behaviour of processing one command at a time on the
    UI thread.
    """

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    def send(
        self,
        command_type: str,
        params: dict[str, Any],
        host: str,
        port: int,
        timeout: float,
    ) -> dict[str, Any]:
        request = _build_payload(command_type, params)
        with self._lock:
            # Attempt once on the existing connection, then once on a fresh one.
            for attempt in range(2):
                reused = self._sock is not None
                try:
                    if self._sock is None:
                        self._sock = socket.create_connection((host, port), timeout=timeout)
                    # Apply the caller's timeout on every call — the cached
                    # socket may have been created with a different one.
                    self._sock.settimeout(timeout)
                    self._sock.sendall(request)
                except OSError:
                    self._close()
                    if not reused or attempt == 1:
                        raise
                    continue  # stale cached connection — retry once on a fresh one
                try:
                    return _recv_one(self._sock)
                except TimeoutError as ex:
                    # The request was delivered; Rhino may still be executing
                    # it. Never re-send — that would run the command twice.
                    self._close()
                    raise _response_timeout_error(timeout) from ex
                except ValueError:
                    # Undecodable/foreign bytes: the stream is desynchronized;
                    # drop the connection so leftovers can't corrupt later calls.
                    self._close()
                    raise
                except OSError:
                    self._close()
                    # A reused connection may have been closed while idle
                    # (Rhino restart, MCPStop) before reading our request —
                    # one transparent retry on a fresh connection is safe.
                    # On a fresh connection the plugin may have started work,
                    # so do not retry.
                    if not reused or attempt == 1:
                        raise
            raise OSError("unreachable")  # pragma: no cover

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def close(self) -> None:
        with self._lock:
            self._close()


_keepalive = _KeepAliveConnection()


def _keepalive_enabled() -> bool:
    return os.environ.get("RHINO_MCP_KEEPALIVE", "1") not in ("0", "false", "no")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_command(
    command_type: str,
    params: dict[str, Any] | None = None,
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
    retries: int | None = None,
) -> dict[str, Any]:
    """
    Send one command to a RhinoMCP-compatible plug-in socket server.

    In keep-alive mode (default) the TCP connection is reused across calls.
    Set RHINO_MCP_KEEPALIVE=0 to open a new connection for every call.

    Retries on ``OSError`` (connection refused, reset) with exponential backoff.
    ``retries`` defaults to ``RHINO_MCP_SOCKET_RETRIES`` env var (default 2).
    Set to 0 to disable retries.
    """
    target_host, target_port, target_timeout = connection_settings(host, port, timeout)
    max_retries = retries if retries is not None else int(
        os.environ.get("RHINO_MCP_SOCKET_RETRIES", str(DEFAULT_RETRIES))
    )
    payload = params or {}
    delay = DEFAULT_RETRY_DELAY
    last_exc: OSError | None = None

    for attempt in range(max_retries + 1):
        try:
            if _keepalive_enabled():
                return _keepalive.send(command_type, payload, target_host, target_port, target_timeout)
            return _attempt(command_type, payload, target_host, target_port, target_timeout)
        except PluginResponseTimeout:
            # The command was delivered and may still be running in Rhino —
            # retrying would execute it again.
            raise
        except OSError as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2

    total_attempts = max_retries + 1
    raise OSError(
        f"Could not connect to Rhino plugin at {target_host}:{target_port} after {total_attempts} attempt(s): {last_exc}. "
        "Ensure Rhino is running with MCPStart active. "
        "If using Docker or a remote host, verify RHINO_MCP_HOST and RHINO_MCP_PORT are set correctly."
    ) from last_exc


def probe(timeout: float = 1.0) -> dict[str, Any]:
    """
    Return whether a RhinoMCP-style socket appears reachable (TCP only).
    """
    host, port, _ = connection_settings(timeout=timeout)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "host": host, "port": port}
    except OSError as ex:
        return {"ok": False, "host": host, "port": port, "message": str(ex)}


def health_check(timeout: float = 3.0) -> dict[str, Any]:
    """
    Send a ``ping`` command and verify the server responds correctly.

    Returns ``{"ok": True, "version": ..., "rhino": ..., "latency_ms": ...}``
    on success, or ``{"ok": False, "error": ..., "error_code": ...}`` on failure.
    """
    host, port, _ = connection_settings()
    t0 = time.monotonic()
    try:
        resp = send_command("ping", {}, timeout=timeout, retries=0)
        latency = round((time.monotonic() - t0) * 1000, 1)
        is_ok = resp.get("ok") is True or resp.get("status") == "ok"
        if is_ok:
            inner = resp.get("result", resp)
            if not isinstance(inner, dict):
                inner = resp
            return {
                "ok": True,
                "host": host,
                "port": port,
                "latency_ms": latency,
                "version": inner.get("version"),
                "rhino": inner.get("rhino"),
                "host_app": inner.get("host_app", "Rhino"),
            }
        snippet = repr(resp)[:_MAX_RAW_DISPLAY]
        return {
            "ok": False,
            "host": host,
            "port": port,
            "error": (
                f"Ping command succeeded but the response was not a success acknowledgment. "
                f"This may indicate a version mismatch between the Python server and the Rhino plugin. "
                f"Response: {snippet}"
            ),
            "error_code": "HEALTH_CHECK_FAILED",
            "raw": resp,
        }
    except OSError as ex:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "error": str(ex),
            "error_code": "SOCKET_UNAVAILABLE",
            "hint": "Ensure Rhino is running and MCPStart has been executed inside Rhino.",
        }

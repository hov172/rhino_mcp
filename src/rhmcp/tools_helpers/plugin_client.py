"""
Client for RhinoMCP-style plug-in socket servers.
"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1999
DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2        # extra attempts after the first (total = retries + 1)
DEFAULT_RETRY_DELAY = 0.5  # seconds before first retry; doubles each attempt


def connection_settings(
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> tuple[str, int, float]:
    return (
        host or os.environ.get("RHINO_MCP_HOST", DEFAULT_HOST),
        port or int(os.environ.get("RHINO_MCP_PORT", str(DEFAULT_PORT))),
        timeout or float(os.environ.get("RHINO_MCP_SOCKET_TIMEOUT", str(DEFAULT_TIMEOUT))),
    )


_MAX_RAW_DISPLAY = 200  # chars of raw response shown in error messages


def _decode_chunks(chunks: list[bytes]) -> str:
    """Decode accumulated chunks as UTF-8, raising ValueError on binary/non-UTF-8 data."""
    raw = b"".join(chunks)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as ex:
        raise ValueError(
            f"Plugin response contains non-UTF-8 bytes at position {ex.start} — "
            f"this usually means a binary protocol mismatch or corrupted data. "
            f"First {_MAX_RAW_DISPLAY} bytes: {raw[:_MAX_RAW_DISPLAY]!r}"
        ) from ex


def _attempt(
    command_type: str,
    params: dict[str, Any],
    target_host: str,
    target_port: int,
    target_timeout: float,
) -> dict[str, Any]:
    payload: dict = {"type": command_type, "params": params}
    _secret = os.environ.get("RHINO_MCP_PLUGIN_SECRET")
    if _secret:
        payload["secret"] = _secret
    request = json.dumps(payload).encode("utf-8")
    with socket.create_connection((target_host, target_port), timeout=target_timeout) as sock:
        sock.settimeout(target_timeout)
        sock.sendall(request)
        chunks: list[bytes] = []
        decoder = json.JSONDecoder()
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
            text = _decode_chunks(chunks)  # raises ValueError on binary data
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
    # Connection closed without a complete JSON object
    try:
        raw_text = _decode_chunks(chunks)
    except ValueError as ex:
        return {"status": "error", "message": str(ex), "error_code": "BINARY_RESPONSE"}
    snippet = raw_text[:_MAX_RAW_DISPLAY]
    total = len(raw_text)
    return {
        "status": "error",
        "message": (
            f"Connection to {target_host}:{target_port} closed before a complete JSON response was received "
            f"({total} bytes received). "
            + (f"Response preview: {snippet!r}" if raw_text else "No data received — the plugin may have crashed or timed out.")
        ),
        "error_code": "INCOMPLETE_RESPONSE",
        "raw": raw_text,
    }


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
            return _attempt(command_type, payload, target_host, target_port, target_timeout)
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

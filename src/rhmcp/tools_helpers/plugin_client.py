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


def _attempt(
    command_type: str,
    params: dict[str, Any],
    target_host: str,
    target_port: int,
    target_timeout: float,
) -> dict[str, Any]:
    request = json.dumps({"type": command_type, "params": params}).encode("utf-8")
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
            text = b"".join(chunks).decode("utf-8", errors="replace")
            try:
                parsed, _end = decoder.raw_decode(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
            return {"status": "error", "message": "Plug-in returned non-object JSON.", "raw": parsed}
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    return {"status": "error", "message": "Incomplete or invalid JSON response", "raw": raw}


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

    raise last_exc  # type: ignore[misc]


def probe(timeout: float = 1.0) -> dict[str, Any]:
    """
    Return whether a RhinoMCP-style socket appears reachable.
    """
    host, port, _ = connection_settings(timeout=timeout)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "host": host, "port": port}
    except OSError as ex:
        return {"ok": False, "host": host, "port": port, "message": str(ex)}

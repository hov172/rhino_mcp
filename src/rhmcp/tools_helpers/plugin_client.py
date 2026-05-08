"""
Client for RhinoMCP-style plug-in socket servers.
"""

from __future__ import annotations

import json
import os
import socket
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1999
DEFAULT_TIMEOUT = 15.0


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


def send_command(
    command_type: str,
    params: dict[str, Any] | None = None,
    host: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """
    Send one command to a RhinoMCP-compatible plug-in socket server.
    """
    target_host, target_port, target_timeout = connection_settings(host, port, timeout)
    request = json.dumps({"type": command_type, "params": params or {}}).encode("utf-8")
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

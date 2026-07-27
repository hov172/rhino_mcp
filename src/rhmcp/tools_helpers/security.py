"""Shared security guards used across rhino_mcp tools."""
from __future__ import annotations

import ipaddress
import os
import socket
import zipfile
from typing import BinaryIO
from urllib.parse import urlparse

# Characters that break Rhino macro strings when embedded between double-quotes.
_RHINO_MACRO_STRIP = str.maketrans("", "", '"\r\n')


def sanitise_rhino_path(path: str) -> str:
    """
    Remove characters that would break a Rhino macro string literal.

    Rhino macros embed paths as: _-Export "«path»" _Enter
    A double-quote inside «path» terminates the string and allows injection.
    Newlines also break the macro parser.
    """
    return path.translate(_RHINO_MACRO_STRIP)


# Private/link-local IPv4 and IPv6 ranges that must never be fetched.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),  # "this network" — 0.0.0.0 reaches loopback
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private(host: str) -> bool:
    """
    True if *host* resolves to any blocked (private/link-local) address.

    Checks every resolved address (A and AAAA) — checking only the first
    record lets an attacker hide a private address behind a public one.
    Callers should validate immediately before fetching to keep the
    validate-to-fetch window minimal.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError):
        # Unresolvable — treat as private to be safe.
        return True
    addrs = []
    for _family, _type, _proto, _canonname, sockaddr in infos:
        try:
            addrs.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            return True
    if not addrs:
        return True
    return any(addr in net for addr in addrs for net in _BLOCKED_NETWORKS)


def validate_download_url(url: str) -> None:
    """
    Raise ValueError if *url* is not a safe remote HTTPS URL.

    Blocks: non-https schemes, local file paths, private/link-local IP ranges.
    """
    if url.startswith("/") or url.startswith("file="):
        raise ValueError("local path not allowed as download URL")

    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"scheme '{parsed.scheme}' not allowed — only https is permitted")

    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL has no host")

    if _is_private(host):
        raise ValueError(f"private/internal host '{host}' not allowed")


def clamp(value: int, lo: int, hi: int) -> int:
    """Return *value* clamped to [lo, hi]."""
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Execution safety gates
# ---------------------------------------------------------------------------

# Env vars that disable arbitrary-code execution tools.
# Default is enabled (1) so existing deployments are unaffected.
# Set to "0" / "false" / "no" to refuse execution at runtime.
_GATE_DISABLED = frozenset(("0", "false", "no"))


def check_execution_gate(env_var: str, tool_name: str) -> dict | None:
    """
    Return an error dict if the execution gate *env_var* is turned off,
    or ``None`` if the tool is allowed to proceed.

    Usage::

        err = check_execution_gate("RHINO_MCP_ENABLE_RHINOSCRIPT", "execute_rhino_python")
        if err:
            return err
    """
    if os.environ.get(env_var, "1").lower() in _GATE_DISABLED:
        return {
            "ok": False,
            "error": (
                f"'{tool_name}' is disabled by server configuration. "
                f"Set {env_var}=1 to enable it."
            ),
            "error_code": "TOOL_DISABLED",
        }
    return None


# ---------------------------------------------------------------------------
# Remote host guard
# ---------------------------------------------------------------------------

_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "::1", "localhost", ""))


def check_remote_allowed(host: str) -> None:
    """
    Raise ``PermissionError`` if *host* is not a loopback address and
    ``RHINO_MCP_ALLOW_REMOTE`` is not set to ``1`` / ``true`` / ``yes``.

    Call this inside ``connection_settings`` to enforce the default
    loopback-only policy for the Rhino plugin bridge.
    """
    if host.lower() in _LOOPBACK_HOSTS:
        return
    allowed = os.environ.get("RHINO_MCP_ALLOW_REMOTE", "0").lower()
    if allowed not in ("1", "true", "yes"):
        raise PermissionError(
            f"Remote Rhino plugin host '{host}' is not allowed by default. "
            "Set RHINO_MCP_ALLOW_REMOTE=1 to permit connections to non-loopback hosts."
        )


def safe_extractall(source: "str | BinaryIO", dest_dir: str) -> None:
    """
    Extract a zip archive to *dest_dir* while blocking Zip Slip attacks.

    Raises ValueError if any member path resolves outside *dest_dir*.
    """
    real_dest = os.path.realpath(dest_dir)
    with zipfile.ZipFile(source, "r") as zf:
        for member in zf.namelist():
            member_real = os.path.realpath(os.path.join(real_dest, member))
            if not member_real.startswith(real_dest + os.sep) and member_real != real_dest:
                raise ValueError(f"Zip slip detected: '{member}' resolves outside extract dir")
        zf.extractall(dest_dir)

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
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_private(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(socket.gethostbyname(host))
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except (socket.gaierror, ValueError):
        # Unresolvable or malformed — treat as private to be safe.
        return True


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

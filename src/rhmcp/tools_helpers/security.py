"""Shared security guards for rhino_mcp tools."""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
import zipfile
from typing import BinaryIO


def sanitise_rhino_path(path: str) -> str:
    """Remove " \\r \\n from path — these break Rhino macro strings embedded as: _-Export "«path»" _Enter"""
    table = str.maketrans("", "", '"\r\n')
    return path.translate(table)


def validate_download_url(url: str) -> None:
    """Raise ValueError if url is not a safe remote HTTPS URL.

    Blocks: local paths (starts with / or file=), non-https schemes,
    private/link-local IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x, ::1, fc00::/7).
    Uses socket.gethostbyname to resolve hostname before checking ranges.
    If hostname is unresolvable, treat as private (raise ValueError).
    """
    # Block bare local paths and file= style strings before URL parsing
    if url.startswith("/"):
        raise ValueError("local path not allowed")
    if url.lower().startswith("file="):
        raise ValueError("local path not allowed")

    parsed = urllib.parse.urlparse(url)

    # Enforce https scheme only
    if parsed.scheme != "https":
        raise ValueError(f"URL scheme '{parsed.scheme}' not allowed; only https is permitted")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    # Resolve hostname to IP
    try:
        resolved_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        raise ValueError(f"private or unresolvable hostname: {hostname}")

    # Check if the resolved IP is in a private/link-local range
    try:
        addr = ipaddress.ip_address(resolved_ip)
    except ValueError:
        raise ValueError(f"invalid IP address resolved from hostname: {hostname}")

    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise ValueError(f"private/reserved IP address blocked: {resolved_ip}")

    # Also check fc00::/7 for IPv6 (unique local) - covered by is_private in Python 3.11+
    # But explicitly handle for older Pythons
    if isinstance(addr, ipaddress.IPv6Address):
        if int(addr) >> 121 == 0x7E:  # fc00::/7
            raise ValueError(f"private/reserved IP address blocked: {resolved_ip}")


def clamp(value: int, lo: int, hi: int) -> int:
    """Return value clamped to [lo, hi]."""
    return max(lo, min(hi, value))


def safe_extractall(source: "str | BinaryIO", dest_dir: str) -> None:
    """Extract zip to dest_dir, raising ValueError('Zip slip detected: ...') if any member resolves outside dest_dir.

    Uses os.path.realpath to detect traversal. After validation passes, calls zf.extractall(dest_dir).
    """
    real_dest = os.path.realpath(dest_dir)

    with zipfile.ZipFile(source) as zf:
        for member in zf.namelist():
            member_path = os.path.realpath(os.path.join(dest_dir, member))
            if not member_path.startswith(real_dest + os.sep) and member_path != real_dest:
                raise ValueError(f"Zip slip detected: {member}")
        zf.extractall(dest_dir)

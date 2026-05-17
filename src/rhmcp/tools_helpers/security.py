"""
Security helpers shared across rhmcp tools.

Functions
---------
sanitise_rhino_path  -- strip characters that could break a Rhino macro string
validate_download_url -- reject non-HTTP(S) and private/loopback URLs
clamp                -- bound a numeric value to [lo, hi]
safe_extractall      -- extract a zip archive, blocking Zip Slip path traversal
"""

from __future__ import annotations

import ipaddress
import os
import zipfile
from pathlib import Path
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# H-1 helper
# ---------------------------------------------------------------------------

_RHINO_MACRO_DANGEROUS = ('"', '\n', '\r', '\0')


def sanitise_rhino_path(path: str) -> str:
    """
    Return *path* with characters that could break a Rhino macro string removed.

    Rhino macro strings embed paths inside double-quoted tokens, so an embedded
    double-quote would terminate the token early.  Newlines and null bytes could
    allow injection of additional macro commands.

    Raises ``ValueError`` if *path* becomes empty after sanitisation.
    """
    cleaned = path
    for ch in _RHINO_MACRO_DANGEROUS:
        cleaned = cleaned.replace(ch, "")
    if not cleaned.strip():
        raise ValueError(f"Path is empty or invalid after sanitisation: {path!r}")
    return cleaned


# ---------------------------------------------------------------------------
# M-3 helper
# ---------------------------------------------------------------------------

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_download_url(url: str) -> None:
    """
    Raise ``ValueError`` if *url* is not a safe remote HTTP/HTTPS URL.

    Blocks:
    - Non-HTTP(S) schemes (file://, ftp://, local paths starting with '/' or 'file=')
    - Loopback and private-network hostnames
    - Empty or missing hostnames
    """
    if not url:
        raise ValueError("Download URL must not be empty.")

    # Block local-path shortcuts used by Gradio (handled by caller separately if needed)
    if url.startswith("/") or url.startswith("file="):
        raise ValueError(f"Local file paths are not permitted as download URLs: {url!r}")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Only http/https download URLs are permitted; got scheme {scheme!r}.")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Download URL has no hostname.")

    # Reject loopback / link-local / private addresses
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_NETWORKS:
            if addr in net:
                raise ValueError(f"Download URL targets a private/loopback address: {hostname!r}")
    except ValueError as exc:
        # ip_address() raises ValueError for non-IP hostnames — check textually
        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "::1") or hostname_lower.endswith(".local"):
            raise ValueError(f"Download URL targets a local hostname: {hostname!r}") from exc
        # Non-IP public hostname — allow it
        if "private/loopback" in str(exc):
            raise


# ---------------------------------------------------------------------------
# M-4 helper
# ---------------------------------------------------------------------------

def clamp(value: int | float, lo: int | float, hi: int | float) -> int | float:
    """Return *value* clamped to the inclusive range [lo, hi]."""
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# H-4 helper
# ---------------------------------------------------------------------------

def safe_extractall(zip_path: str | os.PathLike[str], dest_dir: str | os.PathLike[str]) -> None:
    """
    Extract all members of *zip_path* into *dest_dir*, blocking Zip Slip.

    Raises:
        zipfile.BadZipFile  -- if the archive is corrupt or not a zip file
        ValueError          -- if any member path would escape *dest_dir*
    """
    dest = Path(dest_dir).resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            member_path = (dest / member).resolve()
            try:
                member_path.relative_to(dest)
            except ValueError:
                raise ValueError(
                    f"Zip Slip blocked: archive member {member!r} would extract outside "
                    f"destination directory {str(dest)!r}."
                )
        zf.extractall(dest)

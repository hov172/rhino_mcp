"""
Input validators for MCP tool parameters.

Each function returns an error-dict (``{"ok": False, ...}``) when the value is
invalid, or ``None`` when it is acceptable.  Tools can call these at the top of
their body and return the error directly:

    err = validate.guid(object_id, "object_id")
    if err: return err
"""

from __future__ import annotations

import re
from typing import Any

_GUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def guid(value: Any, field: str = "id") -> dict[str, Any] | None:
    """Validate a GUID string (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."""
    if not isinstance(value, str) or not _GUID_RE.match(value):
        return {
            "ok": False,
            "error": f"{field} must be a valid GUID string (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx), got: {value!r}",
            "error_code": "INVALID_GUID",
        }
    return None


def color(value: Any, field: str = "color") -> dict[str, Any] | None:
    """Validate an RGB or RGBA color list/tuple (each component 0–255)."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) not in (3, 4):
        return {
            "ok": False,
            "error": f"{field} must be a list of 3 (RGB) or 4 (RGBA) integers 0–255, got: {value!r}",
            "error_code": "INVALID_COLOR",
        }
    if not all(isinstance(c, int) and 0 <= c <= 255 for c in value):
        return {
            "ok": False,
            "error": f"{field} values must be integers in range 0–255, got: {list(value)!r}",
            "error_code": "INVALID_COLOR",
        }
    return None


def layer_name(value: Any, field: str = "layer") -> dict[str, Any] | None:
    """Validate a non-empty layer name string."""
    if not isinstance(value, str) or not value.strip():
        return {
            "ok": False,
            "error": f"{field} must be a non-empty string, got: {value!r}",
            "error_code": "INVALID_LAYER_NAME",
        }
    return None


def coordinate(value: Any, field: str = "point") -> dict[str, Any] | None:
    """Validate a 3-element [x, y, z] coordinate."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return {
            "ok": False,
            "error": f"{field} must be a list of 3 numbers [x, y, z], got: {value!r}",
            "error_code": "INVALID_COORDINATE",
        }
    if not all(isinstance(c, (int, float)) for c in value):
        return {
            "ok": False,
            "error": f"{field} values must be numbers, got: {list(value)!r}",
            "error_code": "INVALID_COORDINATE",
        }
    return None


def positive(value: Any, field: str = "value") -> dict[str, Any] | None:
    """Validate a strictly positive number."""
    if not isinstance(value, (int, float)) or value <= 0:
        return {
            "ok": False,
            "error": f"{field} must be a positive number, got: {value!r}",
            "error_code": "INVALID_VALUE",
        }
    return None


def non_negative(value: Any, field: str = "value") -> dict[str, Any] | None:
    """Validate a non-negative number (>= 0)."""
    if not isinstance(value, (int, float)) or value < 0:
        return {
            "ok": False,
            "error": f"{field} must be >= 0, got: {value!r}",
            "error_code": "INVALID_VALUE",
        }
    return None


def guid_list(values: Any, field: str = "ids") -> dict[str, Any] | None:
    """Validate a non-empty list of GUID strings."""
    if not isinstance(values, (list, tuple)) or not values:
        return {
            "ok": False,
            "error": f"{field} must be a non-empty list of GUID strings",
            "error_code": "INVALID_GUID_LIST",
        }
    for i, v in enumerate(values):
        err = guid(v, f"{field}[{i}]")
        if err:
            return err
    return None

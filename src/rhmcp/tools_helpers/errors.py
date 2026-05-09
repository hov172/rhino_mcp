"""
Shared response helpers — every tool should return through ok() or err()
so callers always see a consistent shape:

    {"ok": true/false, "error"?: "...", "error_code"?: "...", ...rest}
"""

from __future__ import annotations

from typing import Any


def ok(data: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    """Successful tool response."""
    return {"ok": True, **(data or {}), **extra}


def err(
    message: str,
    code: str = "ERROR",
    **extra: Any,
) -> dict[str, Any]:
    """
    Failed tool response.

    ``code`` is a short SCREAMING_SNAKE identifier for programmatic handling,
    e.g. ``NOT_FOUND``, ``INVALID_PARAM``, ``RHINO_ERROR``.
    """
    return {"ok": False, "error": message, "error_code": code, **extra}


def normalize(resp: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure every backend response has ``ok`` and, when ok=False, ``error``.

    Applied automatically inside backend.py so individual tools don't need
    to call this explicitly.
    """
    if not isinstance(resp, dict):
        return {"ok": False, "error": repr(resp), "error_code": "BAD_RESPONSE"}

    # Infer ok from legacy status/success fields when absent.
    if "ok" not in resp:
        if resp.get("status") == "error" or resp.get("success") is False:
            resp["ok"] = False
        else:
            resp["ok"] = True

    # Ensure error message is always present on failure.
    if not resp["ok"] and "error" not in resp:
        resp["error"] = (
            resp.get("message")
            or resp.get("error_message")
            or resp.get("details")
            or "Unknown error"
        )
        resp.setdefault("error_code", "ERROR")

    return resp

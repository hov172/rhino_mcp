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


_MAX_REPR_LEN = 300  # max chars for repr() in error messages to avoid flooding logs


def normalize(resp: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure every backend response has ``ok`` and, when ok=False, ``error``.

    Applied automatically inside backend.py so individual tools don't need
    to call this explicitly.
    """
    if not isinstance(resp, dict):
        raw = repr(resp)
        if len(raw) > _MAX_REPR_LEN:
            raw = raw[:_MAX_REPR_LEN] + f"… (truncated, full length {len(raw)})"
        return {"ok": False, "error": f"Backend returned a non-dict response: {raw}", "error_code": "BAD_RESPONSE"}

    # Infer ok from legacy status/success fields when absent.
    if "ok" not in resp:
        if resp.get("status") == "error" or resp.get("success") is False:
            resp["ok"] = False
        else:
            resp["ok"] = True

    # Ensure error message is always present and non-empty on failure.
    if not resp["ok"]:
        if not resp.get("error"):
            resp["error"] = (
                resp.get("message")
                or resp.get("error_message")
                or resp.get("details")
                or "Unknown error — the plugin returned ok=false with no message"
            )
        resp.setdefault("error_code", "ERROR")

    return resp

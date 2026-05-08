"""
Optional usage telemetry for rhino-mcp.

Disabled by default.  Enable with:

    export RHINO_MCP_TELEMETRY=1

Events are appended as newline-delimited JSON to:

    ~/.rhino_mcp_telemetry.jsonl   (default)

Override the path with:

    export RHINO_MCP_TELEMETRY_LOG=/path/to/custom.jsonl

Each line is one JSON object:
    {
        "ts":    "2026-05-08T18:30:00.000000+00:00",  # ISO-8601 UTC
        "tool":  "capture_rhino_view",                 # MCP tool name
        "ms":    142,                                  # wall-clock duration ms
        "ok":    true,                                 # false if an exception was raised
        "error": null                                  # exception class + message, or null
    }

Telemetry is fire-and-forget: any I/O error in _write() is silently swallowed
so a broken log path never interrupts a tool call.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

ENABLED: bool = os.environ.get("RHINO_MCP_TELEMETRY", "").lower() in ("1", "true", "yes")

LOG_PATH: Path = Path(
    os.environ.get(
        "RHINO_MCP_TELEMETRY_LOG",
        str(Path.home() / ".rhino_mcp_telemetry.jsonl"),
    )
)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _write(event: dict) -> None:
    """Append one telemetry event to the log file.  Never raises."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001
        pass


# ── Public API ───────────────────────────────────────────────────────────────

def install(mcp) -> None:  # type: ignore[type-arg]
    """
    Wrap FastMCP's tool-manager call_tool() to record one event per invocation.

    Must be called after all tools are registered and before mcp.run().
    Does nothing when RHINO_MCP_TELEMETRY is not set.

    The patch is applied to the bound method on _tool_manager so that normal
    FastMCP internals (structured output, context injection, etc.) still run
    unchanged inside the original call_tool.
    """
    if not ENABLED:
        return

    original_call_tool = mcp._tool_manager.call_tool

    async def _instrumented(
        name: str,
        arguments: dict,
        context=None,
        convert_result: bool = False,
    ):
        start = time.monotonic()
        exc_str: str | None = None
        try:
            return await original_call_tool(
                name, arguments, context=context, convert_result=convert_result
            )
        except Exception as exc:  # noqa: BLE001
            exc_str = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _write(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "tool": name,
                    "ms": round((time.monotonic() - start) * 1000),
                    "ok": exc_str is None,
                    "error": exc_str,
                }
            )

    mcp._tool_manager.call_tool = _instrumented

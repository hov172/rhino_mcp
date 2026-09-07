"""Bounded PDF requests; parsers run only in disposable child processes."""

from __future__ import annotations

from contextvars import ContextVar
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import time

MAX_INPUT = 50 * 1024 * 1024
MAX_OUTPUT = 24 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 32_000_000
MAX_ITEMS = 10_000
MAX_TEXT = 200_000
TIMEOUT = 30
MEMORY_LIMIT = 768 * 1024 * 1024
_WORKERS = threading.BoundedSemaphore(2)
cancellation = ContextVar("pdf_cancellation", default=None)


class PDFError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def failure(code: str, message: str) -> dict:
    return {"ok": False, "error": message, "error_code": code}


def number(value, name, low, high=None, integer=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < low
        or (high is not None and value > high)
        or (integer and not isinstance(value, int))
    ):
        raise PDFError(
            "INVALID_VALUE",
            f"{name} must be a finite {'integer' if integer else 'number'} from {low}"
            + (f" to {high}." if high is not None else "."),
        )
    return value


def select_pages(spec, count, limit):
    if count < 1 or count > 10000:
        raise PDFError("PDF_LIMIT_EXCEEDED", "PDF must contain 1–10000 pages.")
    if spec is None or spec == "":
        return list(range(min(count, limit))), count > limit
    if not isinstance(spec, str) or len(spec) > 1024:
        raise PDFError(
            "INVALID_PAGE_RANGE",
            "Page selection must be a string of at most 1024 characters.",
        )
    selected = set()
    try:
        for part in spec.split(","):
            values = part.strip().split("-")
            if len(values) not in (1, 2) or not all(
                v.strip().isdigit() for v in values
            ):
                raise ValueError
            lo, hi = (int(values[0]), int(values[-1]))
            if not 1 <= lo <= hi <= count:
                raise ValueError
            selected.update(range(lo - 1, hi))
    except ValueError as exc:
        raise PDFError(
            "INVALID_PAGE_RANGE",
            f"Pages must be within 1–{count}, with ascending ranges.",
        ) from exc
    indices = sorted(selected)
    return indices[:limit], len(indices) > limit


def request(operation: str, path: str, **options) -> dict:
    """Validate before starting a worker; snapshot the file to bound input reads."""
    from rhmcp.tools.documents import _validate_read_path

    try:
        path = _validate_read_path(path)
        number(options.get("dpi", 150), "dpi", 50, 600, integer=True)
        number(options.get("max_pages", 10), "max_pages", 1, 50, integer=True)
        number(options.get("min_length_px", 0), "min_length_px", 0)
        for key in ("real_units_per_px", "real_units_per_point"):
            if options.get(key) is not None:
                number(options[key], key, sys.float_info.min)
        if (
            options.get("real_units_per_px") is not None
            and options.get("real_units_per_point") is not None
        ):
            raise PDFError("INVALID_VALUE", "Supply one scale ratio, not both.")
        if options.get("real_unit", "feet") not in {"feet", "meters", "inches", "mm"}:
            raise PDFError(
                "INVALID_VALUE", "real_unit must be feet, meters, inches, or mm."
            )
        if Path(path).suffix.lower() != ".pdf":
            raise PDFError("INVALID_PDF", "Expected a .pdf file.")
    except PDFError as exc:
        return failure(exc.code, str(exc))
    except (ValueError, TypeError, OSError):
        return failure(
            "INVALID_PATH", "PDF path is invalid or outside allowed read roots."
        )
    if not _WORKERS.acquire(blocking=False):
        return failure(
            "PDF_BUSY", "Two PDF operations are already running; retry later."
        )
    try:
        with tempfile.TemporaryDirectory(prefix="rhmcp-pdf-") as directory:
            snapshot = Path(directory) / "input.pdf"
            output = Path(directory) / "result.json"
            # Do not block on a FIFO or follow a final symlink swapped after validation.
            fd = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            with os.fdopen(fd, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise PDFError("INVALID_PDF", "PDF input must be a regular file.")
                if info.st_size > MAX_INPUT:
                    raise PDFError(
                        "PDF_LIMIT_EXCEEDED", "PDF exceeds the 50 MiB input limit."
                    )
                data = source.read(MAX_INPUT + 1)
            if len(data) > MAX_INPUT:
                raise PDFError(
                    "PDF_LIMIT_EXCEEDED", "PDF exceeds the 50 MiB input limit."
                )
            if not data.startswith(b"%PDF-"):
                raise PDFError("INVALID_PDF", "File does not have a PDF header.")
            snapshot.write_bytes(data)
            del data
            payload = dict(
                options, operation=operation, path=str(snapshot), output=str(output)
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
            import psutil

            with subprocess.Popen(
                [sys.executable, "-m", "rhmcp.tools_helpers.pdf_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env,
            ) as process:
                started = time.monotonic()
                pending = json.dumps(payload)
                monitor = psutil.Process(process.pid)
                while True:
                    try:
                        process.communicate(input=pending, timeout=0.1)
                        break
                    except subprocess.TimeoutExpired:
                        pending = None
                        cancelled = cancellation.get()
                        if cancelled is not None and cancelled.is_set():
                            process.kill()
                            process.communicate()
                            return failure("PDF_CANCELLED", "PDF request cancelled; worker terminated.")
                        if time.monotonic() - started > TIMEOUT:
                            process.kill()
                            process.communicate()
                            return failure(
                                "PDF_TIMEOUT",
                                "PDF processing timed out; the worker was terminated.",
                            )
                        try:
                            memory = monitor.memory_info().rss
                        except psutil.NoSuchProcess:
                            continue
                        except psutil.Error:
                            process.kill()
                            process.communicate()
                            return failure(
                                "PDF_WORKER_FAILED",
                                "Cannot monitor PDF worker resources.",
                            )
                        if memory > MEMORY_LIMIT:
                            process.kill()
                            process.communicate()
                            return failure(
                                "PDF_LIMIT_EXCEEDED",
                                "PDF worker exceeded 768 MiB of memory.",
                            )
                if process.returncode != 0 or not output.is_file():
                    return failure(
                        "PDF_WORKER_FAILED",
                        "PDF worker failed or exceeded its resource limit.",
                    )
            if output.stat().st_size > MAX_OUTPUT:
                return failure("PDF_LIMIT_EXCEEDED", "PDF output exceeds 24 MiB.")
            result = json.loads(output.read_text())
            if not isinstance(result, dict) or "ok" not in result:
                raise ValueError("Invalid worker output")
            if result["ok"]:
                result["path"] = path
            return result
    except PDFError as exc:
        return failure(exc.code, str(exc))
    except FileNotFoundError:
        return failure("FILE_NOT_FOUND", "PDF file not found.")
    except (OSError, ValueError):
        return failure("PDF_PROCESSING_FAILED", "Unable to read or process PDF.")
    finally:
        _WORKERS.release()

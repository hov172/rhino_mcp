"""
Tools for reading local document files so AI agents can inspect
design drawings, floor plans, spreadsheets, and specifications
without leaving the MCP session.

Supported formats
-----------------
PDF    read_pdf, get_pdf_info   (PDFium + pdfplumber)
Image  read_image               (Pillow; pillow-heif adds HEIC support)
Sheet  read_spreadsheet         (stdlib csv  +  openpyxl for .xlsx/.xls)
SVG    read_svg                 (stdlib xml.etree — no extra dependency)
DOCX   read_docx               (python-docx)
"""

from __future__ import annotations

import base64
import csv as _csv
import io
import os
import re
import sys
import xml.etree.ElementTree as _ET

# On macOS, cairocffi's CFFI-based dlopen won't find Homebrew's libcairo
# unless DYLD_LIBRARY_PATH is set before the first import of cairocffi.
# Set it here (module load time) so it's in place when read_svg triggers
# the lazy import of cairosvg → cairocffi.
def _configure_cairo_path() -> None:
    if sys.platform != "darwin":
        return
    candidates = ["/opt/homebrew/lib", "/usr/local/lib"]
    existing = os.environ.get("DYLD_LIBRARY_PATH", "")
    parts = existing.split(":") if existing else []
    for c in candidates:
        if os.path.isdir(c) and c not in parts:
            parts.insert(0, c)
    os.environ["DYLD_LIBRARY_PATH"] = ":".join(p for p in parts if p)

_configure_cairo_path()
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS  = {".png", ".jpg", ".jpeg", ".tif", ".tiff",
                ".bmp", ".webp", ".heic", ".heif", ".gif"}
_SHEET_EXTS  = {".csv", ".xlsx", ".xls"}
_SVG_EXTS    = {".svg", ".svgz"}
_DOCX_EXTS   = {".docx"}
_PDF_EXTS    = {".pdf"}


def _b64_png(img: Any) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _parse_scale_hint(hint: str) -> tuple[float, str]:
    """Parse a drawing scale string and return (paper_inches_per_real_unit, real_unit).

    Supported formats
    -----------------
    Architectural imperial  ``1/4" = 1'``  ``1/8" = 1'-0"``  ``1" =..."""
    hint = hint.strip()

    # Metric ratio: 1:100, 1:50, 1 : 200
    m = re.match(r'^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$', hint)
    if m:
        paper_val = float(m.group(1))
        real_val = float(m.group(2))
        # paper_val mm = real_val mm  →  1 m real = (paper_val/real_val)*1000 mm on paper
        # convert paper mm → paper inches: * (1/25.4)
        paper_in_per_real_m = (paper_val / real_val) * 1000.0 / 25.4
        return paper_in_per_real_m, "meters"

    # Imperial: {frac}" = {feet}['-{inches}"]
    # Matches: 1/4" = 1'  |  1/4" = 1'-0"  |  1" = 10'  |  3/16" = 1'
    m = re.match(
        r'^(\d+(?:[./]\d+)?)\s*(?:in|inch(?:es)?|")?\s*=\s*'
        r'(\d+(?:\.\d+)?)\s*(?:\'|ft|feet|foot)'
        r'(?:[^\d]*(\d+(?:\.\d+)?)\s*(?:"|in))?',
        hint, re.IGNORECASE,
    )
    if m:
        paper_str = m.group(1)
        if '/' in paper_str:
            num, den = paper_str.split('/')
            paper_inches = float(num) / float(den)
        else:
            paper_inches = float(paper_str)

        real_feet = float(m.group(2))
        real_extra_in = float(m.group(3)) if m.group(3) else 0.0
        real_feet_total = real_feet + real_extra_in / 12.0

        return paper_inches / real_feet_total, "feet"

    raise ValueError(
        f"Unrecognised scale format: {hint!r}. "
        "Use '1/4\" = 1\\'', '1/8\" = 1\\'-0\"', '1:100', etc."
    )


# ---------------------------------------------------------------------------
# R7-2: Path allow-list helper
# ---------------------------------------------------------------------------

def _validate_read_path(path: str) -> str:
    """Restrict read paths to user home dir or env-configured roots (R7-2)."""
    import pathlib
    resolved = pathlib.Path(path).expanduser().resolve()

    raw_roots = os.environ.get("RHINO_MCP_READ_ROOTS", "")
    if raw_roots:
        allowed_roots = [
            pathlib.Path(r).resolve()
            for r in raw_roots.split(os.pathsep)
            if r
        ]
    else:
        allowed_roots = [pathlib.Path.home().resolve()]

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return str(resolved)
        except ValueError:
            continue

    raise ValueError(
        f"Path {path!r} is outside allowed read roots. "
        f"Set RHINO_MCP_READ_ROOTS env var to allow additional directories."
    )


# ---------------------------------------------------------------------------
# R7-1: cairosvg URL fetcher that blocks external/local resource loading
# ---------------------------------------------------------------------------

def _svg_no_fetch(url: str, *args, **kwargs):
    """Block all external/local resource fetching during SVG rendering (R7-1)."""
    raise ValueError(f"External SVG resource fetching disabled: {url!r}")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    # ── PDF ─────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(title="Get PDF Info", readOnlyHint=True))
    def get_pdf_info(path: str, pages: str | None = None, max_pages: int = 50) -> dict[str, Any]:
        """Return PDF metadata and page sizes; paginate with pages (at most 50 per call)."""
        from rhmcp.tools_helpers.pdf_backend import request
        return request('info', path, pages=pages, max_pages=max_pages)

    @mcp.tool(annotations=ToolAnnotations(title="Read PDF", readOnlyHint=True))
    def read_pdf(path: str, pages: str | None = None, dpi: int = 150,
                 extract_text: bool = True, max_pages: int = 10,
                 scale_hint: str | None = None) -> dict[str, Any]:
        """Render PDF pages to PNG and text with bounded isolated processing.

        DPI must be 50–600; oversized pages require a lower DPI. Pass the same
        DPI to read_pdf_vectors when using the returned real_units_per_px.
        """
        import math
        from rhmcp.tools_helpers.pdf_backend import request, failure, number, PDFError
        info = None
        try:
            number(dpi, 'dpi', 50, 600, integer=True)
            if scale_hint:
                if not isinstance(scale_hint, str) or len(scale_hint) > 256:
                    raise ValueError('Scale hint too long.')
                paper, unit = _parse_scale_hint(scale_hint)
                if not math.isfinite(paper) or paper <= 0:
                    raise ValueError('Scale must be finite and positive.')
                pixels = paper * dpi
                info = {'scale_hint': scale_hint, 'real_unit': unit,
                        'px_per_real_unit': pixels, 'real_units_per_px': 1 / pixels,
                        'real_units_per_point': 1 / (paper * 72)}
        except (ValueError, TypeError, ZeroDivisionError, OverflowError, AttributeError) as exc:
            return failure(exc.code if isinstance(exc, PDFError) else 'INVALID_VALUE', 'Invalid DPI or drawing scale.')
        return request('read', path, pages=pages, dpi=dpi, extract_text=extract_text,
                       max_pages=max_pages, scale_info=info)

    @mcp.tool(annotations=ToolAnnotations(title="Calibrate PDF Scale", readOnlyHint=True))
    def calibrate_pdf_scale(
        pixel_point_1: list[float],
        pixel_point_2: list[float],
        real_distance: float,
        real_unit: str = "feet",
    ) -> dict[str, Any]:
        """Compute the exact pixel-to-real-world scale from two identified points
        in a rendered PDF page.

        After calling ``read_pdf``, visually identify two points whose
        real-world..."""
        import math
        from rhmcp.tools_helpers.pdf_backend import number, PDFError, failure
        try:
            for name, point in [('pixel_point_1', pixel_point_1), ('pixel_point_2', pixel_point_2)]:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise PDFError('INVALID_VALUE', f'{name} must contain exactly two coordinates.')
                for value in point:
                    number(value, name, -1e12, 1e12)
            number(real_distance, 'real_distance', 1e-12, 1e12)
            if real_unit not in {'feet', 'meters', 'inches', 'mm'}:
                raise PDFError('INVALID_VALUE', 'Unsupported real_unit.')
        except PDFError as exc:
            return failure(exc.code, str(exc))

        dx = float(pixel_point_2[0]) - float(pixel_point_1[0])
        dy = float(pixel_point_2[1]) - float(pixel_point_1[1])
        pixel_distance = math.sqrt(dx * dx + dy * dy)
        if pixel_distance < 1:
            return {"ok": False, "error": "The two points are too close together — pixel distance < 1"}

        px_per_unit = pixel_distance / real_distance
        return {
            "ok": True,
            "px_per_real_unit": round(px_per_unit, 4),
            "real_units_per_px": real_distance / pixel_distance,
            "real_unit": real_unit,
            "pixel_distance": round(pixel_distance, 2),
            "real_distance": real_distance,
            "note": (
                "Use real_units_per_px to convert any pixel coordinate from the "
                "rendered image to model-space distance. "
                "Pass px_per_real_unit as a reference when calling create_rhino_geometry."
            ),
        }

    @mcp.tool(annotations=ToolAnnotations(title="Read PDF Vectors", readOnlyHint=True))
    def read_pdf_vectors(path: str, pages: str | None = None,
                         real_units_per_px: float | None = None, real_unit: str = "feet",
                         min_length_px: float = 2.0, dpi: int = 150,
                         real_units_per_point: float | None = None,
                         max_pages: int = 10) -> dict[str, Any]:
        """Extract lines, rectangles, and cubic curves in rotated crop-relative PDF points.

        Use real_units_per_point, or supply real_units_per_px with the SAME dpi
        used to render/calibrate the page. min_length_px uses that DPI. Paths
        describe drawing commands; clipping/layer visibility is not verified.
        """
        from rhmcp.tools_helpers.pdf_backend import request
        return request('vectors', path, pages=pages, dpi=dpi, max_pages=max_pages,
                       real_units_per_px=real_units_per_px, real_units_per_point=real_units_per_point,
                       real_unit=real_unit, min_length_px=min_length_px)

    @mcp.tool(annotations=ToolAnnotations(title="Extract PDF Dimensions", readOnlyHint=True))
    def extract_pdf_dimensions(path: str, pages: str | None = None,
                               real_units_per_px: float | None = None,
                               real_unit: str = "feet", dpi: int = 150,
                               max_pages: int = 10) -> dict[str, Any]:
        """Find heuristic dimension annotations with rotated crop-relative pixel bounds.

        Use the same DPI as read_pdf. Only text with explicit units is matched;
        bare part numbers are not measurements. No OCR is performed.
        """
        from rhmcp.tools_helpers.pdf_backend import request
        return request('dimensions', path, pages=pages, dpi=dpi, max_pages=max_pages,
                       real_units_per_px=real_units_per_px, real_unit=real_unit)

    # ── IMAGE ────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(title="Read Image", readOnlyHint=True))
    def read_image(
        path: str,
        max_dimension: int = 2048,
        quality: int = 90,
    ) -> dict[str, Any]:
        """Read an image file and return it as a base64-encoded PNG.

        Supports JPG, PNG, TIFF, BMP, WEBP, GIF, HEIC/HEIF.  The image is
        resized (preserving aspect ratio) if either dimension..."""
        from rhmcp.tools_helpers.security import clamp
        if max_dimension is not None:
            max_dimension = clamp(max_dimension, 1, 8192)
        try:
            path = _validate_read_path(path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        try:
            from PIL import Image
        except ImportError:
            return {"ok": False, "error": "Pillow not installed — run: uv pip install Pillow"}

        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if p.suffix.lower() not in _IMAGE_EXTS:
            return {"ok": False, "error": f"Unsupported image type: {p.suffix}"}

        # Register HEIC support if available
        if p.suffix.lower() in {".heic", ".heif"}:
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ImportError:
                return {"ok": False, "error": "pillow-heif not installed — run: uv pip install pillow-heif"}

        try:
            img = Image.open(str(p))
            img.load()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        orig_w, orig_h = img.size
        img = img.convert("RGB")

        if max(orig_w, orig_h) > max_dimension:
            ratio = max_dimension / max(orig_w, orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        else:
            new_w, new_h = orig_w, orig_h

        return {
            "ok": True,
            "path": str(p),
            "format": p.suffix.lstrip(".").upper(),
            "original_width": orig_w,
            "original_height": orig_h,
            "returned_width": new_w,
            "returned_height": new_h,
            "image_data": _b64_png(img),
            "mime_type": "image/png",
        }

    # ── SPREADSHEET (CSV + Excel) ────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(title="Read Spreadsheet", readOnlyHint=True))
    def read_spreadsheet(
        path: str,
        sheet: str | int | None = None,
        max_rows: int = 500,
        header_row: bool = True,
    ) -> dict[str, Any]:
        """Read a CSV or Excel file and return rows as structured data.

        For Excel files, pass *sheet* as a sheet name or 1-based index.
        Omit *sheet* to read the first sheet.  Returns all sheet..."""
        from rhmcp.tools_helpers.security import clamp
        max_rows = clamp(max_rows, 1, 100_000)
        try:
            path = _validate_read_path(path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}

        ext = p.suffix.lower()

        # ── CSV ──
        if ext == ".csv":
            try:
                with p.open(newline="", encoding="utf-8-sig") as fh:
                    reader = _csv.reader(fh)
                    all_rows = list(reader)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            if not all_rows:
                return {"ok": True, "path": str(p), "format": "CSV",
                        "sheet_names": None, "headers": [], "rows": [], "row_count": 0}

            if header_row:
                headers = all_rows[0]
                data_rows = all_rows[1 : max_rows + 1]
                rows = [dict(zip(headers, r)) for r in data_rows]
            else:
                headers = []
                rows = all_rows[:max_rows]

            return {
                "ok": True, "path": str(p), "format": "CSV",
                "sheet_names": None,
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "truncated": len(all_rows) - (1 if header_row else 0) > max_rows,
            }

        # ── Excel ──
        if ext in {".xlsx", ".xls"}:
            try:
                import openpyxl
            except ImportError:
                return {"ok": False, "error": "openpyxl not installed — run: uv pip install openpyxl"}

            try:
                wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

            sheet_names = wb.sheetnames

            if sheet is None:
                ws = wb.active
            elif isinstance(sheet, int):
                # Documented as a 1-based index — reject 0 and out-of-range
                # values instead of silently wrapping around.
                if sheet < 1 or sheet > len(sheet_names):
                    wb.close()
                    return {
                        "ok": False,
                        "error": f"Sheet index {sheet} out of range — expected a 1-based index "
                                 f"between 1 and {len(sheet_names)}. Available sheets: {sheet_names}",
                    }
                ws = wb[sheet_names[sheet - 1]]
            else:
                if sheet not in sheet_names:
                    return {"ok": False, "error": f"Sheet {sheet!r} not found. Available: {sheet_names}"}
                ws = wb[sheet]

            all_rows = [[cell.value for cell in row] for row in ws.iter_rows()]
            wb.close()

            if not all_rows:
                return {"ok": True, "path": str(p), "format": "Excel",
                        "sheet_names": sheet_names, "sheet": ws.title,
                        "headers": [], "rows": [], "row_count": 0}

            if header_row:
                headers = [str(c) if c is not None else "" for c in all_rows[0]]
                data_rows = all_rows[1 : max_rows + 1]
                rows = [dict(zip(headers, [str(c) if c is not None else "" for c in r]))
                        for r in data_rows]
            else:
                headers = []
                rows = [[str(c) if c is not None else "" for c in r] for r in all_rows[:max_rows]]

            return {
                "ok": True, "path": str(p), "format": "Excel",
                "sheet_names": sheet_names,
                "sheet": ws.title,
                "headers": headers,
                "rows": rows,
                "row_count": len(rows),
                "truncated": len(all_rows) - (1 if header_row else 0) > max_rows,
            }

        return {"ok": False, "error": f"Unsupported spreadsheet format: {ext}"}

    # ── SVG ──────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(title="Read SVG", readOnlyHint=True))
    def read_svg(
        path: str,
        include_raw: bool = True,
        render_png: bool = True,
        render_dpi: int = 150,
    ) -> dict[str, Any]:
        """Read an SVG file and return its content and metadata.

        Returns the raw SVG text (valid XML the agent can parse) and a
        rendered PNG preview.  Extracts the declared width, height,..."""
        from rhmcp.tools_helpers.security import clamp
        render_dpi = clamp(render_dpi, 24, 600)
        try:
            path = _validate_read_path(path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if p.suffix.lower() not in _SVG_EXTS:
            return {"ok": False, "error": f"Not an SVG file: {path}"}

        try:
            raw_bytes = p.read_bytes()
            # .svgz is gzip-compressed SVG — decompress before decoding.
            if p.suffix.lower() == ".svgz" or raw_bytes[:2] == b"\x1f\x8b":
                import gzip
                raw_bytes = gzip.decompress(raw_bytes)
            svg_text = raw_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        # Parse metadata
        try:
            root = _ET.fromstring(svg_text)

            width  = root.get("width", "")
            height = root.get("height", "")
            viewbox = root.get("viewBox", "")
            child_count = len(list(root))
            # Count all descendant elements
            elem_count = sum(1 for _ in root.iter())
        except Exception:
            width = height = viewbox = ""
            child_count = elem_count = -1

        result: dict[str, Any] = {
            "ok": True,
            "path": str(p),
            "format": "SVG",
            "width": width,
            "height": height,
            "viewBox": viewbox,
            "top_level_elements": child_count,
            "total_elements": elem_count,
            "file_size_bytes": p.stat().st_size,
        }

        if include_raw:
            result["svg_text"] = svg_text

        # Optional raster render
        if render_png:
            try:
                import cairosvg  # type: ignore[import-untyped]
                import inspect as _inspect
                scale = render_dpi / 96.0
                _svg2png_kwargs: dict = {
                    "bytestring": svg_text.encode(),
                    "scale": scale,
                    "url_fetcher": _svg_no_fetch,
                }
                # Pass unsafe=False only if cairosvg supports it (older versions don't)
                if "unsafe" in _inspect.signature(cairosvg.svg2png).parameters:
                    _svg2png_kwargs["unsafe"] = False
                png_bytes = cairosvg.svg2png(**_svg2png_kwargs)
                result["image_data"] = base64.b64encode(png_bytes).decode()
                result["mime_type"] = "image/png"
                result["rendered_dpi"] = render_dpi
            except ImportError:
                result["render_note"] = (
                    "cairosvg not installed — PNG preview unavailable. "
                    "Run: uv pip install cairosvg"
                )
            except Exception as exc:
                result["render_note"] = f"PNG render failed: {exc}"

        return result

    # ── DOCX ─────────────────────────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(title="Read DOCX", readOnlyHint=True))
    def read_docx(
        path: str,
        include_tables: bool = True,
        max_paragraphs: int | None = None,
    ) -> dict[str, Any]:
        """Read a Word document (.docx) and return its text and tables.

        Returns paragraphs as a list of ``{text, style}`` objects and tables
        as row-major lists of string cells.  Use this to..."""
        from rhmcp.tools_helpers.security import clamp
        max_paragraphs = clamp(max_paragraphs or 50_000, 1, 50_000)
        try:
            path = _validate_read_path(path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        try:
            import docx as _docx
        except ImportError:
            return {"ok": False, "error": "python-docx not installed — run: uv pip install python-docx"}

        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if p.suffix.lower() not in _DOCX_EXTS:
            return {"ok": False, "error": f"Not a .docx file: {path}"}

        try:
            doc = _docx.Document(str(p))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        paras = [
            {"text": para.text, "style": para.style.name}
            for para in doc.paragraphs
            if para.text.strip()
        ]

        truncated_paras = len(paras) > max_paragraphs
        paras = paras[:max_paragraphs]

        full_text = "\n".join(p["text"] for p in paras)

        result: dict[str, Any] = {
            "ok": True,
            "path": str(p),
            "format": "DOCX",
            "paragraph_count": len(paras),
            "truncated_paragraphs": truncated_paras,
            "text": full_text,
            "paragraphs": paras,
        }

        if include_tables:
            tables = []
            for tbl in doc.tables:
                rows = [
                    [cell.text.strip() for cell in row.cells]
                    for row in tbl.rows
                ]
                tables.append({"rows": rows, "row_count": len(rows)})
            result["tables"] = tables
            result["table_count"] = len(tables)

        return result

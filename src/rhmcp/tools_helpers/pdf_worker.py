"""Single-request PDF parser process. Never imported to parse in the MCP process."""

from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
import re
import sys

from rhmcp.tools_helpers.pdf_backend import (
    MAX_ITEMS,
    MAX_OUTPUT,
    MAX_PIXELS,
    MAX_TEXT,
    MAX_TOTAL_PIXELS,
    PDFError,
    failure,
    select_pages,
)


def limits():
    # Windows has no resource module; parent still enforces timeout, concurrency,
    # pixels, input/output caps. OS memory/CPU ceilings apply on POSIX.
    if sys.platform != "win32":
        import resource

        ceilings = [(resource.RLIMIT_CPU, 25), (resource.RLIMIT_FSIZE, MAX_OUTPUT)]
        if sys.platform.startswith("linux"):
            ceilings.append((resource.RLIMIT_AS, 1536 * 1024 * 1024))
        for kind, value in ceilings:
            _, hard = resource.getrlimit(kind)
            if hard != resource.RLIM_INFINITY:
                value = min(value, hard)
            resource.setrlimit(kind, (value, value))


def budget_size(width, height, scale):
    if not all(math.isfinite(v) and v > 0 for v in (width, height, scale)):
        raise PDFError("INVALID_PDF", "Invalid page dimensions.")
    pixels = math.ceil(width * scale) * math.ceil(height * scale)
    if pixels > MAX_PIXELS:
        raise PDFError(
            "PDF_LIMIT_EXCEEDED",
            "Page exceeds 16 million rendered pixels; lower the DPI.",
        )
    return pixels


def text_limit(text):
    if len(text) > MAX_TEXT:
        raise PDFError("PDF_LIMIT_EXCEEDED", "Page exceeds the 200000 character limit.")
    return text


def geometry(page, args, origin):
    """Retain PDF path commands, including cubic curves and closing edges."""
    scale = args.get("dpi", 150) / 72
    ratio = args.get("real_units_per_point")
    if ratio is None and args.get("real_units_per_px") is not None:
        ratio = args["real_units_per_px"] * scale

    def point(p):
        return [p[0] - origin[0], p[1] - origin[1]]

    segments = []
    unsupported = 0
    filtered = 0
    paths = page.lines + page.rects + page.curves
    if len(paths) > MAX_ITEMS:
        raise PDFError("PDF_LIMIT_EXCEEDED", "Page exceeds the path limit.")
    for obj in paths:
        current = start = None
        for command in obj.get("path", []):
            op = command[0]
            if op == "m":
                current = start = point(command[1])
                continue
            if current is None:
                unsupported += 1
                continue
            controls = []
            if op == "l":
                end = point(command[1])
            elif op == "c":
                controls = [point(command[1]), point(command[2])]
                end = point(command[3])
            elif op == "h" and start is not None:
                end = start
            else:
                unsupported += 1
                continue
            length = math.dist(current, end)
            if not controls and length * scale < args.get("min_length_px", 2):
                filtered += 1
                current = end
                continue
            segment = {
                "type": "curve"
                if controls
                else ("rect" if obj["object_type"] == "rect" else "line"),
                "start": current,
                "end": end,
            }
            if controls:
                segment["control_points"] = controls
            if ratio is not None:
                segment.update(
                    start_real=[v * ratio for v in current],
                    end_real=[v * ratio for v in end],
                    real_unit=args.get("real_unit", "feet"),
                )
                if controls:
                    segment["control_points_real"] = [
                        [v * ratio for v in p] for p in controls
                    ]
                else:
                    segment["length_real"] = length * ratio
            segments.append(segment)
            if len(segments) > MAX_ITEMS:
                raise PDFError("PDF_LIMIT_EXCEEDED", "Page exceeds the segment limit.")
            current = end
    return {
        "segments": segments,
        "segment_count": len(segments),
        "has_vectors": bool(paths),
        "unsupported_commands": unsupported,
        "filtered_segments": filtered,
        "partial": bool(unsupported),
        "visibility_verified": False,
    }


def dimensions(page, args, origin):
    scale = args.get("dpi", 150) / 72
    # Match annotated units, not arbitrary bare drawing/part identifiers.
    pattern = re.compile(
        r"\d+(?:\.\d+)?\s*(?:mm|cm|m|ft|feet|in|inches)\b|\d+\s*['’]\s*(?:-?\s*\d+(?:/\d+)?\s*[\"”])?",
        re.I,
    )
    if len(page.chars) > MAX_TEXT:
        raise PDFError("PDF_LIMIT_EXCEEDED", "Page exceeds the character limit.")
    result = []
    for line in page.extract_text_lines(layout=False, return_chars=False):
        text = line["text"].strip()
        if not pattern.search(text):
            continue
        bbox = [
            (line["x0"] - origin[0]) * scale,
            (line["top"] - origin[1]) * scale,
            (line["x1"] - origin[0]) * scale,
            (line["bottom"] - origin[1]) * scale,
        ]
        center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
        item = {"text": text, "bbox_px": bbox, "center_px": center, "estimated": True}
        ratio = args.get("real_units_per_px")
        if ratio is not None:
            item.update(
                center_real=[v * ratio for v in center],
                real_unit=args.get("real_unit", "feet"),
            )
        result.append(item)
        if len(result) > MAX_ITEMS:
            raise PDFError("PDF_LIMIT_EXCEEDED", "Page exceeds the dimension limit.")
    return result


def process(args):
    import pypdfium2 as pdfium
    from contextlib import ExitStack, closing

    operation = args["operation"]
    with ExitStack() as stack:
        try:
            pdf = stack.enter_context(pdfium.PdfDocument(args["path"]))
        except pdfium.PdfiumError as exc:
            code = "PDF_PASSWORD_REQUIRED" if exc.err_code == 4 else "INVALID_PDF"
            raise PDFError(
                code,
                "PDF requires a password."
                if exc.err_code == 4
                else "PDF is corrupt or unsupported.",
            ) from exc
        count = len(pdf)
        indices, truncated = select_pages(
            args.get("pages"), count, args.get("max_pages", 10)
        )
        out = {
            "ok": True,
            "page_count": count,
            "pages_returned": len(indices),
            "truncated": truncated,
            "pages": [],
            "pdf_backend": "pdfium/pdfplumber",
        }
        dpi = args.get("dpi", 150)
        scale = dpi / 72
        plumber = None
        if operation in ("vectors", "dimensions"):
            import pdfplumber

            plumber = stack.enter_context(
                pdfplumber.open(args["path"], pages=[i + 1 for i in indices])
            )
        if operation == "info":
            meta = pdf.get_metadata_dict()
            for key in ("title", "author", "subject", "creator"):
                out[key] = text_limit(meta.get(key.title(), ""))
        else:
            out["dpi"] = dpi
        total_pixels = total_items = 0
        for n, idx in enumerate(indices):
            with closing(pdf[idx]) as page:
                width, height = page.get_size()
                if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                    raise PDFError("INVALID_PDF", "Invalid page size.")
                entry = {"page": idx + 1}
                if operation == "info":
                    entry.update(
                        width_pt=width,
                        height_pt=height,
                        width_in=width / 72,
                        height_in=height / 72,
                    )
                elif operation == "read":
                    total_pixels += budget_size(width, height, scale)
                    if total_pixels > MAX_TOTAL_PIXELS:
                        raise PDFError(
                            "PDF_LIMIT_EXCEEDED",
                            "Request exceeds 32 million rendered pixels.",
                        )
                    with closing(page.render(scale=scale)) as bitmap:
                        with bitmap.to_pil() as image:
                            buffer = io.BytesIO()
                            image.save(buffer, format="PNG")
                            encoded = base64.b64encode(buffer.getvalue()).decode(
                                "ascii"
                            )
                            if len(encoded) > MAX_OUTPUT:
                                raise PDFError(
                                    "PDF_LIMIT_EXCEEDED",
                                    "Rendered output exceeds 24 MiB.",
                                )
                            entry.update(
                                width_px=image.width,
                                height_px=image.height,
                                image_data=encoded,
                                mime_type="image/png",
                            )
                    if args.get("extract_text", True):
                        with closing(page.get_textpage()) as textpage:
                            if textpage.count_chars() > MAX_TEXT:
                                raise PDFError(
                                    "PDF_LIMIT_EXCEEDED",
                                    "Page exceeds the character limit.",
                                )
                            entry["text"] = text_limit(
                                textpage.get_text_range()
                            ).strip()
                    if args.get("scale_info"):
                        info = args["scale_info"]
                        ratio = info["real_units_per_px"]
                        entry.update(
                            real_width=entry["width_px"] * ratio,
                            real_height=entry["height_px"] * ratio,
                            **{
                                k: info[k]
                                for k in (
                                    "real_unit",
                                    "px_per_real_unit",
                                    "real_units_per_px",
                                )
                            },
                        )
                elif plumber is not None:
                    pp = plumber.pages[n]
                    # pdfplumber normalizes rotation. Crop origin is in that same
                    # top-left coordinate system; PDFium renders the crop box.
                    crop = pp.cropbox
                    origin = crop[:2]
                    if (
                        abs(crop[2] - crop[0] - width) > 0.1
                        or abs(crop[3] - crop[1] - height) > 0.1
                    ):
                        raise PDFError(
                            "PDF_UNSUPPORTED_GEOMETRY",
                            "Page crop/UserUnit geometry cannot be aligned reliably.",
                        )
                    if operation == "vectors":
                        entry.update(geometry(pp, args, origin))
                        total_items += entry["segment_count"]
                    else:
                        cropped = pp.crop(crop)
                        entry["dimensions"] = dimensions(cropped, args, origin)
                        total_items += len(entry["dimensions"])
                    pp.close()
                    if total_items > MAX_ITEMS:
                        raise PDFError(
                            "PDF_LIMIT_EXCEEDED", "Request exceeds 10000 output items."
                        )
                else:
                    raise PDFError("INVALID_VALUE", "Unknown PDF operation.")
                out["pages"].append(entry)
        if args.get("scale_info"):
            out["scale"] = args["scale_info"]
        if operation in ("vectors", "dimensions"):
            out.update(
                real_units_per_px=args.get("real_units_per_px"),
                real_unit=args.get("real_unit", "feet"),
            )
        if operation == "vectors":
            out.update(
                total_segments=total_items,
                coordinate_units="points",
                coordinate_origin="rotated_crop_top_left",
                real_units_per_point=args.get("real_units_per_point"),
                vector_pdf=any(p["has_vectors"] for p in out["pages"]),
                partial=any(p["partial"] for p in out["pages"]),
                visibility_verified=False,
            )
            if not out["vector_pdf"]:
                return dict(
                    failure(
                        "NO_VECTORS", "No drawing paths found; PDF may be raster-only."
                    ),
                    pages_checked=[i + 1 for i in indices],
                    truncated=truncated,
                )
        if operation == "dimensions":
            out.update(
                total_dimensions=total_items,
                estimated=True,
                coordinate_origin="rotated_crop_top_left",
            )
        return out


def main():
    args = json.loads(sys.stdin.read(8192))
    try:
        limits()
        result = process(args)
    except PDFError as exc:
        result = failure(exc.code, str(exc))
    except MemoryError:
        result = failure("PDF_LIMIT_EXCEEDED", "PDF exceeded worker memory limit.")
    except Exception:
        result = failure("PDF_PROCESSING_FAILED", "Unable to process PDF safely.")
    try:
        encoded = json.dumps(result, allow_nan=False)
        if len(encoded.encode()) > MAX_OUTPUT:
            encoded = json.dumps(
                failure("PDF_LIMIT_EXCEEDED", "PDF output exceeds 24 MiB.")
            )
    except (ValueError, MemoryError):
        encoded = json.dumps(failure("PDF_PROCESSING_FAILED", "Invalid PDF output."))
    Path(args["output"]).write_text(encoded)


if __name__ == "__main__":
    main()

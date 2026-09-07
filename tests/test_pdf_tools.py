"""PDF behavior regressions using tiny generated documents, without PyMuPDF."""

from pathlib import Path
import base64
import io
import math

import pytest
from PIL import Image
from rhmcp.tools import documents
from rhmcp.tools_helpers import pdf_backend as backend


def make_pdf(
    path,
    stream=b"0 124 m 72 124 l S BT /F1 11 Tf 10 84 Td (3000mm) Tj ET",
    width=144,
    height=144,
    rotation=0,
    crop=None,
    pages=1,
):
    """Minimal valid fixture writer; no PDF engine is required to create inputs."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for _ in range(pages):
        page_id = len(objects) + 1
        kids.append(f"{page_id} 0 R")
        crop_entry = f"/CropBox [{' '.join(map(str, crop))}]" if crop else ""
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                f"/Rotate {rotation} {crop_entry} /Resources << /Font << /F1 3 0 R >> >> "
                f"/Contents {page_id + 1} 0 R >>"
            ).encode()
        )
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>".encode()
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{n} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        content.extend(f"{offset:010} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(content)
    return str(path)


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setenv("RHINO_MCP_READ_ROOTS", str(tmp_path))

    class Registry:
        def __init__(self):
            self.tools = {}

        def tool(self, **kwargs):
            def register(fn):
                self.tools[fn.__name__] = fn
                return fn

            return register

    registry = Registry()
    documents.register(registry)
    return registry.tools


@pytest.mark.parametrize("dpi", [72, 150, 300])
def test_scale_render_vectors_and_points_agree(tools, tmp_path, dpi):
    path = make_pdf(tmp_path / "scale.pdf")
    image = tools["read_pdf"](path, dpi=dpi, scale_hint="1/4\" = 1'")
    assert image["ok"], image
    with Image.open(
        io.BytesIO(base64.b64decode(image["pages"][0]["image_data"]))
    ) as png:
        assert png.size == (dpi * 2, dpi * 2)
    result = tools["read_pdf_vectors"](
        path, dpi=dpi, real_units_per_px=image["scale"]["real_units_per_px"]
    )
    assert result["ok"], result
    assert result["coordinate_units"] == "points"
    assert result["pages"][0]["segments"][0]["length_real"] == pytest.approx(4)
    result = tools["read_pdf_vectors"](
        path, real_units_per_point=image["scale"]["real_units_per_point"]
    )
    assert result["pages"][0]["segments"][0]["length_real"] == pytest.approx(4)


def test_cubic_curve_and_closed_rectangle(tools, tmp_path):
    path = make_pdf(
        tmp_path / "curves.pdf",
        stream=b"10 130 m 20 90 60 90 72 130 c S 20 20 40 30 re S",
    )
    result = tools["read_pdf_vectors"](path)
    assert result["ok"], result
    items = result["pages"][0]["segments"]
    assert sum(i["type"] == "rect" for i in items) == 4
    curve = next(i for i in items if i["type"] == "curve")
    assert len(curve["control_points"]) == 2
    assert not result["partial"]


def test_rotated_dimension_bounds_align_with_image(tools, tmp_path):
    path = make_pdf(tmp_path / "rotated.pdf", height=288, rotation=90)
    dims = tools["extract_pdf_dimensions"](path, dpi=72)
    assert dims["ok"], dims
    bbox = dims["pages"][0]["dimensions"][0]["bbox_px"]
    # Text was placed at x=10,y=84; after clockwise rotation its x is near 84.
    assert 75 < bbox[0] < 95
    assert bbox[1] == pytest.approx(10)
    rendered = tools["read_pdf"](path, dpi=72)
    assert rendered["pages"][0]["width_px"] == 288
    assert rendered["pages"][0]["height_px"] == 144


def test_crop_origin_and_pixel_bounds(tools, tmp_path):
    path = make_pdf(tmp_path / "crop.pdf", crop=[0, 40, 100, 140])
    result = tools["read_pdf_vectors"](path, dpi=72)
    assert result["ok"], result
    assert result["pages"][0]["segments"][0]["start"] == pytest.approx([0, 16])
    image = tools["read_pdf"](path, dpi=72)
    assert image["pages"][0]["width_px"] == 100
    assert image["pages"][0]["height_px"] == 100


@pytest.mark.parametrize(
    "name", ["get_pdf_info", "read_pdf", "read_pdf_vectors", "extract_pdf_dimensions"]
)
def test_password_error_is_structured(tools, tmp_path, name):
    path = tmp_path / "encrypted.pdf"
    path.write_bytes(
        (Path(__file__).parent / "fixtures/pdf/encrypted.pdf").read_bytes()
    )
    result = tools[name](str(path))
    assert result["error_code"] == "PDF_PASSWORD_REQUIRED", result


@pytest.mark.parametrize("pages", ["999", "0", "2-1", "1-999", "abc", "1,,1"])
def test_bad_page_ranges_fail(tools, tmp_path, pages):
    result = tools["read_pdf"](make_pdf(tmp_path / "a.pdf"), pages=pages)
    assert result["error_code"] == "INVALID_PAGE_RANGE", result


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dpi": -150},
        {"dpi": 0},
        {"dpi": 601},
        {"real_units_per_px": -1},
        {"real_units_per_px": math.inf},
        {"real_units_per_px": math.nan},
    ],
)
def test_invalid_dimension_parameters(tools, tmp_path, kwargs):
    result = tools["extract_pdf_dimensions"](make_pdf(tmp_path / "a.pdf"), **kwargs)
    assert result["error_code"] == "INVALID_VALUE"


def test_non_pdf_and_corrupt_pdf_rejected(tools, tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not a PDF")
    assert tools["get_pdf_info"](str(path))["error_code"] == "INVALID_PDF"
    path.write_bytes(b"%PDF-1.7\ncorrupt")
    assert not tools["get_pdf_info"](str(path))["ok"]


def test_oversized_page_rejected_before_render(tools, tmp_path):
    result = tools["read_pdf"](
        make_pdf(tmp_path / "large.pdf", width=2592, height=3456), dpi=600
    )
    assert result["error_code"] == "PDF_LIMIT_EXCEEDED", result


def test_info_pagination_and_vector_truncation(tools, tmp_path):
    path = make_pdf(tmp_path / "many.pdf", pages=3)
    for name in ["get_pdf_info", "read_pdf_vectors", "extract_pdf_dimensions"]:
        result = tools[name](path, max_pages=1)
        assert (
            result["page_count"] == 3
            and result["pages_returned"] == 1
            and result["truncated"]
        )
    assert tools["get_pdf_info"](path, pages="3")["pages"][0]["page"] == 3


def test_bare_part_number_is_not_dimension(tools, tmp_path):
    result = tools["extract_pdf_dimensions"](
        make_pdf(tmp_path / "id.pdf", stream=b"BT /F1 11 Tf 10 84 Td (12345) Tj ET")
    )
    assert result["ok"] and result["total_dimensions"] == 0


def test_timeout_kills_worker_and_next_request_succeeds(tools, tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "a.pdf")
    monkeypatch.setattr(backend, "TIMEOUT", 0)
    assert tools["get_pdf_info"](path)["error_code"] == "PDF_TIMEOUT"
    monkeypatch.setattr(backend, "TIMEOUT", 30)
    assert tools["get_pdf_info"](path)["ok"]


def test_busy_and_input_limit(tools, tmp_path, monkeypatch):
    path = make_pdf(tmp_path / "a.pdf")
    backend._WORKERS.acquire()
    backend._WORKERS.acquire()
    try:
        assert tools["get_pdf_info"](path)["error_code"] == "PDF_BUSY"
    finally:
        backend._WORKERS.release()
        backend._WORKERS.release()
    monkeypatch.setattr(backend, "MAX_INPUT", 10)
    assert tools["get_pdf_info"](path)["error_code"] == "PDF_LIMIT_EXCEEDED"


def test_invalid_scale_hint(tools, tmp_path):
    path = make_pdf(tmp_path / "a.pdf")
    for hint in ["0:100", "1:0", "1/0\" = 1'"]:
        assert tools["read_pdf"](path, scale_hint=hint)["error_code"] == "INVALID_VALUE"


def test_memory_limit_kills_worker(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "MEMORY_LIMIT", 1)
    result = tools["get_pdf_info"](make_pdf(tmp_path / "a.pdf"))
    assert result["error_code"] == "PDF_LIMIT_EXCEEDED", result


def test_parallel_requests_use_separate_workers(tools, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = make_pdf(tmp_path / "a.pdf")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: tools["read_pdf_vectors"](path), range(2)))
    assert all(r["ok"] for r in results), results


def test_raster_only_response_and_minimum_length_units(tools, tmp_path):
    empty = make_pdf(tmp_path / "empty.pdf", stream=b"")
    assert tools["read_pdf_vectors"](empty)["error_code"] == "NO_VECTORS"
    path = make_pdf(tmp_path / "line.pdf")
    # 72 points = 150 pixels at 150 DPI, so a 100 pixel cutoff retains it.
    result = tools["read_pdf_vectors"](path, dpi=150, min_length_px=100)
    assert result["total_segments"] == 1
    result = tools["read_pdf_vectors"](path, dpi=72, min_length_px=100)
    assert result["ok"] and result["vector_pdf"] and result["total_segments"] == 0
    assert result["pages"][0]["filtered_segments"] == 1


def test_mcp_cancellation_terminates_pdf_child(tools, tmp_path, monkeypatch):
    import asyncio
    import subprocess
    import sys
    from rhmcp.tools_helpers.tool_runtime import RuntimeMCP

    real_popen = subprocess.Popen
    children = []

    def sleeping_child(*args, **kwargs):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(backend.subprocess, 'Popen', sleeping_child)
    path = make_pdf(tmp_path / 'cancel.pdf')
    mcp = RuntimeMCP('pdf-cancel-test')
    documents.register(mcp)

    async def check():
        tool = mcp._tool_manager.get_tool('get_pdf_info')
        task = asyncio.create_task(tool.run({'path': path}))
        for _ in range(100):
            if children:
                break
            await asyncio.sleep(.01)
        assert children
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(100):
            if children[0].poll() is not None:
                break
            await asyncio.sleep(.01)
        assert children[0].poll() is not None
    asyncio.run(check())


def test_worker_crash_is_structured(tools, tmp_path, monkeypatch):
    import subprocess
    import sys
    real_popen = subprocess.Popen
    monkeypatch.setattr(backend.subprocess, 'Popen', lambda *args, **kwargs:
                        real_popen([sys.executable, '-c', 'import os; os._exit(2)'], **kwargs))
    result = tools['get_pdf_info'](make_pdf(tmp_path / 'crash.pdf'))
    assert result['error_code'] == 'PDF_WORKER_FAILED'


def test_response_limit(tools, tmp_path, monkeypatch):
    monkeypatch.setattr(backend, 'MAX_OUTPUT', 1)
    result = tools['get_pdf_info'](make_pdf(tmp_path / 'output.pdf'))
    assert result['error_code'] == 'PDF_LIMIT_EXCEEDED'


def test_calibration_rejects_nonfinite_values(tools):
    result = tools['calibrate_pdf_scale']([0, 0], [math.nan, 1], 4)
    assert result['error_code'] == 'INVALID_VALUE'

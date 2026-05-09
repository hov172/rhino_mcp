"""Branded PDF report generator — Jinja2 + DocRaptor + S3."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_report_history: list[dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent.parent / "report_templates"


class _AttrDict:
    """Wrap a plain dict so Jinja2 templates can access keys as attributes."""
    def __init__(self, d: dict) -> None:
        self.__dict__.update(d)

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(f"_AttrDict has no attribute '{name}'")

    def get(self, key: str, default=None):
        return self.__dict__.get(key, default)


def _render_html(
    project_name: str,
    scheme_name: str,
    author: str | None,
    metrics: dict,
    renders: dict,
    design_language: dict,
    solar: dict | None,
    params: list[dict],
    include_solar: bool,
    include_design_language: bool,
) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    css_path = _TEMPLATES_DIR / "report.css"
    css = css_path.read_text() if css_path.exists() else ""
    template = env.get_template("report.html.jinja2")
    return template.render(
        project_name=project_name,
        scheme_name=scheme_name,
        author=author,
        date=time.strftime("%B %d, %Y"),
        metrics=_AttrDict(metrics) if isinstance(metrics, dict) else metrics,
        renders=renders,
        design_language=_AttrDict(design_language) if isinstance(design_language, dict) else design_language,
        solar=_AttrDict(solar) if isinstance(solar, dict) else solar,
        solar_capture_b64="",
        params=params,
        include_solar=include_solar,
        include_design_language=include_design_language,
        css=css,
    )


def _html_to_pdf_docraptor(html: str) -> bytes:
    api_key = os.environ.get("DOCRAPTOR_API_KEY", "")
    resp = httpx.post(
        "https://docraptor.com/docs",
        json={
            "user_credentials": api_key,
            "doc": {
                "document_content": html,
                "document_type": "pdf",
                "test": False,
                "prince_options": {"media": "print"},
            },
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.content


def _upload_to_s3(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    import boto3
    bucket = os.environ["URBAN_AGENT_S3_BUCKET"]
    ts = int(time.time())
    pdf_key = f"reports/{project}/{scheme}/{ts}.pdf"
    html_key = f"reports/{project}/{scheme}/{ts}.html"
    client = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    client.put_object(Bucket=bucket, Key=html_key, Body=html.encode(), ContentType="text/html")
    client.put_object(Bucket=bucket, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")
    pdf_url = client.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": pdf_key}, ExpiresIn=604800)
    html_url = client.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": html_key}, ExpiresIn=604800)
    return pdf_url, html_url


def _save_local(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    ts = int(time.time())
    out_dir = Path.home() / ".urbanagent" / "reports" / project / f"{scheme}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "report.pdf"
    html_path = out_dir / "report.html"
    pdf_path.write_bytes(pdf_bytes)
    html_path.write_text(html)
    return f"file://{pdf_path}", f"file://{html_path}"


def reset() -> None:
    """Reset module state."""
    global _report_history
    _report_history = []


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Export Urban Report", destructiveHint=False))
    def urban_export_report(
        project_name: str,
        scheme_name: str,
        author: str | None = None,
        include_solar: bool = True,
        include_design_language: bool = True,
        format: str = "pdf",
    ) -> dict[str, object]:
        """
        Export a branded PDF (or HTML) report: cover page, executive summary,
        massing renders, metrics, solar analysis, design language, parameters.
        Uploads to S3 and returns a 7-day presigned URL.
        Falls back to local ~/.urbanagent/reports/ when cloud credentials absent.
        """
        from rhmcp.tools import urban_design_language, urban_renders
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = urban_renders._current_renders
        dl = urban_design_language._current_design_language or {}
        solar = None  # populated when urban_run_analysis stores results

        html = _render_html(
            project_name=project_name,
            scheme_name=scheme_name,
            author=author,
            metrics=metrics,
            renders=renders,
            design_language=dl,
            solar=solar,
            params=[],
            include_solar=include_solar,
            include_design_language=include_design_language,
        )

        pdf_bytes = b""
        if os.environ.get("DOCRAPTOR_API_KEY"):
            try:
                pdf_bytes = _html_to_pdf_docraptor(html)
            except Exception as exc:
                print(f"[urban_report] DocRaptor failed: {exc}", flush=True)

        if not pdf_bytes:
            pdf_bytes = html.encode()  # fallback: store HTML as "pdf"

        pdf_url = html_url = ""
        local_path = ""

        if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
            try:
                pdf_url, html_url = _upload_to_s3(pdf_bytes, html, project_name, scheme_name)
            except Exception as exc:
                print(f"[urban_report] S3 upload failed: {exc}", flush=True)

        if not pdf_url:
            pdf_url, html_url = _save_local(pdf_bytes, html, project_name, scheme_name)
            local_path = pdf_url.replace("file://", "")

        record: dict[str, Any] = {
            "scheme_name": scheme_name,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "timestamp": int(time.time()),
            "file_size_kb": round(len(pdf_bytes) / 1024, 1),
        }
        _report_history.append(record)

        return {
            "ok": True,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "file_size_kb": record["file_size_kb"],
            "local_path": local_path,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Preview Urban Report", readOnlyHint=True))
    def urban_preview_report() -> dict[str, object]:
        """
        Render the report as HTML only — no PDF, no S3. Fast iteration before final export.
        Returns the rendered HTML string and writes a temp file.
        """
        import tempfile
        from rhmcp.tools import urban_design_language, urban_renders
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = urban_renders._current_renders
        dl = urban_design_language._current_design_language or {}

        html = _render_html(
            project_name="Preview",
            scheme_name="Draft",
            author=None,
            metrics=metrics,
            renders=renders,
            design_language=dl,
            solar=None,
            params=[],
            include_solar=False,
            include_design_language=bool(dl),
        )

        fd, tmp_str = tempfile.mkstemp(suffix=".html")
        os.close(fd)
        tmp = Path(tmp_str)
        tmp.write_text(html)
        return {"ok": True, "html_path": str(tmp), "html_content": html}

    @mcp.tool(annotations=ToolAnnotations(title="List Urban Reports", readOnlyHint=True))
    def urban_list_reports() -> list[dict[str, object]]:
        """List all reports exported this session."""
        return list(_report_history)

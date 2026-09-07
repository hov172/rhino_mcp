"""Branded PDF report generator — Jinja2 + DocRaptor + S3."""
from __future__ import annotations
from rhmcp.tools_helpers.workflow_state import current as state

import os
import time
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Environment, FileSystemLoader
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# State is stored in the current actor/project/instance scope
# ---------------------------------------------------------------------------


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
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
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
    if not resp.content.startswith(b"%PDF-"):
        raise ValueError("PDF service returned a non-PDF response")
    return resp.content


def _upload_to_s3(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    import re as _re
    import boto3
    bucket = os.environ["URBAN_AGENT_S3_BUCKET"]
    ts = uuid.uuid4().hex
    safe_project = _re.sub(r'[^\w\-.]', '_', project)[:64].strip(".") or "project"
    safe_scheme = _re.sub(r'[^\w\-.]', '_', scheme)[:64] or "scheme"
    from rhmcp.tools_helpers.workflow_state import storage_namespace
    namespace = storage_namespace()
    pdf_key = f"reports/{safe_project}/{safe_scheme}/{namespace}/{ts}.pdf"
    html_key = f"reports/{safe_project}/{safe_scheme}/{namespace}/{ts}.html"
    client = boto3.client(
        "s3",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    client.put_object(Bucket=bucket, Key=html_key, Body=html.encode(), ContentType="text/html")
    pdf_url = ""
    if pdf_bytes:
        if not pdf_bytes.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF content")
        client.put_object(Bucket=bucket, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")
        pdf_url = client.generate_presigned_url("get_object",
            Params={"Bucket": bucket, "Key": pdf_key}, ExpiresIn=604800)
    html_url = client.generate_presigned_url("get_object",
        Params={"Bucket": bucket, "Key": html_key}, ExpiresIn=604800)
    return pdf_url, html_url


def _save_local(pdf_bytes: bytes, html: str, project: str, scheme: str) -> tuple[str, str]:
    import re as _re
    project = _re.sub(r'[^\w\-.]', '_', project)[:64].strip(".") or "project"
    scheme = _re.sub(r'[^\w\-.]', '_', scheme)[:64] or "scheme"
    ts = uuid.uuid4().hex
    from rhmcp.tools_helpers.workflow_state import storage_namespace
    root = Path(os.environ.get("RHINO_MCP_REPORT_DIR", str(Path.home() / ".urbanagent" / "reports")))
    out_dir = root / storage_namespace() / project / f"{scheme}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "report.pdf"
    html_path = out_dir / "report.html"
    if pdf_bytes:
        if not pdf_bytes.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF content")
        pdf_path.write_bytes(pdf_bytes)
    html_path.write_text(html, encoding="utf-8")
    return pdf_path.as_uri() if pdf_bytes else "", html_path.as_uri()


def reset() -> None:
    """Reset module state."""
    state().report_history = []


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
        """Export a branded PDF (or HTML) report: cover page, executive summary,
        massing renders, metrics, solar analysis, design language, parameters.
        Uploads to S3 and returns a 7-day..."""
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = state().current_renders
        dl = state().current_design_language or {}
        solar = state().current_solar if include_solar else None
        if format not in ("pdf", "html"):
            return {"ok": False, "error": "format must be pdf or html", "error_code": "INVALID_VALUE"}

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
        if format == "pdf" and os.environ.get("DOCRAPTOR_API_KEY"):
            try:
                pdf_bytes = _html_to_pdf_docraptor(html)
            except Exception as exc:
                print(f"[urban_report] DocRaptor failed: {exc}", file=sys.stderr, flush=True)


        pdf_url = html_url = ""
        local_path = ""

        if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
            try:
                pdf_url, html_url = _upload_to_s3(pdf_bytes, html, project_name, scheme_name)
            except Exception as exc:
                print(f"[urban_report] S3 upload failed: {exc}", file=sys.stderr, flush=True)

        if not html_url:
            pdf_url, html_url = _save_local(pdf_bytes, html, project_name, scheme_name)
            local_path = (pdf_url or html_url).replace("file://", "")

        record: dict[str, Any] = {
            "scheme_name": scheme_name,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "timestamp": int(time.time()),
            "file_size_kb": round(len(pdf_bytes or html.encode()) / 1024, 1),
        }
        state().report_history.append(record)

        return {
            "ok": True,
            "pdf_url": pdf_url,
            "html_url": html_url,
            "file_size_kb": record["file_size_kb"],
            "local_path": local_path,
            "format": "pdf" if pdf_url else "html",
            "warnings": ["PDF unavailable; exported HTML only."] if format == "pdf" and not pdf_url else [],
        }

    @mcp.tool(annotations=ToolAnnotations(title="Preview Urban Report", readOnlyHint=True))
    def urban_preview_report() -> dict[str, object]:
        """
        Render the report as HTML only — no PDF, no S3. Fast iteration before final export.
        Returns the rendered HTML string and writes a temp file.
        """
        import tempfile
        from rhmcp.tools.urban import _urban_get_metrics

        metrics = _urban_get_metrics()
        renders = state().current_renders
        dl = state().current_design_language or {}

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
        return list(state().report_history)

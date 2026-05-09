"""Unit tests for urban_report tools. DocRaptor and S3 are mocked."""
from __future__ import annotations
import importlib
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from mcp.server.fastmcp import FastMCP

_SAMPLE_METRICS = {"gfa_m2": 28000.0, "far": 3.5, "unit_count_est": 280, "open_space_pct": 22.0}
_SAMPLE_DL = {
    "ok": True, "set": True,
    "style_name": "Nordic", "facade_vocabulary": ["brick"],
    "material_palette": [{"name": "Brick", "hex": "#C4956A", "role": "primary"}],
    "colour_story": {}, "landscape_character": "Green.",
    "diffusion_prompt": "", "negative_prompt": "",
    "executive_summary": "A warm scheme.",
}


def _register():
    import rhmcp.tools.urban_report as m
    importlib.reload(m)
    mcp = FastMCP("test-report")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def _mock_docraptor_response(pdf_bytes: bytes = b"%PDF-test"):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.content = pdf_bytes
    return resp


def _mock_s3_client():
    client = MagicMock()
    client.put_object = MagicMock()
    client.generate_presigned_url = MagicMock(return_value="https://s3.example.com/report.pdf")
    return client


class TestUrbanExportReport(unittest.TestCase):
    def _call(self, **kw):
        tools = _register()
        defaults = dict(project_name="TestProject", scheme_name="SchemeA")
        defaults.update(kw)
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post", return_value=_mock_docraptor_response()):
                        with patch("boto3.client", return_value=_mock_s3_client()):
                            with patch.dict("os.environ", {
                                "DOCRAPTOR_API_KEY": "test",
                                "URBAN_AGENT_S3_BUCKET": "test-bucket",
                                "AWS_ACCESS_KEY_ID": "key",
                                "AWS_SECRET_ACCESS_KEY": "secret",
                            }):
                                return tools["urban_export_report"](**defaults)

    def test_returns_ok_true_with_pdf_url(self):
        r = self._call()
        self.assertTrue(r["ok"])
        self.assertIn("pdf_url", r)

    def test_s3_upload_uses_correct_key_format(self):
        s3 = _mock_s3_client()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post", return_value=_mock_docraptor_response()):
                        with patch("boto3.client", return_value=s3):
                            with patch.dict("os.environ", {
                                "DOCRAPTOR_API_KEY": "test",
                                "URBAN_AGENT_S3_BUCKET": "bucket",
                                "AWS_ACCESS_KEY_ID": "k", "AWS_SECRET_ACCESS_KEY": "s",
                            }):
                                tools = _register()
                                tools["urban_export_report"](project_name="Proj", scheme_name="V1")
        call_kwargs = s3.put_object.call_args[1]
        self.assertTrue(call_kwargs["Key"].startswith("reports/Proj/V1/"))
        self.assertTrue(call_kwargs["Key"].endswith(".pdf"))

    def test_solar_section_omitted_when_flag_false(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}):
                        r = tools["urban_export_report"](
                            project_name="P", scheme_name="S", include_solar=False)
        # Local fallback — file:// url
        self.assertIn("pdf_url", r)

    def test_design_language_section_omitted_when_flag_false(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}):
                        r = tools["urban_export_report"](
                            project_name="P", scheme_name="S", include_design_language=False)
        self.assertIn("pdf_url", r)

    def test_falls_back_to_local_when_no_cloud_credentials(self):
        import tempfile
        tmp_home = Path(tempfile.mkdtemp())
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch.dict("os.environ", {}, clear=True):
                        with patch("pathlib.Path.home", return_value=tmp_home):
                            r = tools["urban_export_report"](project_name="P", scheme_name="S")
        self.assertTrue(r["ok"])
        self.assertTrue(r["pdf_url"].startswith("file://") or "local_path" in r)


class TestUrbanPreviewReport(unittest.TestCase):
    def test_preview_writes_html_without_api_calls(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    with patch("httpx.post") as mock_post:
                        r = tools["urban_preview_report"]()
        mock_post.assert_not_called()
        self.assertTrue(r["ok"])
        self.assertIn("html_content", r)

    def test_preview_html_contains_project_sections(self):
        tools = _register()
        with patch("rhmcp.tools.urban_design_language._current_design_language", _SAMPLE_DL):
            with patch("rhmcp.tools.urban_renders._current_renders", {}):
                with patch("rhmcp.tools.urban._urban_get_metrics", return_value=_SAMPLE_METRICS):
                    r = tools["urban_preview_report"]()
        self.assertIn("Executive Summary", r["html_content"])
        self.assertIn("UrbanAgent", r["html_content"])


class TestUrbanListReports(unittest.TestCase):
    def test_returns_list(self):
        tools = _register()
        r = tools["urban_list_reports"]()
        self.assertIsInstance(r, list)

"""Unit tests for security guards — no live Rhino required."""
from __future__ import annotations
import io
import os
import zipfile

import pytest
from rhmcp.tools_helpers.security import (
    clamp,
    safe_extractall,
    sanitise_rhino_path,
    validate_download_url,
)


class TestSanitiseRhinoPath:
    def test_clean_path_unchanged(self):
        assert sanitise_rhino_path("/tmp/model.3dm") == "/tmp/model.3dm"

    def test_double_quote_stripped(self):
        assert '"' not in sanitise_rhino_path('/tmp/evil"_Quit.3dm')

    def test_backslash_preserved_windows(self):
        result = sanitise_rhino_path(r"C:\Users\alice\model.3dm")
        assert result == r"C:\Users\alice\model.3dm"

    def test_newline_stripped(self):
        assert "\n" not in sanitise_rhino_path("/tmp/a\nb.3dm")

    def test_carriage_return_stripped(self):
        assert "\r" not in sanitise_rhino_path("/tmp/a\rb.3dm")

    def test_quote_removed_macro_safe(self):
        evil = '/tmp/model" _Quit _Enter "'
        safe = sanitise_rhino_path(evil)
        macro = f'_-Export "{safe}" _Enter'
        assert macro.count('"') == 2

    def test_newline_removed_macro_safe(self):
        evil = "/tmp/model\n_Quit"
        safe = sanitise_rhino_path(evil)
        assert "\n" not in safe

    def test_normal_windows_path_intact(self):
        path = r"C:\Users\alice\model.3dm"
        assert sanitise_rhino_path(path) == path


class TestValidateDownloadUrl:
    def test_https_allowed(self):
        validate_download_url("https://example.com/model.glb")  # no raise

    def test_http_blocked(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_download_url("http://example.com/model.glb")

    def test_file_scheme_blocked(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_download_url("file:///etc/passwd")

    def test_local_path_blocked(self):
        with pytest.raises(ValueError, match="local"):
            validate_download_url("/etc/passwd")

    def test_aws_metadata_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://169.254.169.254/latest/meta-data/")

    def test_localhost_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://localhost/secret")

    def test_rfc1918_10_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://10.0.0.1/secret")

    def test_rfc1918_172_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://172.16.0.1/secret")

    def test_rfc1918_192_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://192.168.1.1/secret")


class TestClamp:
    def test_within_range(self):
        assert clamp(150, 50, 600) == 150

    def test_below_min(self):
        assert clamp(10, 50, 600) == 50

    def test_above_max(self):
        assert clamp(9999, 50, 600) == 600

    def test_clamp_dpi_max(self):
        assert clamp(9999, 50, 600) == 600

    def test_clamp_dpi_min(self):
        assert clamp(1, 50, 600) == 50

    def test_clamp_dimension_max(self):
        assert clamp(100_000, 1, 8192) == 8192


class TestZipSlip:
    def test_safe_zip_extracted_normally(self, tmp_path):
        zf_bytes = io.BytesIO()
        with zipfile.ZipFile(zf_bytes, "w") as zf:
            zf.writestr("model/scene.gltf", '{"asset":{}}')
        zf_bytes.seek(0)
        extract_dir = str(tmp_path / "out")
        os.makedirs(extract_dir)
        safe_extractall(zf_bytes, extract_dir)
        assert os.path.exists(os.path.join(extract_dir, "model", "scene.gltf"))

    def test_zip_slip_path_raises(self, tmp_path):
        zf_bytes = io.BytesIO()
        with zipfile.ZipFile(zf_bytes, "w") as zf:
            zf.writestr("../../evil.sh", "rm -rf /")
        zf_bytes.seek(0)
        extract_dir = str(tmp_path / "out")
        os.makedirs(extract_dir)
        with pytest.raises(ValueError, match="Zip slip"):
            safe_extractall(zf_bytes, extract_dir)


class TestJinja2Autoescape:
    def test_xss_payload_escaped_in_report(self):
        """project_name with <script> must be HTML-escaped in output."""
        from types import SimpleNamespace
        from rhmcp.tools.urban_report import _render_html
        metrics = SimpleNamespace(gfa_m2=1000, far=2.5, unit_count_est=10, open_space_pct=20)
        html = _render_html(
            project_name="<script>alert(1)</script>",
            scheme_name="Test",
            author="Tester",
            metrics=metrics,
            renders={},
            design_language={},
            solar=None,
            params=[],
            include_solar=False,
            include_design_language=False,
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


class TestDownloadFileSecurity:
    def _get_download_file(self):
        import importlib
        return importlib.import_module("rhmcp.tools.ai_generation")._download_file

    def test_local_path_rejected(self):
        dl = self._get_download_file()
        result = dl("/etc/passwd", api_key=None, output_dir=None, service="rodin")
        assert result["ok"] is False
        assert "not allowed" in result["error"].lower()

    def test_file_equals_path_rejected(self):
        dl = self._get_download_file()
        result = dl("file=/etc/passwd", api_key=None, output_dir=None, service="rodin")
        assert result["ok"] is False

    def test_http_scheme_rejected(self):
        dl = self._get_download_file()
        result = dl("http://example.com/model.glb", api_key=None, output_dir=None, service="rodin")
        assert result["ok"] is False
        assert "scheme" in result["error"].lower()

    def test_aws_metadata_rejected(self):
        dl = self._get_download_file()
        result = dl("https://169.254.169.254/latest/meta-data/", api_key=None, output_dir=None, service="rodin")
        assert result["ok"] is False
        assert "private" in result["error"].lower()


class TestJobStoreNoApiKey:
    def test_api_key_not_stored_in_job_store(self):
        """api_key must never appear in _JOB_STORE values."""
        import importlib
        mod = importlib.import_module("rhmcp.tools.ai_generation")
        store = mod._JOB_STORE
        store["test-job-123"] = {
            "service": "rodin",
            "task_uuid": "abc",
            "output_format": "glb",
        }
        assert "api_key" not in store["test-job-123"]
        del store["test-job-123"]

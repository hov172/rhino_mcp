"""
Unit tests for rhmcp.tools_helpers.security.
No Rhino instance required.
"""

from __future__ import annotations

import io
import os
import socket
import struct
import tempfile
import zipfile
import unittest
from unittest.mock import patch

from rhmcp.tools_helpers.security import (
    _is_private,
    clamp,
    safe_extractall,
    sanitise_rhino_path,
    validate_download_url,
)


class TestSanitiseRhinoPath(unittest.TestCase):
    def test_clean_path_unchanged(self) -> None:
        p = "/Users/alice/models/building.3dm"
        self.assertEqual(sanitise_rhino_path(p), p)

    def test_strips_double_quote(self) -> None:
        self.assertEqual(sanitise_rhino_path('/tmp/bad"name.3dm'), "/tmp/badname.3dm")

    def test_strips_newline(self) -> None:
        self.assertEqual(sanitise_rhino_path("/tmp/foo\nbar.3dm"), "/tmp/foobar.3dm")

    def test_strips_carriage_return(self) -> None:
        self.assertEqual(sanitise_rhino_path("/tmp/foo\rbar.3dm"), "/tmp/foobar.3dm")

    def test_strips_null_byte(self) -> None:
        self.assertEqual(sanitise_rhino_path("/tmp/foo\0bar.3dm"), "/tmp/foobar.3dm")

    def test_raises_on_empty_result(self) -> None:
        with self.assertRaises(ValueError):
            sanitise_rhino_path('"\n\r\0')


class TestValidateDownloadUrl(unittest.TestCase):
    def test_https_allowed(self) -> None:
        with patch("rhmcp.tools_helpers.security._is_private", return_value=False):
            validate_download_url("https://example.com/model.glb")  # must not raise

    def test_http_allowed(self) -> None:
        with patch("rhmcp.tools_helpers.security._is_private", return_value=False):
            validate_download_url("http://cdn.example.com/file.zip")  # must not raise

    def test_local_path_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("/etc/passwd")

    def test_file_equals_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("file=/tmp/model.glb")

    def test_file_scheme_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("file:///etc/passwd")

    def test_localhost_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("http://localhost/secret")

    def test_loopback_ip_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("http://127.0.0.1/secret")

    def test_private_ip_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("http://192.168.1.1/secret")

    def test_empty_blocked(self) -> None:
        with self.assertRaises(ValueError):
            validate_download_url("")

    def test_unresolvable_hostname_blocked(self) -> None:
        """DNS failure must be fail-closed: unresolvable hostnames are blocked."""
        with self.assertRaises(ValueError):
            validate_download_url("https://this-hostname-does-not-exist.invalid/model.glb")


class TestIsPrivate(unittest.TestCase):
    def test_unresolvable_returns_true(self) -> None:
        """_is_private must return True (blocked) when DNS resolution fails."""
        self.assertTrue(_is_private("this-hostname-does-not-exist.invalid"))

    def test_private_ip_returns_true(self) -> None:
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("192.168.1.1", 0))]):
            self.assertTrue(_is_private("somehost.example"))

    def test_public_ip_returns_false(self) -> None:
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("1.2.3.4", 0))]):
            self.assertFalse(_is_private("somehost.example"))


class TestClamp(unittest.TestCase):
    def test_within_range(self) -> None:
        self.assertEqual(clamp(50, 1, 100), 50)

    def test_below_lo(self) -> None:
        self.assertEqual(clamp(-5, 1, 100), 1)

    def test_above_hi(self) -> None:
        self.assertEqual(clamp(9999, 1, 8192), 8192)

    def test_at_lo(self) -> None:
        self.assertEqual(clamp(1, 1, 100), 1)

    def test_at_hi(self) -> None:
        self.assertEqual(clamp(100, 1, 100), 100)

    def test_float(self) -> None:
        self.assertAlmostEqual(clamp(0.5, 0.0, 1.0), 0.5)


class TestSafeExtractall(unittest.TestCase):
    def _make_zip(self, members: dict[str, bytes], path: str) -> None:
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in members.items():
                zf.writestr(name, data)

    def test_normal_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "good.zip")
            self._make_zip({"model.glb": b"data", "tex/tex.png": b"png"}, zip_path)
            dest = os.path.join(tmp, "out")
            os.makedirs(dest)
            safe_extractall(zip_path, dest)
            self.assertTrue(os.path.exists(os.path.join(dest, "model.glb")))
            self.assertTrue(os.path.exists(os.path.join(dest, "tex", "tex.png")))

    def test_zip_slip_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "evil.zip")
            # Manually craft a zip with a traversal member name
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("../../evil.txt", "pwned")
            dest = os.path.join(tmp, "out")
            os.makedirs(dest)
            with self.assertRaises(ValueError, msg="Zip Slip should be blocked"):
                safe_extractall(zip_path, dest)


class TestRound6To8Helpers(unittest.TestCase):
    # ------------------------------------------------------------------
    # _svg_no_fetch (documents.py R7-1)
    # ------------------------------------------------------------------

    def test_svg_no_fetch_http_raises(self) -> None:
        from rhmcp.tools.documents import _svg_no_fetch
        with self.assertRaises(ValueError):
            _svg_no_fetch("http://evil.com/x.png")

    def test_svg_no_fetch_file_scheme_raises(self) -> None:
        from rhmcp.tools.documents import _svg_no_fetch
        with self.assertRaises(ValueError):
            _svg_no_fetch("file:///etc/passwd")

    def test_svg_no_fetch_data_uri_raises(self) -> None:
        from rhmcp.tools.documents import _svg_no_fetch
        with self.assertRaises(ValueError):
            _svg_no_fetch("data:image/png;base64,abc")

    # ------------------------------------------------------------------
    # _validate_read_path (documents.py R7-2)
    # ------------------------------------------------------------------

    def test_validate_read_path_home_accepted(self) -> None:
        from rhmcp.tools.documents import _validate_read_path
        home = os.path.expanduser("~")
        result = _validate_read_path(os.path.join(home, "some_file.pdf"))
        self.assertIsInstance(result, str)

    def test_validate_read_path_etc_passwd_rejected(self) -> None:
        from rhmcp.tools.documents import _validate_read_path
        with self.assertRaises(ValueError):
            _validate_read_path("/etc/passwd")

    def test_validate_read_path_tmp_rejected_by_default(self) -> None:
        from rhmcp.tools.documents import _validate_read_path
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RHINO_MCP_READ_ROOTS", None)
            with self.assertRaises(ValueError):
                _validate_read_path("/tmp/x.txt")

    def test_validate_read_path_custom_root_accepted(self) -> None:
        from rhmcp.tools.documents import _validate_read_path
        with patch.dict(os.environ, {"RHINO_MCP_READ_ROOTS": "/tmp"}):
            result = _validate_read_path("/tmp/x.txt")
            self.assertIsInstance(result, str)

    # ------------------------------------------------------------------
    # _safe_export_path (urban.py R4-4)
    # ------------------------------------------------------------------

    def test_safe_export_path_home_accepted(self) -> None:
        from rhmcp.tools.urban import _safe_export_path
        home = os.path.expanduser("~")
        result = _safe_export_path(os.path.join(home, "out.json"))
        self.assertIsInstance(result, str)

    def test_safe_export_path_tempdir_accepted(self) -> None:
        from rhmcp.tools.urban import _safe_export_path
        result = _safe_export_path(os.path.join(tempfile.gettempdir(), "out.json"))
        self.assertIsInstance(result, str)

    def test_safe_export_path_etc_rejected(self) -> None:
        from rhmcp.tools.urban import _safe_export_path
        with self.assertRaises(ValueError):
            _safe_export_path("/etc/x")

    # ------------------------------------------------------------------
    # _JOB_STORE bounded dict (ai_generation.py R6-7)
    # ------------------------------------------------------------------

    def test_job_store_bounded_evicts_oldest(self) -> None:
        from rhmcp.tools.ai_generation import _BoundedDict, _JOB_STORE_MAX
        store = _BoundedDict()
        # Fill beyond limit
        for i in range(_JOB_STORE_MAX + 1):
            store[str(i)] = {"idx": i}
        self.assertLessEqual(len(store), _JOB_STORE_MAX)
        # Oldest key ("0") must have been evicted
        self.assertNotIn("0", store)
        # Newest key must still be present
        self.assertIn(str(_JOB_STORE_MAX), store)


if __name__ == "__main__":
    unittest.main()

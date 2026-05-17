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
        validate_download_url("https://example.com/model.glb")  # must not raise

    def test_http_allowed(self) -> None:
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

    def test_decimal_ip_localhost_blocked(self) -> None:
        with patch("socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            with self.assertRaises(ValueError, msg="decimal IP for loopback should be blocked"):
                validate_download_url("https://2130706433/secret")

    def test_ipv4_mapped_ipv6_loopback_blocked(self) -> None:
        with patch("socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("::ffff:127.0.0.1", 0))]):
            with self.assertRaises(ValueError, msg="IPv4-mapped IPv6 loopback should be blocked"):
                validate_download_url("https://some-host/secret")

    def test_trailing_dot_localhost_blocked(self) -> None:
        with patch("socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            with self.assertRaises(ValueError, msg="trailing-dot hostname should be blocked"):
                validate_download_url("https://localhost./secret")

    def test_zero_ip_blocked(self) -> None:
        with patch("socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("0.0.0.0", 0))]):
            with self.assertRaises(ValueError, msg="0.0.0.0 should be blocked"):
                validate_download_url("https://0.0.0.0/secret")


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

    def test_symlink_member_raises(self) -> None:
        zf_bytes = io.BytesIO()
        with zipfile.ZipFile(zf_bytes, "w") as zf:
            info = zipfile.ZipInfo("link")
            # Set Unix symlink mode (0xA1FF) in external_attr high 16 bits
            info.external_attr = 0xA1FF0000
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, "/etc/passwd")
        zf_bytes.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            extract_dir = os.path.join(tmp, "out")
            os.makedirs(extract_dir)
            with self.assertRaises(ValueError, msg="symlink member should be blocked"):
                safe_extractall(zf_bytes, extract_dir)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations
import io, os, pytest
from rhmcp.tools_helpers.security import sanitise_rhino_path, validate_download_url, clamp, safe_extractall
import zipfile

class TestSanitiseRhinoPath:
    def test_clean_path_unchanged(self):
        assert sanitise_rhino_path("/tmp/model.3dm") == "/tmp/model.3dm"
    def test_double_quote_stripped(self):
        assert '"' not in sanitise_rhino_path('/tmp/evil"_Quit.3dm')
    def test_backslash_preserved_windows(self):
        assert sanitise_rhino_path(r"C:\Users\alice\model.3dm") == r"C:\Users\alice\model.3dm"
    def test_newline_stripped(self):
        assert "\n" not in sanitise_rhino_path("/tmp/a\nb.3dm")
    def test_carriage_return_stripped(self):
        assert "\r" not in sanitise_rhino_path("/tmp/a\rb.3dm")

class TestValidateDownloadUrl:
    def test_https_allowed(self, monkeypatch):
        import socket as _socket
        # Mock getaddrinfo to return a public IP (1.1.1.1)
        monkeypatch.setattr(
            _socket, "getaddrinfo",
            lambda host, port, *a, **kw: [(None, None, None, None, ("1.1.1.1", 0))]
        )
        validate_download_url("https://sketchfab.com/model.glb")  # must not raise

    def test_unresolvable_hostname_blocked(self, monkeypatch):
        import socket as _socket
        monkeypatch.setattr(
            _socket, "getaddrinfo",
            lambda *a, **kw: (_ for _ in ()).throw(_socket.gaierror("Name not resolved"))
        )
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://not-a-real-host-xyz123.example/")

    def test_http_blocked(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_download_url("http://example.com/model.glb")
    def test_file_scheme_blocked(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_download_url("file:///etc/passwd")
    def test_local_path_blocked(self):
        with pytest.raises(ValueError, match="local"):
            validate_download_url("/etc/passwd")
    def test_file_equals_blocked(self):
        with pytest.raises(ValueError, match="local"):
            validate_download_url("file=/etc/passwd")
    def test_aws_metadata_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://169.254.169.254/latest/meta-data/")
    def test_localhost_blocked(self):
        with pytest.raises(ValueError, match="private"):
            validate_download_url("https://127.0.0.1/secret")
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

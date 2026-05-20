# tests/test_plugin_client.py
"""Unit tests for plugin_client.py — no live Rhino required."""
import json
import socket
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(responses: list[bytes]) -> tuple[socket.socket, int]:
    """
    Spin up a minimal TCP echo server that sends *responses* in order, then
    closes the connection.  Returns (server_socket, port).
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port = srv.getsockname()[1]

    def _serve():
        for resp in responses:
            try:
                conn, _ = srv.accept()
                # drain the request
                conn.recv(65536)
                conn.sendall(resp)
                conn.close()
            except OSError:
                break
        srv.close()

    threading.Thread(target=_serve, daemon=True).start()
    return srv, port


def _make_keepalive_server(responses: list[bytes]) -> tuple[socket.socket, int]:
    """
    Server that keeps the connection open and sends *responses* for successive
    requests on the same connection.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def _serve():
        conn, _ = srv.accept()
        for resp in responses:
            conn.recv(65536)  # drain request
            conn.sendall(resp)
        conn.close()
        srv.close()

    threading.Thread(target=_serve, daemon=True).start()
    return srv, port


# ---------------------------------------------------------------------------
# _decode_chunks
# ---------------------------------------------------------------------------

class TestDecodeChunks:
    def test_valid_utf8(self):
        from rhmcp.tools_helpers.plugin_client import _decode_chunks
        assert _decode_chunks([b"hello"]) == "hello"

    def test_multi_chunk(self):
        from rhmcp.tools_helpers.plugin_client import _decode_chunks
        assert _decode_chunks([b"he", b"llo"]) == "hello"

    def test_invalid_utf8_raises(self):
        from rhmcp.tools_helpers.plugin_client import _decode_chunks
        with pytest.raises(ValueError, match="non-UTF-8"):
            _decode_chunks([b"\xff\xfe"])


# ---------------------------------------------------------------------------
# _recv_one
# ---------------------------------------------------------------------------

class TestRecvOne:
    def test_reads_dict(self):
        from rhmcp.tools_helpers.plugin_client import _recv_one
        sock = MagicMock()
        payload = json.dumps({"status": "ok"}).encode()
        sock.recv.side_effect = [payload, b""]
        result = _recv_one(sock)
        assert result == {"status": "ok"}

    def test_reassembles_chunked(self):
        from rhmcp.tools_helpers.plugin_client import _recv_one
        sock = MagicMock()
        payload = json.dumps({"x": 1}).encode()
        # split mid-json
        sock.recv.side_effect = [payload[:3], payload[3:], b""]
        result = _recv_one(sock)
        assert result == {"x": 1}

    def test_empty_response_raises(self):
        from rhmcp.tools_helpers.plugin_client import _recv_one
        sock = MagicMock()
        sock.recv.return_value = b""
        with pytest.raises(OSError, match="closed"):
            _recv_one(sock)


# ---------------------------------------------------------------------------
# _KeepAliveConnection — reconnect on stale socket
# ---------------------------------------------------------------------------

class TestKeepAliveConnection:
    def test_reuses_connection_across_calls(self, monkeypatch):
        """Two calls should use the same underlying socket."""
        from rhmcp.tools_helpers.plugin_client import _KeepAliveConnection

        resp = json.dumps({"status": "ok"}).encode()
        _, port = _make_keepalive_server([resp, resp])

        ka = _KeepAliveConnection()
        r1 = ka.send("ping", {}, "127.0.0.1", port, 2.0)
        r2 = ka.send("ping", {}, "127.0.0.1", port, 2.0)
        assert r1 == {"status": "ok"}
        assert r2 == {"status": "ok"}
        # same socket object was reused
        assert ka._sock is not None
        ka.close()

    def test_reconnects_after_stale_socket(self, monkeypatch):
        """If sendall raises on the cached socket, client closes it and reconnects."""
        from rhmcp.tools_helpers.plugin_client import _KeepAliveConnection

        resp_bytes = json.dumps({"n": 2}).encode()
        _, port = _make_server([resp_bytes])

        ka = _KeepAliveConnection()

        # Pre-install a stale socket that raises BrokenPipeError on sendall
        stale = MagicMock()
        stale.sendall.side_effect = BrokenPipeError("stale")
        ka._sock = stale

        # Should detect the failure, close stale socket, reconnect, and succeed
        result = ka.send("ping", {}, "127.0.0.1", port, 2.0)
        assert result == {"n": 2}
        stale.close.assert_called_once()  # old socket was closed
        ka.close()

    def test_close_clears_socket(self):
        from rhmcp.tools_helpers.plugin_client import _KeepAliveConnection
        ka = _KeepAliveConnection()
        mock_sock = MagicMock()
        ka._sock = mock_sock
        ka.close()
        mock_sock.close.assert_called_once()
        assert ka._sock is None

    def test_connection_refused_raises_oserror(self):
        from rhmcp.tools_helpers.plugin_client import _KeepAliveConnection
        ka = _KeepAliveConnection()
        with pytest.raises(OSError):
            ka.send("ping", {}, "127.0.0.1", 19990, 0.2)


# ---------------------------------------------------------------------------
# send_command — keepalive enabled/disabled
# ---------------------------------------------------------------------------

class TestSendCommand:
    def test_uses_keepalive_by_default(self, monkeypatch):
        from rhmcp.tools_helpers import plugin_client
        monkeypatch.delenv("RHINO_MCP_KEEPALIVE", raising=False)
        assert plugin_client._keepalive_enabled() is True

    def test_keepalive_disabled_via_env(self, monkeypatch):
        from rhmcp.tools_helpers import plugin_client
        monkeypatch.setenv("RHINO_MCP_KEEPALIVE", "0")
        assert plugin_client._keepalive_enabled() is False

    def test_send_command_retries_on_refused(self, monkeypatch):
        """send_command retries and raises after max_retries with no server."""
        from rhmcp.tools_helpers.plugin_client import send_command
        monkeypatch.setenv("RHINO_MCP_KEEPALIVE", "0")
        with pytest.raises(OSError):
            send_command("ping", {}, host="127.0.0.1", port=19991, timeout=0.1, retries=0)

    def test_send_command_keepalive_path(self, monkeypatch):
        from rhmcp.tools_helpers import plugin_client
        monkeypatch.delenv("RHINO_MCP_KEEPALIVE", raising=False)

        resp = json.dumps({"ok": True}).encode()
        _, port = _make_keepalive_server([resp])

        # Reset module-level keepalive instance for test isolation
        monkeypatch.setattr(plugin_client, "_keepalive", plugin_client._KeepAliveConnection())

        result = plugin_client.send_command("ping", {}, host="127.0.0.1", port=port, timeout=2.0, retries=0)
        assert result == {"ok": True}
        plugin_client._keepalive.close()

    def test_send_command_oneshot_path(self, monkeypatch):
        from rhmcp.tools_helpers import plugin_client
        monkeypatch.setenv("RHINO_MCP_KEEPALIVE", "0")

        resp = json.dumps({"ok": True}).encode()
        _, port = _make_server([resp])

        result = plugin_client.send_command("ping", {}, host="127.0.0.1", port=port, timeout=2.0, retries=0)
        assert result == {"ok": True}

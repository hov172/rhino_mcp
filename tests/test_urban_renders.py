"""Unit tests for urban_renders tools. fal.ai and Rhino calls are mocked."""
from __future__ import annotations
import base64
import unittest
from unittest.mock import patch, MagicMock
from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    import importlib
    import rhmcp.tools.urban_renders as m
    importlib.reload(m)
    mcp = FastMCP("test-renders")
    with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True, "result": {"image_data": base64.b64encode(b"PNG").decode()}}):
        m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


_FAKE_B64 = base64.b64encode(b"fakepng").decode()
_FAL_RESPONSE = {"images": [{"url": "https://fal.ai/fake.png"}], "seed": 42, "request_id": "req-1"}


def _mock_backend(b64: str = _FAKE_B64):
    return {"ok": True, "result": {"image_data": b64}}


def _mock_httpx_for_fal(img_b64: str = _FAKE_B64):
    """Return a mock httpx Client context manager that handles fal POST + image GET."""
    img_bytes = base64.b64decode(img_b64) if img_b64 else b"png"
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = _FAL_RESPONSE
    get_resp = MagicMock()
    get_resp.raise_for_status = MagicMock()
    get_resp.content = img_bytes
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = post_resp
    client.get.return_value = get_resp
    return client


class TestUrbanRenderViews(unittest.TestCase):
    def _call(self, views=None, **kw):
        tools = _register()
        views = views or ["Perspective"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    return tools["urban_render_views"](views=views, **kw)

    def test_returns_one_result_per_view(self):
        results = self._call(views=["Perspective", "Top"])
        self.assertEqual(len(results), 2)

    def test_each_result_has_required_keys(self):
        results = self._call()
        r = results[0]
        for k in ("view", "original_b64", "rendered_b64", "prompt_used", "seed", "ok"):
            self.assertIn(k, r)

    def test_prompt_includes_view_suffix(self):
        results = self._call(views=["Perspective"])
        self.assertIn("street view", results[0]["prompt_used"])

    def test_style_override_appended_to_prompt(self):
        results = self._call(views=["Perspective"], style_override="brutalist concrete")
        self.assertIn("brutalist concrete", results[0]["prompt_used"])

    def test_fal_failure_returns_ok_false_with_original_b64(self):
        tools = _register()
        bad_client = MagicMock()
        bad_client.__enter__ = MagicMock(return_value=bad_client)
        bad_client.__exit__ = MagicMock(return_value=False)
        bad_client.post.side_effect = Exception("timeout")
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=bad_client):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    results = tools["urban_render_views"](views=["Perspective"])
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[0]["original_b64"], _FAKE_B64)
        self.assertEqual(results[0]["rendered_b64"], "")


class TestUrbanRenderStylePreview(unittest.TestCase):
    def test_returns_image_without_rhino_capture(self):
        tools = _register()
        with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
            with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                r = tools["urban_render_style_preview"](style_prompt="brutalist concrete tower")
        self.assertTrue(r["ok"])
        self.assertIn("image_b64", r)
        self.assertIn("seed", r)


class TestUrbanGetRenders(unittest.TestCase):
    def test_returns_empty_dict_when_none_stored(self):
        tools = _register()
        r = tools["urban_get_renders"]()
        self.assertIsInstance(r, dict)
        self.assertEqual(len(r), 0)

    def test_returns_stored_renders_after_render_views(self):
        tools = _register()
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_mock_backend()):
            with patch("httpx.Client", return_value=_mock_httpx_for_fal()):
                with patch.dict("os.environ", {"FAL_KEY": "testkey"}):
                    tools["urban_render_views"](views=["Perspective"])
        r = tools["urban_get_renders"]()
        self.assertIn("Perspective", r)

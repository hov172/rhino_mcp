"""Unit tests for urban_design_language tools. No real API calls."""
from __future__ import annotations
import json
import unittest
from unittest.mock import patch, MagicMock
from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    import importlib
    import rhmcp.tools.urban_design_language as m
    importlib.reload(m)          # reset module-level state between tests
    mcp = FastMCP("test-dl")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


def _mock_client(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(data))]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


_SAMPLE = {
    "style_name": "Contemporary Nordic Mixed-Use",
    "facade_vocabulary": ["brick", "steel", "glass", "setback", "balcony", "planted edge"],
    "material_palette": [{"name": "London Stock Brick", "hex": "#C4956A", "role": "primary"}],
    "colour_story": {"primary": "#C4956A", "secondary": "#1E293B", "accent": "#7DD3FC"},
    "landscape_character": "Dense urban greenery at ground level.",
    "diffusion_prompt": "architectural render, Contemporary Nordic Mixed-Use, brick, photorealistic, 8k",
    "negative_prompt": "cartoon, blurry, low quality",
    "executive_summary": "A warm contemporary scheme with a Nordic character.",
}


class TestUrbanGenerateDesignLanguage(unittest.TestCase):
    def _call(self, **kw):
        tools = _register()
        defaults = dict(brief="Mixed-use in Shoreditch", typology="podium_tower",
                        far=3.5, climate_zone="London")
        defaults.update(kw)
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                return tools["urban_generate_design_language"](**defaults)

    def test_returns_all_schema_keys(self):
        r = self._call()
        self.assertTrue(r["ok"])
        for k in ("style_name", "facade_vocabulary", "material_palette", "colour_story",
                  "landscape_character", "diffusion_prompt", "negative_prompt", "executive_summary"):
            self.assertIn(k, r)

    def test_diffusion_prompt_includes_style_name(self):
        r = self._call()
        self.assertIn("Contemporary Nordic", r["diffusion_prompt"])

    def test_missing_api_key_returns_error(self):
        tools = _register()
        with patch.dict("os.environ", {}, clear=True):
            r = tools["urban_generate_design_language"](
                brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        self.assertFalse(r["ok"])
        self.assertIn("ANTHROPIC_API_KEY", r["error"])


class TestUrbanUpdateDesignLanguage(unittest.TestCase):
    def _setup(self):
        tools = _register()
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                tools["urban_generate_design_language"](
                    brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        return tools

    def test_patches_single_field_preserves_others(self):
        tools = self._setup()
        r = tools["urban_update_design_language"](field="style_name", value="Brutalist Concrete")
        self.assertTrue(r["ok"])
        import rhmcp.tools.urban_design_language as m
        self.assertEqual(m.state().current_design_language["style_name"], "Brutalist Concrete")
        self.assertIn("facade_vocabulary", m.state().current_design_language)

    def test_rederives_diffusion_prompt_on_style_change(self):
        tools = self._setup()
        import rhmcp.tools.urban_design_language as m
        old_prompt = m.state().current_design_language["diffusion_prompt"]
        r = tools["urban_update_design_language"](field="style_name", value="Tropical Brutalist")
        self.assertTrue(r["diffusion_prompt_updated"])
        self.assertNotEqual(m.state().current_design_language["diffusion_prompt"], old_prompt)

    def test_returns_error_on_unknown_field(self):
        tools = self._setup()
        r = tools["urban_update_design_language"](field="nonexistent", value="x")
        self.assertFalse(r["ok"])
        self.assertIn("nonexistent", r["error"])


class TestUrbanGetDesignLanguage(unittest.TestCase):
    def test_returns_zero_defaults_when_none_set(self):
        tools = _register()
        r = tools["urban_get_design_language"]()
        self.assertTrue(r["ok"])
        self.assertFalse(r["set"])
        self.assertEqual(r["style_name"], "")
        self.assertEqual(r["facade_vocabulary"], [])

    def test_returns_set_true_after_generate(self):
        tools = _register()
        with patch("anthropic.Anthropic", return_value=_mock_client(_SAMPLE)):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
                tools["urban_generate_design_language"](
                    brief="test", typology="tower", far=5.0, climate_zone="Tokyo")
        r = tools["urban_get_design_language"]()
        self.assertTrue(r["set"])
        self.assertEqual(r["style_name"], "Contemporary Nordic Mixed-Use")

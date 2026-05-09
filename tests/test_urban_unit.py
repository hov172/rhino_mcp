"""Unit tests for urban massing tools. Requires no running Rhino instance."""
from __future__ import annotations
import unittest
from unittest.mock import patch, MagicMock

from mcp.server.fastmcp import FastMCP


def _register_urban() -> dict[str, object]:
    """
    Register urban module and return tool-name → callable map.
    used by TestUrban* classes in subsequent tasks (Tasks 2–7)
    """
    import importlib
    mod = importlib.import_module("rhmcp.tools.urban")
    mcp = FastMCP("test-urban")
    with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
        mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


class TestUrbanConstants(unittest.TestCase):
    def test_typology_gh_map_has_five_entries(self) -> None:
        import rhmcp.tools.urban as u
        self.assertEqual(len(u._TYPOLOGY_GH_MAP), 5)

    def test_slider_maps_cover_all_typologies(self) -> None:
        import rhmcp.tools.urban as u
        for typology in u._TYPOLOGY_GH_MAP:
            self.assertIn(typology, u._SLIDER_MAPS)
            self.assertGreater(len(u._SLIDER_MAPS[typology]), 0)

    def test_epw_defaults_has_seven_entries(self) -> None:
        import rhmcp.tools.urban as u
        self.assertEqual(len(u._EPW_DEFAULTS), 7)

    def test_parse_metrics_panel_parses_all_fields(self) -> None:
        import rhmcp.tools.urban as u
        text = "GFA: 28000\nFAR: 3.5\nUnits: 280\nOpenSpace: 22"
        m = u._parse_metrics_panel(text)
        self.assertAlmostEqual(m["gfa_m2"], 28000.0)
        self.assertAlmostEqual(m["far"], 3.5)
        self.assertEqual(m["unit_count_est"], 280)
        self.assertAlmostEqual(m["open_space_pct"], 22.0)

    def test_parse_metrics_panel_returns_zeros_on_empty(self) -> None:
        import rhmcp.tools.urban as u
        m = u._parse_metrics_panel("")
        self.assertEqual(m["gfa_m2"], 0.0)
        self.assertEqual(m["far"], 0.0)


class TestUrbanGetMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_returns_zeros_when_no_definition_open(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = None
        fn = self.tools["urban_get_metrics"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn()
        self.assertEqual(result["gfa_m2"], 0.0)
        self.assertEqual(result["far"], 0.0)
        self.assertEqual(result["unit_count_est"], 0)
        self.assertEqual(result["open_space_pct"], 0.0)

    def test_parses_panel_output_correctly(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = "metrics-guid-123"
        fn = self.tools["urban_get_metrics"]
        mock_result = {
            "ok": True,
            "result": {
                "outputs": [{"values": ["GFA: 19200\nFAR: 3.0\nUnits: 192\nOpenSpace: 35"]}]
            },
        }
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=mock_result):
            result = fn()
        self.assertAlmostEqual(result["gfa_m2"], 19200.0)
        self.assertAlmostEqual(result["far"], 3.0)
        self.assertEqual(result["unit_count_est"], 192)
        self.assertAlmostEqual(result["open_space_pct"], 35.0)
        u._current_metrics_guid = None  # cleanup

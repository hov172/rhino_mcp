# tests/test_gh_intelligence.py
from __future__ import annotations

import importlib
import unittest
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    mod = importlib.import_module("rhmcp.tools.gh_intelligence")
    mcp = FastMCP("test-gh-intelligence")
    mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


_PLUGIN_OK_ANALYSIS = {
    "ok": True,
    "component_count": 10,
    "connection_count": 8,
    "wire_crossing_estimate": 5,
    "cluster_count": 2,
    "clusters": [
        {"member_ids": ["aaa", "bbb", "ccc"], "label": "Cluster 1"},
        {"member_ids": ["ddd", "eee"], "label": "Cluster 2"},
    ],
    "ungrouped_component_count": 8,
    "isolated_component_count": 1,
    "complexity_score": 45,
    "canvas_bounds": {"x_min": 0, "x_max": 1000, "y_min": 0, "y_max": 500},
    "suggestions": ["5 wire crossings detected"],
}

_PLUGIN_OK_GRAPH = {
    "ok": True,
    "components": [
        {"id": "aaa", "x": 0.0, "y": 0.0, "name": "Point"},
        {"id": "bbb", "x": 200.0, "y": 0.0, "name": "Circle"},
        {"id": "ccc", "x": 400.0, "y": 0.0, "name": "Extrude"},
    ],
    "connections": [
        {"from_id": "aaa", "to_id": "bbb"},
        {"from_id": "bbb", "to_id": "ccc"},
    ],
}


class TestLayoutUtility(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("rhmcp.tools.gh_intelligence")

    def test_compute_layout_linear_chain(self):
        """A→B→C should get layers 0, 1, 2 (left to right)."""
        components = [
            {"id": "a", "x": 100.0, "y": 50.0},
            {"id": "b", "x": 50.0, "y": 200.0},
            {"id": "c", "x": 300.0, "y": 100.0},
        ]
        connections = [{"from_id": "a", "to_id": "b"}, {"from_id": "b", "to_id": "c"}]
        layout = self.mod._compute_layout(components, connections)
        self.assertIn("a", layout)
        self.assertIn("b", layout)
        self.assertIn("c", layout)
        # a is source → lowest x; c is sink → highest x
        self.assertLess(layout["a"]["x"], layout["b"]["x"])
        self.assertLess(layout["b"]["x"], layout["c"]["x"])

    def test_compute_layout_isolated_node(self):
        """Isolated node (no edges) must still appear in output."""
        components = [{"id": "x", "x": 0.0, "y": 0.0}]
        layout = self.mod._compute_layout(components, [])
        self.assertIn("x", layout)

    def test_clamp_positions_within_bounds(self):
        layout = {"a": {"x": 200.0, "y": 100.0}}
        result = self.mod._clamp_positions(layout)
        self.assertEqual(result["a"]["x"], 200.0)

    def test_clamp_positions_exceeds_max(self):
        layout = {"a": {"x": 999_999.0, "y": -999_999.0}}
        result = self.mod._clamp_positions(layout)
        self.assertEqual(result["a"]["x"], 100_000.0)
        self.assertEqual(result["a"]["y"], -100_000.0)

    def test_load_gh1_to_gh2_map_returns_dict(self):
        mapping = self.mod._load_gh1_to_gh2_map()
        self.assertIsInstance(mapping, dict)

    def test_load_gh1_to_gh2_map_missing_file_returns_empty(self):
        with patch("rhmcp.tools.gh_intelligence._MAP_PATH", "/nonexistent/path.yml"):
            mapping = self.mod._load_gh1_to_gh2_map()
        self.assertEqual(mapping, {})


class TestGhAnalyzeCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def test_returns_ok_fields(self):
        """gh_analyze_canvas passes through the plugin response."""
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK_ANALYSIS):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertIn("complexity_score", result)
        self.assertIn("suggestions", result)

    def test_plugin_error_propagated(self):
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn()
        self.assertFalse(result["ok"])

    def test_oserror_returns_error(self):
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError):
            result = fn()
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()

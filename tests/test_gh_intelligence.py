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


class TestGhRefactorCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def _mock_plugin(self, command, params, rhino_id=None):
        if command == "gh_get_canvas_analysis":
            return _PLUGIN_OK_ANALYSIS
        if command == "gh_get_graph_data":
            return _PLUGIN_OK_GRAPH
        if command == "gh_move_component":
            return {"ok": True}
        if command == "gh_add_group":
            return {"ok": True, "group_id": "new-group-id"}
        return {"ok": False, "error": f"Unexpected command: {command}"}

    def test_preview_mode_makes_no_mutations(self):
        """apply=False must not call gh_move_component."""
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=self._mock_plugin) as mock_pr:
            result = fn(apply=False)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("preview"))
        # gh_move_component must never have been called
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
        self.assertEqual(len(move_calls), 0)

    def test_apply_mode_calls_move_for_each_component(self):
        """apply=True must call gh_move_component once per component."""
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=self._mock_plugin) as mock_pr:
            result = fn(apply=True)
        self.assertTrue(result.get("ok"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
        self.assertEqual(len(move_calls), len(_PLUGIN_OK_GRAPH["components"]))

    def test_dry_run_fails_on_out_of_bounds_position(self):
        """If layout produces out-of-bounds positions, abort before first move."""
        fn = self.tools["gh_refactor_canvas"]

        def bad_graph(command, params, rhino_id=None):
            if command == "gh_get_canvas_analysis":
                return _PLUGIN_OK_ANALYSIS
            if command == "gh_get_graph_data":
                return {"ok": True, "components": [{"id": "z", "x": 0.0, "y": 0.0, "name": "X"}], "connections": []}
            return {"ok": False, "error": "unexpected"}

        # Patch _compute_layout to return an out-of-bounds position
        mod = importlib.import_module("rhmcp.tools.gh_intelligence")
        original = mod._compute_layout
        mod._compute_layout = lambda comps, conns: {"z": {"x": 200_000.0, "y": 0.0}}
        try:
            with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=bad_graph) as mock_pr:
                result = fn(apply=True)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("error_code"), "LAYOUT_VALIDATION_FAILED")
            move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
            self.assertEqual(len(move_calls), 0)
        finally:
            mod._compute_layout = original

    def test_analysis_error_propagated(self):
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn(apply=False)
        self.assertFalse(result["ok"])


class TestGh2RefactorCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    _GH2_GRAPH = {
        "ok": True,
        "components": [
            {"id": "g1", "x": 0.0,   "y": 0.0,   "instance_guid": "g1"},
            {"id": "g2", "x": 100.0, "y": 200.0,  "instance_guid": "g2"},
        ],
        "connections": [{"from_id": "g1", "to_id": "g2"}],
        "groups": [],
    }

    def _mock_gh2_plugin(self, command, params, rhino_id=None):
        if command == "gh2_get_canvas_graph":
            return self._GH2_GRAPH
        if command == "gh2_move_component":
            return {"ok": True}
        if command == "gh2_add_group":
            return {"ok": True, "group_id": "gh2-grp"}
        return {"ok": False, "error": f"Unexpected: {command}"}

    def test_gh2_not_available_returns_error(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH2 not available", "error_code": "GH2_NOT_AVAILABLE"}):
            result = fn(apply=False)
        self.assertFalse(result["ok"])

    def test_preview_makes_no_mutations(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   side_effect=self._mock_gh2_plugin) as mock_pr:
            result = fn(apply=False)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("preview"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh2_move_component"]
        self.assertEqual(len(move_calls), 0)

    def test_apply_calls_gh2_move(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   side_effect=self._mock_gh2_plugin) as mock_pr:
            result = fn(apply=True)
        self.assertTrue(result.get("ok"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh2_move_component"]
        self.assertEqual(len(move_calls), len(self._GH2_GRAPH["components"]))


_EXPORT_DATA = {
    "ok": True,
    "count": 3,
    "components": [
        {
            "instance_guid": "comp-1",
            "type_guid": "57da07bd-ecab-415d-9d86-be1145e9f0eb",
            "nick_name": "Pt",
            "type_name": "GH_Point",
            "x": 0.0, "y": 0.0,
            "inputs": [], "outputs": [{"name": "Pt", "type_name": "Point3d"}],
            "values": {},
            "connections": [{"from_output": "Pt", "to_id": "comp-2", "to_input": "C"}],
        },
        {
            "instance_guid": "comp-2",
            "type_guid": "87f87f55-92ef-4298-ba26-3d7dbde42ad8",
            "nick_name": "Circle",
            "type_name": "GH_Circle",
            "x": 200.0, "y": 0.0,
            "inputs": [{"name": "C", "type_name": "Point3d"}, {"name": "R", "type_name": "Number"}],
            "outputs": [{"name": "C", "type_name": "Circle"}],
            "values": {},
            "connections": [],
        },
        {
            "instance_guid": "comp-3",
            "type_guid": "unknown-guid-not-in-map",
            "nick_name": "LegacyComp",
            "type_name": "GH_SomeLegacyThing",
            "x": 400.0, "y": 0.0,
            "inputs": [], "outputs": [],
            "values": {},
            "connections": [],
        },
    ],
}


class TestGhMigrateToGh2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def test_confirm_false_returns_confirmation_required(self):
        fn = self.tools["gh_migrate_to_gh2"]
        result = fn(confirm=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("error_code"), "CONFIRMATION_REQUIRED")

    def test_confirm_false_never_calls_plugin(self):
        fn = self.tools["gh_migrate_to_gh2"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            fn(confirm=False)
        mock_pr.assert_not_called()

    def test_unmapped_component_in_unmapped_list(self):
        """Components with no GH2 mapping must appear in unmapped, not crash."""
        fn = self.tools["gh_migrate_to_gh2"]

        def mock_plugin(command, params, rhino_id=None):
            if command == "gh1_export_migration_data":
                return _EXPORT_DATA
            if command in ("gh2_start", "gh2_apply_graph"):
                return {"ok": True, "placed": {}, "wired": 0, "errors": []}
            return {"ok": False, "error": f"unexpected: {command}"}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin):
            result = fn(confirm=True)

        self.assertTrue(result.get("ok"))
        self.assertIsInstance(result.get("unmapped"), list)
        unmapped_guids = [u["gh1_guid"] for u in result["unmapped"]]
        self.assertIn("unknown-guid-not-in-map", unmapped_guids)

    def test_export_error_propagated(self):
        fn = self.tools["gh_migrate_to_gh2"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn(confirm=True)
        self.assertFalse(result["ok"])

    def test_unmapped_always_present(self):
        """unmapped key must exist even when all components mapped."""
        fn = self.tools["gh_migrate_to_gh2"]
        export_all_mapped = {
            "ok": True, "count": 1,
            "components": [{
                "instance_guid": "c1",
                "type_guid": "57da07bd-ecab-415d-9d86-be1145e9f0eb",
                "nick_name": "Pt", "type_name": "GH_Point",
                "x": 0.0, "y": 0.0,
                "inputs": [], "outputs": [], "values": {}, "connections": [],
            }],
        }
        def mock_plugin(command, params, rhino_id=None):
            if command == "gh1_export_migration_data":
                return export_all_mapped
            return {"ok": True, "placed": {}, "wired": 0, "errors": []}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin):
            result = fn(confirm=True)

        self.assertIn("unmapped", result)
        self.assertIsInstance(result["unmapped"], list)

    def test_close_gh1_calls_close_definition(self):
        """close_gh1=True must call gh_close_definition."""
        fn = self.tools["gh_migrate_to_gh2"]

        def mock_plugin(command, params, rhino_id=None):
            if command == "gh1_export_migration_data":
                return {"ok": True, "count": 0, "components": []}
            if command in ("gh2_start", "gh2_apply_graph"):
                return {"ok": True, "placed": {}, "wired": 0, "errors": []}
            if command == "gh_close_definition":
                return {"ok": True}
            return {"ok": False, "error": f"unexpected: {command}"}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin) as mock_pr:
            result = fn(confirm=True, close_gh1=True)

        self.assertTrue(result.get("gh1_closed"))
        close_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_close_definition"]
        self.assertEqual(len(close_calls), 1)


class TestGh2IntelligenceTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def test_gh2_move_component_registered(self):
        self.assertIn("gh2_move_component", self.tools)

    def test_gh2_add_group_registered(self):
        self.assertIn("gh2_add_group", self.tools)

    def test_gh2_move_component_passes_through(self):
        fn = self.tools["gh2_move_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": True}) as mock_pr:
            result = fn(instance_guid="abc-123", x=100.0, y=200.0)
        self.assertTrue(result["ok"])
        mock_pr.assert_called_once_with(
            "gh2_move_component",
            {"instance_guid": "abc-123", "x": 100.0, "y": 200.0},
            rhino_id=None,
        )

    def test_gh2_add_group_passes_through(self):
        fn = self.tools["gh2_add_group"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": True, "group_id": "grp-1"}) as mock_pr:
            result = fn(instance_guids=["a", "b"], label="My Group")
        self.assertTrue(result["ok"])
        mock_pr.assert_called_once_with(
            "gh2_add_group",
            {"instance_guids": ["a", "b"], "label": "My Group"},
            rhino_id=None,
        )


if __name__ == "__main__":
    unittest.main()

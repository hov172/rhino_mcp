"""Unit tests for GH2 tool wrappers (no live Rhino required)."""
from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_gh2() -> dict[str, object]:
    """Import gh2, call register() with a fresh FastMCP, return tool-name → fn."""
    mod = importlib.import_module("rhmcp.tools.gh2")
    mcp = FastMCP("test-gh2")
    mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


_PLUGIN_OK = {"ok": True, "backend": "plugin", "result": {}}


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestGH2Registration(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_all_11_tools_registered(self) -> None:
        """All 11 GH2 tools must be registered with correct names."""
        expected = {
            "gh2_start", "gh2_get_canvas_graph", "gh2_apply_graph",
            "gh2_place_component", "gh2_place_slider", "gh2_connect",
            "gh2_connect_many", "gh2_describe_component", "gh2_search_components",
            "gh2_solve_graph", "gh2_clear_canvas",
        }
        registered = set(self.tools.keys())
        self.assertEqual(registered, expected, f"Tool mismatch — extra: {registered - expected}, missing: {expected - registered}")

    def test_register_function_exists(self) -> None:
        """gh2 module must expose a callable register() function."""
        import rhmcp.tools.gh2 as gh2
        self.assertTrue(hasattr(gh2, "register"))
        self.assertTrue(callable(gh2.register))


# ---------------------------------------------------------------------------
# gh2_clear_canvas — confirm guard
# ---------------------------------------------------------------------------

class TestGH2ClearCanvas(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_requires_confirm_true(self) -> None:
        """gh2_clear_canvas must refuse when confirm=False (the default)."""
        fn = self.tools["gh2_clear_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            result = fn(confirm=False)
        self.assertFalse(result["ok"])
        self.assertIn("confirm", result["error"].lower())
        mock_pr.assert_not_called()

    def test_default_confirm_is_false(self) -> None:
        """Calling gh2_clear_canvas with no args must also be refused."""
        fn = self.tools["gh2_clear_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            result = fn()
        self.assertFalse(result["ok"])
        mock_pr.assert_not_called()

    def test_sends_command_when_confirmed(self) -> None:
        """gh2_clear_canvas must call plugin_result when confirm=True."""
        fn = self.tools["gh2_clear_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            result = fn(confirm=True)
        mock_pr.assert_called_once()
        cmd = mock_pr.call_args[0][0]
        self.assertEqual(cmd, "gh2_clear_canvas")

    def test_oserror_returns_structured_error(self) -> None:
        """gh2_clear_canvas must return ok=False (not raise) on OSError."""
        fn = self.tools["gh2_clear_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")):
            result = fn(confirm=True)
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


# ---------------------------------------------------------------------------
# gh2_place_component — guard: name or guid required
# ---------------------------------------------------------------------------

class TestGH2PlaceComponent(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_requires_type_name_or_guid(self) -> None:
        """gh2_place_component must refuse if both type_name and component_guid are absent."""
        fn = self.tools["gh2_place_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            result = fn()
        self.assertFalse(result["ok"])
        mock_pr.assert_not_called()

    def test_accepts_type_name(self) -> None:
        """gh2_place_component must proceed when type_name is given."""
        fn = self.tools["gh2_place_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(type_name="Point")
        mock_pr.assert_called_once()
        cmd, params = mock_pr.call_args[0]
        self.assertEqual(cmd, "gh2_place_component")
        self.assertEqual(params["name"], "Point")

    def test_accepts_component_guid(self) -> None:
        """gh2_place_component must proceed when component_guid is given."""
        guid = "57da07bd-ecab-415d-9cae-be61acf5b7ca"
        fn = self.tools["gh2_place_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(component_guid=guid)
        mock_pr.assert_called_once()
        _, params = mock_pr.call_args[0]
        self.assertEqual(params["component_guid"], guid)

    def test_oserror_returns_structured_error(self) -> None:
        """gh2_place_component must return ok=False (not raise) on OSError."""
        fn = self.tools["gh2_place_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")):
            result = fn(type_name="Circle")
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# gh2_describe_component — guard: instance_guid or name required
# ---------------------------------------------------------------------------

class TestGH2DescribeComponent(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_requires_guid_or_name(self) -> None:
        """gh2_describe_component must refuse if both instance_guid and name are absent."""
        fn = self.tools["gh2_describe_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            result = fn()
        self.assertFalse(result["ok"])
        mock_pr.assert_not_called()

    def test_accepts_instance_guid(self) -> None:
        """gh2_describe_component must proceed when instance_guid is given."""
        fn = self.tools["gh2_describe_component"]
        guid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(instance_guid=guid)
        mock_pr.assert_called_once()

    def test_accepts_name(self) -> None:
        """gh2_describe_component must proceed when name is given."""
        fn = self.tools["gh2_describe_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(name="Point")
        mock_pr.assert_called_once()

    def test_oserror_returns_structured_error(self) -> None:
        """gh2_describe_component must return ok=False (not raise) on OSError."""
        fn = self.tools["gh2_describe_component"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")):
            result = fn(name="Circle")
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# rhino_id forwarding
# ---------------------------------------------------------------------------

class TestGH2RhinoIdForwarding(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_gh2_start_forwards_rhino_id(self) -> None:
        """gh2_start must pass rhino_id as a keyword arg to plugin_result."""
        fn = self.tools["gh2_start"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(rhino_id="12345")
        mock_pr.assert_called_once()
        self.assertEqual(mock_pr.call_args[1].get("rhino_id"), "12345")

    def test_gh2_solve_graph_forwards_rhino_id(self) -> None:
        """gh2_solve_graph must pass rhino_id to plugin_result."""
        fn = self.tools["gh2_solve_graph"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(rhino_id="42")
        mock_pr.assert_called_once()
        self.assertEqual(mock_pr.call_args[1].get("rhino_id"), "42")

    def test_gh2_get_canvas_graph_forwards_rhino_id(self) -> None:
        """gh2_get_canvas_graph must pass rhino_id to plugin_result."""
        fn = self.tools["gh2_get_canvas_graph"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(rhino_id="test-rhino")
        mock_pr.assert_called_once()
        self.assertEqual(mock_pr.call_args[1].get("rhino_id"), "test-rhino")


# ---------------------------------------------------------------------------
# gh2_apply_graph — params forwarding
# ---------------------------------------------------------------------------

class TestGH2ApplyGraph(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def test_applies_components_and_wires(self) -> None:
        """gh2_apply_graph must forward components and wires to plugin."""
        fn = self.tools["gh2_apply_graph"]
        components = [{"key": "a", "type_name": "Point", "x": 0, "y": 0}]
        wires = [{"from_key": "a", "from_output": 0, "to_key": "b", "to_input": 0}]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(components=components, wires=wires)
        mock_pr.assert_called_once()
        _, params = mock_pr.call_args[0]
        self.assertEqual(params["components"], components)
        self.assertEqual(params["wires"], wires)

    def test_omits_wires_when_none(self) -> None:
        """gh2_apply_graph must omit the wires key when wires is None."""
        fn = self.tools["gh2_apply_graph"]
        components = [{"key": "a", "type_name": "Point", "x": 0, "y": 0}]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK) as mock_pr:
            fn(components=components, wires=None)
        _, params = mock_pr.call_args[0]
        self.assertNotIn("wires", params)


# ---------------------------------------------------------------------------
# OSError handling — plugin-only dispatch must never raise
# ---------------------------------------------------------------------------

class TestGH2OSErrorHandling(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK):
            cls.tools = _register_gh2()

    def _check_oserror(self, tool_name: str, **kwargs) -> None:
        fn = self.tools[tool_name]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError("refused")):
            result = fn(**kwargs)
        self.assertFalse(result["ok"], f"{tool_name} should return ok=False on OSError")
        self.assertIn("error", result)

    def test_gh2_start_oserror(self) -> None:
        self._check_oserror("gh2_start")

    def test_gh2_get_canvas_graph_oserror(self) -> None:
        self._check_oserror("gh2_get_canvas_graph")

    def test_gh2_apply_graph_oserror(self) -> None:
        self._check_oserror("gh2_apply_graph", components=[])

    def test_gh2_place_slider_oserror(self) -> None:
        self._check_oserror("gh2_place_slider")

    def test_gh2_connect_oserror(self) -> None:
        self._check_oserror("gh2_connect", from_instance="a", to_instance="b")

    def test_gh2_connect_many_oserror(self) -> None:
        self._check_oserror("gh2_connect_many", wires=[])

    def test_gh2_search_components_oserror(self) -> None:
        self._check_oserror("gh2_search_components", query="point")

    def test_gh2_solve_graph_oserror(self) -> None:
        self._check_oserror("gh2_solve_graph")


if __name__ == "__main__":
    unittest.main()

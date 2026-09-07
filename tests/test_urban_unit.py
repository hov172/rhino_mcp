"""Unit tests for urban massing tools. Requires no running Rhino instance."""
from __future__ import annotations
import base64
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from mcp.server.fastmcp import FastMCP, Image


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


def _canvas_result(mapping: dict[str, str]) -> dict[str, object]:
    return {
        "ok": True,
        "result": {
            "components": [
                {"nick_name": nick, "name": nick, "instance_guid": guid}
                for nick, guid in mapping.items()
            ]
        },
    }


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


class TestUrbanDefinitionAssets(unittest.TestCase):
    def test_typology_definition_files_exist(self) -> None:
        import rhmcp.tools.urban as u
        for typology, path in u._TYPOLOGY_GH_MAP.items():
            self.assertTrue(Path(path).is_file(), f"Missing .gh definition for {typology}: {path}")

    def test_analysis_definition_files_exist(self) -> None:
        import rhmcp.tools.urban as u
        for analysis_type, path in u._ANALYSIS_GH_MAP.items():
            self.assertTrue(Path(path).is_file(), f"Missing .gh analysis definition for {analysis_type}: {path}")

    def test_generator_script_exists_for_gh_assets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        generator = root / "scripts" / "generate_urban_gh.py"
        self.assertTrue(generator.is_file())
        text = generator.read_text()
        for required_name in ["BakeTarget", "Metrics", "analysis_solar.gh", "radiation_mesh"]:
            self.assertIn(required_name, text)


class TestUrbanGetMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_returns_zeros_when_no_definition_open(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_metrics_guid = None
        fn = self.tools["urban_get_metrics"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn()
        self.assertEqual(result["gfa_m2"], 0.0)
        self.assertEqual(result["far"], 0.0)
        self.assertEqual(result["unit_count_est"], 0)
        self.assertEqual(result["open_space_pct"], 0.0)

    def test_parses_panel_output_correctly(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_metrics_guid = "metrics-guid-123"
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
        u.state().current_metrics_guid = None  # cleanup


class TestUrbanGenerateMassing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def _mock_execute_python(self, result_value=None):
        """Return a mock for execute_python that yields the discovery script result."""
        mock = MagicMock()
        mock.return_value = {"ok": True, "result": result_value or {
            "site_width": "guid-sw", "site_depth": "guid-sd",
            "floor_count": "guid-fc", "tower_count": "guid-tc",
            "floor_height": "guid-fh", "footprint_width": "guid-fw",
            "footprint_depth": "guid-fd", "setback": "guid-sb",
            "residential_pct": "guid-rp", "retail_floors": "guid-rf",
            "Metrics": "guid-metrics", "BakeTarget": "guid-bake",
        }}
        return mock

    def _mock_canvas(self):
        return _canvas_result({
            "site_width": "guid-sw", "site_depth": "guid-sd",
            "floor_count": "guid-fc", "tower_count": "guid-tc",
            "floor_height": "guid-fh", "footprint_width": "guid-fw",
            "footprint_depth": "guid-fd", "setback": "guid-sb",
            "residential_pct": "guid-rp", "retail_floors": "guid-rf",
            "Metrics": "guid-metrics", "BakeTarget": "guid-bake",
        })

    def test_returns_error_on_unknown_typology(self) -> None:
        fn = self.tools["urban_generate_massing"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn(typology="spaceship", site_origin=[0, 0, 0],
                        site_width=80, site_depth=80)
        self.assertFalse(result["ok"])
        self.assertIn("spaceship", result["error"])

    def test_opens_correct_gh_file_for_typology(self) -> None:
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return self._mock_canvas()
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="tower", site_origin=[0, 0, 0], site_width=80, site_depth=80)

        open_calls = [(c, p) for c, p in plugin_calls if c == "gh_open_document"]
        self.assertEqual(len(open_calls), 1)
        self.assertIn("tower.gh", open_calls[0][1]["path"])

    def test_sets_site_width_and_depth_sliders(self) -> None:
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return self._mock_canvas()
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="tower", site_origin=[0, 0, 0], site_width=100.0, site_depth=80.0)

        slider_calls = {p.get("instance_guid"): p.get("value")
                        for c, p in plugin_calls if c == "gh_set_slider"}
        self.assertIn("guid-sw", slider_calls)
        self.assertIn("guid-sd", slider_calls)
        self.assertAlmostEqual(slider_calls["guid-sw"], 100.0)
        self.assertAlmostEqual(slider_calls["guid-sd"], 80.0)

    def test_bakes_to_correct_layer(self) -> None:
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return self._mock_canvas()
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="courtyard", site_origin=[0, 0, 0], site_width=80, site_depth=80)

        bake_calls = [(c, p) for c, p in plugin_calls if c == "gh_bake_component"]
        self.assertEqual(len(bake_calls), 1)
        self.assertEqual(bake_calls[0][1]["layer"], "Urban::Massing::courtyard")

    def test_returns_ok_true_with_metrics_fields(self) -> None:
        import rhmcp.tools.urban as u
        fn = self.tools["urban_generate_massing"]

        def capture_plugin(cmd, params):
            if cmd == "gh_get_canvas":
                return self._mock_canvas()
            if cmd == "gh_get_output":
                return {"ok": True, "result": {
                    "outputs": [{"values": ["GFA: 6400\nFAR: 2.0\nUnits: 64\nOpenSpace: 40"]}]
                }}
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            result = fn(typology="courtyard", site_origin=[0, 0, 0],
                        site_width=80, site_depth=80)

        self.assertTrue(result["ok"])
        self.assertIn("gfa_m2", result)
        self.assertIn("far", result)
        self.assertIn("unit_count_est", result)
        self.assertIn("open_space_pct", result)
        u.state().current_typology = None
        u.state().current_slider_guids = {}
        u.state().current_metrics_guid = None
        u.state().current_bake_guid = None


class TestUrbanUpdateParam(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def setUp(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_typology = "tower"
        u.state().current_slider_guids = {"floor_count": "guid-fc", "setback": "guid-sb"}
        u.state().current_metrics_guid = "guid-metrics"

    def tearDown(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_typology = None
        u.state().current_slider_guids = {}
        u.state().current_metrics_guid = None

    def test_calls_gh_set_slider_with_correct_guid(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(param_name="floor_count", value=25.0)
        set_calls = [c for c in mock_plugin.call_args_list if c[0][0] == "gh_set_slider"]
        self.assertEqual(len(set_calls), 1)
        self.assertEqual(set_calls[0][0][1]["instance_guid"], "guid-fc")
        self.assertAlmostEqual(set_calls[0][0][1]["value"], 25.0)

    def test_re_runs_solver_after_setting_value(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(param_name="floor_count", value=10.0)
        solve_calls = [c for c in mock_plugin.call_args_list if c[0][0] == "gh_run_solution"]
        self.assertEqual(len(solve_calls), 1)

    def test_returns_error_on_unknown_param_name(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            result = fn(param_name="nonexistent_param", value=5.0)
        self.assertFalse(result["ok"])
        self.assertIn("nonexistent_param", result["error"])


_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestUrbanCaptureAndEvaluate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def setUp(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_metrics_guid = "guid-metrics"

    def tearDown(self) -> None:
        import rhmcp.tools.urban as u
        u.state().current_metrics_guid = None

    def test_returns_metrics_dict_and_image(self) -> None:
        b64 = base64.b64encode(_PNG_1X1).decode()
        capture_response = {
            "ok": True,
            "result": {"b64": b64, "path": None, "saved": False, "width": 1200, "height": 900},
        }
        metrics_response = {
            "ok": True,
            "result": {"outputs": [{"values": ["GFA: 5000\nFAR: 2.0\nUnits: 50\nOpenSpace: 30"]}]},
        }

        def side_effect(cmd, params):
            if cmd == "gh_get_output":
                return metrics_response
            return {"ok": True}

        fn = self.tools["urban_capture_and_evaluate"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=side_effect), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=capture_response):
            result = fn()

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 2)
        metrics, img = result[0], result[1]
        self.assertIsInstance(metrics, dict)
        self.assertIn("gfa_m2", metrics)
        self.assertIsInstance(img, Image)

    def test_returns_metrics_only_on_capture_failure(self) -> None:
        metrics_response = {
            "ok": True,
            "result": {"outputs": [{"values": ["GFA: 0\nFAR: 0\nUnits: 0\nOpenSpace: 0"]}]},
        }

        def side_effect(cmd, params):
            if cmd == "gh_get_output":
                return metrics_response
            return {"ok": True}

        fn = self.tools["urban_capture_and_evaluate"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=side_effect), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": False, "error": "no view"}):
            result = fn()

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)
        self.assertIn("gfa_m2", result[0])


class TestUrbanRunAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def _mock_discovery(self):
        return _canvas_result({
                "epw_path": "guid-epw",
                "geometry_layer": "guid-layer",
                "analysis_period": "guid-period",
                "grid_size": "guid-grid",
                "radiation_mesh": "guid-mesh",
                "avg_radiation_kwh_m2": "guid-avg",
                "overshadow_hours_worst": "guid-shadow",
        })

    def test_returns_error_on_unknown_analysis_type(self) -> None:
        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn(analysis_type="wind", geometry_layer="Urban::Massing::tower")
        self.assertFalse(result["ok"])
        self.assertIn("wind", result["error"])

    def test_opens_analysis_solar_gh(self) -> None:
        plugin_calls = []

        def capture(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return self._mock_discovery()
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=self._mock_discovery()):
            fn(analysis_type="solar", geometry_layer="Urban::Massing::courtyard", climate_zone="London")

        open_calls = [(c, p) for c, p in plugin_calls if c == "gh_open_document"]
        self.assertEqual(len(open_calls), 1)
        self.assertIn("analysis_solar.gh", open_calls[0][1]["path"])

    def test_sets_epw_path_for_known_climate_zone(self) -> None:
        plugin_calls = []

        def capture(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return self._mock_discovery()
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=self._mock_discovery()):
            fn(analysis_type="solar", geometry_layer="Urban::Massing::tower", climate_zone="Dubai")

        panel_calls = [(c, p) for c, p in plugin_calls if c == "gh_set_panel"]
        epw_calls = [p for _, p in panel_calls if ".epw" in str(p.get("text", ""))]
        self.assertTrue(len(epw_calls) > 0, "Expected a gh_set_panel call with the EPW path")

    def test_returns_radiation_dict_keys(self) -> None:
        def capture(cmd, params):
            if cmd == "gh_get_canvas":
                return self._mock_discovery()
            if cmd == "gh_get_output":
                return {"ok": True, "result": {"outputs": [{"values": ["380"]}]}}
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=self._mock_discovery()):
            result = fn(analysis_type="solar", geometry_layer="Urban::Massing::tower", climate_zone="London")

        self.assertTrue(result["ok"])
        self.assertEqual(result["analysis_type"], "solar")
        self.assertIn("avg_radiation_kwh_m2", result)
        self.assertIn("overshadow_hours_worst", result)


class TestUrbanClearMassing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_deletes_objects_on_urban_layers(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 12}}) as mock_py:
            fn()
        self.assertTrue(mock_py.called)
        code_arg = mock_py.call_args[0][0]
        self.assertIn("Urban", code_arg)

    def test_returns_deleted_count(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 7}}):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 7)

    def test_noop_safe_when_no_objects(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 0}}):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 0)


class TestUrbanBriefPrompt(unittest.TestCase):
    def test_urban_brief_registers_as_prompt(self) -> None:
        import importlib
        mod = importlib.import_module("rhmcp.tools.urban_prompt")
        mcp = FastMCP("test-urban-prompt")
        mod.register(mcp)
        self.assertIn("urban_brief", mcp._prompt_manager._prompts)

    def test_urban_brief_content_contains_mandatory_fields(self) -> None:
        import asyncio
        import importlib

        mod = importlib.import_module("rhmcp.tools.urban_prompt")
        mcp = FastMCP("test-urban-prompt")
        mod.register(mcp)
        prompt = mcp._prompt_manager._prompts["urban_brief"]
        messages = asyncio.run(prompt.render({}))
        text = " ".join(str(m) for m in messages)
        for field in ["site_width", "site_depth", "far_target", "typology", "residential_pct"]:
            self.assertIn(field, text, f"Expected '{field}' in urban_brief content")


class TestUrbanPrdTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_parse_urban_prompt_extracts_far_dimensions_and_mix(self) -> None:
        fn = self.tools["parse_urban_prompt"]
        result = fn("Create a mixed-use district with 4.5 FAR on an 80m x 80m site, 70% residential, 20% office, 10% retail near transit")
        self.assertTrue(result["ok"])
        self.assertEqual(result["far_target"], 4.5)
        self.assertEqual(result["site_width"], 80.0)
        self.assertEqual(result["site_depth"], 80.0)
        self.assertEqual(result["use_mix"]["residential_pct"], 70.0)
        self.assertIn(result["typology"], {"podium_tower", "tower"})
        self.assertEqual(result["missing_fields"], [])

    def test_generate_site_layout_returns_parcels_without_baking(self) -> None:
        fn = self.tools["generate_site_layout"]
        result = fn(site_width=400, site_depth=400, bake=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["layout"]["parcel_count"], 20)
        self.assertGreater(result["layout"]["road_area_m2"], 0)

    def test_calculate_urban_metrics_validates_far_target(self) -> None:
        fn = self.tools["calculate_urban_metrics"]
        result = fn(site_width=100, site_depth=100, gfa_m2=45000, residential_pct=70, far_target=4.5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["metrics"]["far"], 4.5)
        self.assertTrue(result["metrics"]["far_within_2pct"])

    def test_optimize_plan_recommends_tower_floor_count(self) -> None:
        fn = self.tools["optimize_plan"]
        result = fn(target_far=4.5, site_width=80, site_depth=80, typology="tower", apply=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["typology"], "tower")
        self.assertIn("floor_count", result["recommended_params"])

    def test_export_model_rejects_unknown_format(self) -> None:
        fn = self.tools["export_model"]
        result = fn(output_format="ifc")
        self.assertFalse(result["ok"])
        self.assertIn("output_format", result["error"])

    def test_save_project_version_writes_manifest(self) -> None:
        import tempfile
        fn = self.tools["save_project_version"]
        with tempfile.TemporaryDirectory() as tmp, \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {"output": "saved"}}):
            result = fn(project_name="Demo Project", version_name="v1", directory=tmp, metadata={"far": 4.5})
        self.assertTrue(result["ok"])
        self.assertIn("version.json", result["manifest_path"])

    def test_create_urban_scheme_orchestrates_generation(self) -> None:
        fn = self.tools["create_urban_scheme"]
        plugin_calls = []
        mapping = {
            "site_width": "guid-sw", "site_depth": "guid-sd",
            "podium_floors": "guid-pf", "podium_setback": "guid-ps",
            "tower_floors": "guid-tf", "tower_count": "guid-tc",
            "floor_height": "guid-fh", "residential_pct": "guid-rp",
            "retail_pct": "guid-retail", "Metrics": "guid-metrics",
            "BakeTarget": "guid-bake",
        }

        def capture(cmd, params):
            plugin_calls.append((cmd, params))
            if cmd == "gh_get_canvas":
                return _canvas_result(mapping)
            if cmd == "gh_get_output":
                return {"ok": True, "result": {"outputs": [{"values": ["GFA: 28800\nFAR: 4.5\nUnits: 288\nOpenSpace: 20"]}]}}
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture):
            result = fn(prompt="Create a mixed-use district with 4.5 FAR on an 80m x 80m site near transit")
        self.assertTrue(result["ok"])
        self.assertIn("summary", result)
        self.assertEqual(result["metrics"]["far"], 4.5)
        self.assertTrue(any(call[0] == "gh_open_document" for call in plugin_calls))

    def test_create_urban_scheme_uses_geojson_site_boundary_dimensions(self) -> None:
        fn = self.tools["create_urban_scheme"]
        site_boundary = {
            "type": "Polygon",
            "coordinates": [[
                [0, 0], [120, 0], [120, 80], [0, 80], [0, 0],
            ]],
        }
        mapping = {
            "site_width": "guid-sw", "site_depth": "guid-sd",
            "floor_count": "guid-fc", "block_width": "guid-bw",
            "residential_pct": "guid-rp", "retail_pct": "guid-retail",
            "Metrics": "guid-metrics", "BakeTarget": "guid-bake",
        }

        def capture(cmd, params):
            if cmd == "gh_get_canvas":
                return _canvas_result(mapping)
            if cmd == "gh_get_output":
                return {"ok": True, "result": {"outputs": [{"values": ["GFA: 19200\nFAR: 2.0\nUnits: 192\nOpenSpace: 0"]}]}}
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture):
            result = fn(prompt="Create a 2.0 FAR perimeter block", site_boundary=site_boundary)
        self.assertTrue(result["ok"])
        self.assertEqual(result["site_boundary"]["site_width"], 120.0)
        self.assertEqual(result["site_boundary"]["site_depth"], 80.0)
        self.assertEqual(result["parsed"]["site_width"], 120.0)
        self.assertEqual(result["parsed"]["site_depth"], 80.0)

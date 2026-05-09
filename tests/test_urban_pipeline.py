"""Unit tests for urban_pipeline orchestrator. All sub-tools mocked."""
from __future__ import annotations
import importlib
import unittest
from unittest.mock import patch, MagicMock, call
from mcp.server.fastmcp import FastMCP

_SAMPLE_METRICS = {"gfa_m2": 28000.0, "far": 3.5, "unit_count_est": 280, "open_space_pct": 22.0}
_SAMPLE_DL_RESULT = {"ok": True, "style_name": "Nordic", "diffusion_prompt": "nordic render"}
_SAMPLE_RENDERS = [{"view": "Perspective", "ok": True, "rendered_b64": "abc", "original_b64": "abc"}]
_SAMPLE_ANALYSIS = {"ok": True, "avg_radiation_kwh_m2": 380}
_SAMPLE_EXPORT = {"ok": True, "pdf_url": "https://s3.example.com/report.pdf", "html_url": ""}


def _register():
    import rhmcp.tools.urban_pipeline as m
    importlib.reload(m)
    mcp = FastMCP("test-pipeline")
    m.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


class TestUrbanRunStudioPipeline(unittest.TestCase):
    def _run(self, **kw):
        tools = _register()
        defaults = dict(project_name="TestProject", scheme_name="V1",
                        brief="Mixed-use in London", render_views=["Perspective"])
        defaults.update(kw)
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT) as mock_dl:
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       return_value=_SAMPLE_RENDERS) as mock_rv:
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS) as mock_solar:
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT) as mock_export:
                        result = tools["urban_run_studio_pipeline"](**defaults)
        return result, mock_dl, mock_rv, mock_solar, mock_export

    def test_calls_all_four_steps_in_order(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run()
        mock_dl.assert_called_once()
        mock_rv.assert_called_once()
        mock_solar.assert_called_once()
        mock_export.assert_called_once()

    def test_result_contains_report_url(self):
        r, *_ = self._run()
        self.assertTrue(r["ok"])
        self.assertEqual(r["report_url"], "https://s3.example.com/report.pdf")

    def test_skip_renders_skips_render_views_step(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run(skip_steps=["renders"])
        mock_rv.assert_not_called()
        mock_export.assert_called_once()

    def test_include_solar_false_skips_solar_step(self):
        r, mock_dl, mock_rv, mock_solar, mock_export = self._run(include_solar=False)
        mock_solar.assert_not_called()

    def test_render_failure_does_not_abort_pipeline(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT):
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       side_effect=Exception("fal timeout")):
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS):
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT) as mock_export:
                        r = tools["urban_run_studio_pipeline"](
                            project_name="P", scheme_name="S",
                            render_views=["Perspective"])
        mock_export.assert_called_once()
        self.assertIn("renders", r["errors"][0].lower() if r["errors"] else "")

    def test_step_log_has_entry_per_attempted_step(self):
        r, *_ = self._run()
        steps = [s["step"] for s in r["step_log"]]
        self.assertIn("design_language", steps)
        self.assertIn("renders", steps)
        self.assertIn("export", steps)

    def test_design_language_failure_aborts_pipeline(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   side_effect=Exception("API error")):
            r = tools["urban_run_studio_pipeline"](
                project_name="P", scheme_name="S", render_views=["Perspective"])
        self.assertFalse(r["ok"])
        self.assertFalse(r.get("report_url", ""))


class TestUrbanListPipelineRuns(unittest.TestCase):
    def test_accumulates_runs_across_calls(self):
        tools = _register()
        with patch("rhmcp.tools.urban_pipeline._step_generate_design_language",
                   return_value=_SAMPLE_DL_RESULT):
            with patch("rhmcp.tools.urban_pipeline._step_render_views",
                       return_value=_SAMPLE_RENDERS):
                with patch("rhmcp.tools.urban_pipeline._step_run_solar",
                           return_value=_SAMPLE_ANALYSIS):
                    with patch("rhmcp.tools.urban_pipeline._step_export_report",
                               return_value=_SAMPLE_EXPORT):
                        for i in range(3):
                            tools["urban_run_studio_pipeline"](
                                project_name="P", scheme_name=f"V{i}")
        runs = tools["urban_list_pipeline_runs"]()
        self.assertEqual(len(runs), 3)

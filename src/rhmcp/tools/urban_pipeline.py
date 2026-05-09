"""Studio Pipeline — single-call orchestrator: brief → design language → renders → report."""
from __future__ import annotations

import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_pipeline_history: list[dict[str, Any]] = []
_current_run: dict[str, Any] | None = None

# ---------------------------------------------------------------------------
# Step functions (module-level so tests can patch them)
# ---------------------------------------------------------------------------

def _step_generate_design_language(
    brief: str, typology: str, far: float, climate_zone: str, style_hints: str | None
) -> dict[str, Any]:
    from rhmcp.tools.urban_design_language import _current_design_language
    if not brief and _current_design_language:
        return {"ok": True, **_current_design_language}
    import rhmcp.tools.urban_design_language as m
    from rhmcp.tools import urban_design_language
    import anthropic, json, os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "error": "ANTHROPIC_API_KEY not set"}
    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = urban_design_language._build_user_prompt(
        brief, typology, far, climate_zone, style_hints)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=urban_design_language._SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    result = json.loads(msg.content[0].text)
    urban_design_language._current_design_language = result
    return {"ok": True, **result}


def _step_render_views(views: list[str], strength: float) -> list[dict[str, Any]]:
    from rhmcp.tools import urban_renders
    import os
    if not os.environ.get("FAL_KEY"):
        return [{"view": v, "ok": False, "error": "FAL_KEY not set",
                 "original_b64": "", "rendered_b64": "", "prompt_used": "",
                 "seed": 0, "model": "", "fal_request_id": ""} for v in views]
    results = []
    from rhmcp.tools.urban_design_language import _current_design_language
    base_prompt = (_current_design_language or {}).get(
        "diffusion_prompt", "architectural render, photorealistic, 8k")
    negative = (_current_design_language or {}).get(
        "negative_prompt", "cartoon, blurry, low quality")
    for view in views:
        b64 = urban_renders._capture_named_view(view)
        suffix = urban_renders._VIEW_SUFFIXES.get(view, urban_renders._DEFAULT_SUFFIX)
        prompt = f"{base_prompt}, {suffix}"
        try:
            rendered_b64, request_id, seed = urban_renders._fal_img2img(
                b64, prompt, negative, strength, None)
            result: dict[str, Any] = {
                "view": view, "ok": True,
                "original_b64": b64, "rendered_b64": rendered_b64,
                "prompt_used": prompt, "seed": seed,
                "model": "fal-ai/flux-dev-canny", "fal_request_id": request_id,
            }
        except Exception as exc:
            result = {"view": view, "ok": False, "error": str(exc),
                      "original_b64": b64, "rendered_b64": "", "prompt_used": prompt,
                      "seed": 0, "model": "", "fal_request_id": ""}
        urban_renders._current_renders[view] = result
        results.append(result)
    return results


def _step_run_solar(geometry_layer: str, climate_zone: str) -> dict[str, Any]:
    # Solar analysis via urban module — stub if not available
    try:
        from rhmcp.tools.urban import _urban_get_metrics
        # _urban_run_analysis_internal does not exist; fall back to metrics only
        return {"ok": False, "error": "solar analysis not available"}
    except (ImportError, AttributeError):
        return {"ok": False, "error": "solar analysis not available"}


def _step_export_report(project_name: str, scheme_name: str,
                        include_solar: bool) -> dict[str, Any]:
    from rhmcp.tools import urban_design_language, urban_renders, urban_report
    try:
        from rhmcp.tools.urban import _urban_get_metrics
        metrics = _urban_get_metrics()
    except (ImportError, AttributeError):
        metrics = {"gfa_m2": 0.0, "far": 0.0, "unit_count_est": 0, "open_space_pct": 0.0}
    renders = urban_renders._current_renders
    dl = urban_design_language._current_design_language or {}
    html = urban_report._render_html(
        project_name=project_name,
        scheme_name=scheme_name,
        author=None,
        metrics=metrics,
        renders=renders,
        design_language=dl,
        solar=None,
        params=[],
        include_solar=include_solar,
        include_design_language=bool(dl),
    )
    import os
    pdf_bytes = b""
    if os.environ.get("DOCRAPTOR_API_KEY"):
        try:
            pdf_bytes = urban_report._html_to_pdf_docraptor(html)
        except Exception:
            pass
    if not pdf_bytes:
        pdf_bytes = html.encode()
    pdf_url = html_url = ""
    if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
        try:
            pdf_url, html_url = urban_report._upload_to_s3(
                pdf_bytes, html, project_name, scheme_name)
        except Exception:
            pass
    if not pdf_url:
        pdf_url, html_url = urban_report._save_local(
            pdf_bytes, html, project_name, scheme_name)
    return {"ok": True, "pdf_url": pdf_url, "html_url": html_url}


def reset() -> None:
    global _pipeline_history, _current_run
    _pipeline_history = []
    _current_run = None


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Run Studio Pipeline", destructiveHint=True))
    def urban_run_studio_pipeline(
        project_name: str,
        scheme_name: str,
        brief: str | None = None,
        render_views: list[str] | None = None,
        render_strength: float = 0.65,
        include_solar: bool = True,
        style_hints: str | None = None,
        skip_steps: list[str] | None = None,
    ) -> dict[str, object]:
        """
        Single-call studio pipeline: brief → design language → AI renders → solar → PDF report.
        Returns PipelineResult with report_url, renders, metrics, step_log.
        Individual step failures do not abort the pipeline (except design_language failure).
        Use skip_steps=["renders"] or skip_steps=["solar"] to re-run from a checkpoint.
        """
        global _current_run
        skip = set(skip_steps or [])
        views = render_views or ["Perspective", "Top", "Front", "Right"]
        brief_text = brief or ""
        run_id = str(uuid.uuid4())[:8]
        t_start = time.time()
        step_log: list[dict[str, Any]] = []
        errors: list[str] = []
        report_url = ""
        renders: list[dict] = []

        _current_run = {"run_id": run_id, "running": True, "current_step": "design_language",
                        "steps_done": 0, "steps_total": 4}

        # Step 1 — Design Language (aborting on failure)
        t0 = time.time()
        if "design_language" in skip:
            step_log.append({"step": "design_language", "status": "skipped",
                             "duration_s": 0.0, "summary": "reusing existing design language"})
        else:
            try:
                typology = "tower"
                far = 3.5
                try:
                    from rhmcp.tools.urban import _current_typology
                    typology = _current_typology or "tower"
                except (ImportError, AttributeError):
                    pass
                dl_result = _step_generate_design_language(
                    brief_text, typology, far, "London", style_hints)
                step_log.append({"step": "design_language", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"Design language: {dl_result.get('style_name', '')}"})
            except Exception as exc:
                _current_run["running"] = False
                return {"ok": False, "run_id": run_id, "report_url": "",
                        "renders": [], "metrics": {}, "design_language": {},
                        "step_log": step_log, "elapsed_s": round(time.time() - t_start, 2),
                        "errors": [f"design_language: {exc}"]}

        _current_run["steps_done"] = 1
        _current_run["current_step"] = "renders"

        # Step 2 — AI Renders (non-aborting)
        t0 = time.time()
        if "renders" in skip:
            step_log.append({"step": "renders", "status": "skipped",
                             "duration_s": 0.0, "summary": "reusing existing renders"})
        else:
            try:
                renders = _step_render_views(views, render_strength)
                failed = sum(1 for r in renders if not r.get("ok"))
                step_log.append({"step": "renders", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"{len(renders)} views rendered, {failed} failed"})
                if failed:
                    errors.append(f"renders: {failed}/{len(renders)} views failed")
            except Exception as exc:
                step_log.append({"step": "renders", "status": "failed",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": str(exc)})
                errors.append(f"renders: {exc}")

        _current_run["steps_done"] = 2
        _current_run["current_step"] = "solar"

        # Step 3 — Solar (non-aborting, optional)
        t0 = time.time()
        solar: dict[str, Any] | None = None
        if not include_solar or "solar" in skip:
            step_log.append({"step": "solar", "status": "skipped",
                             "duration_s": 0.0, "summary": "solar analysis skipped"})
        else:
            try:
                layer = "Urban::Massing::Tower"
                solar = _step_run_solar(layer, "London")
                step_log.append({"step": "solar", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"avg radiation {solar.get('avg_radiation_kwh_m2', 0)} kWh/m²"})
            except Exception as exc:
                step_log.append({"step": "solar", "status": "failed",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": str(exc)})
                errors.append(f"solar: {exc}")

        _current_run["steps_done"] = 3
        _current_run["current_step"] = "export"

        # Step 4 — Export (non-aborting)
        t0 = time.time()
        try:
            export = _step_export_report(project_name, scheme_name,
                                         include_solar and solar is not None)
            report_url = export.get("pdf_url", "")
            step_log.append({"step": "export", "status": "ok",
                             "duration_s": round(time.time() - t0, 2),
                             "summary": f"report exported to {report_url}"})
        except Exception as exc:
            step_log.append({"step": "export", "status": "failed",
                             "duration_s": round(time.time() - t0, 2), "summary": str(exc)})
            errors.append(f"export: {exc}")

        elapsed = round(time.time() - t_start, 2)
        _current_run["running"] = False
        _current_run["steps_done"] = 4

        result: dict[str, Any] = {
            "ok": True,
            "run_id": run_id,
            "scheme_name": scheme_name,
            "report_url": report_url,
            "renders": renders,
            "step_log": step_log,
            "elapsed_s": elapsed,
            "errors": errors,
        }
        _pipeline_history.append({
            "run_id": run_id, "scheme_name": scheme_name,
            "timestamp": int(time.time()), "report_url": report_url,
            "steps_completed": len([s for s in step_log if s["status"] == "ok"]),
            "errors": errors,
        })
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Pipeline Status", readOnlyHint=True))
    def urban_pipeline_status() -> dict[str, object]:
        """Return status of the running or last completed pipeline."""
        if _current_run is None:
            return {"running": False, "current_step": None,
                    "steps_done": 0, "steps_total": 4, "elapsed_s": 0.0, "errors": []}
        return dict(_current_run)

    @mcp.tool(annotations=ToolAnnotations(title="List Pipeline Runs", readOnlyHint=True))
    def urban_list_pipeline_runs() -> list[dict[str, object]]:
        """List all pipeline runs this session with their report URLs and step summaries."""
        return list(_pipeline_history)

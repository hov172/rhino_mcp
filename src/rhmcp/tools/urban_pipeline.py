"""Studio Pipeline — single-call orchestrator: brief → design language → renders → report."""
from __future__ import annotations
from rhmcp.tools_helpers.workflow_state import current as state

import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# State is stored in the current actor/project/instance scope
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Step functions (module-level so tests can patch them)
# ---------------------------------------------------------------------------

def _step_generate_design_language(
    brief: str, typology: str, far: float, climate_zone: str, style_hints: str | None
) -> dict[str, Any]:
    if not brief and state().current_design_language:
        return {"ok": True, **state().current_design_language}
    from rhmcp.tools import urban_design_language
    import anthropic
    import json
    import os
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
    state().current_design_language = result
    return {"ok": True, **result}


def _step_render_views(views: list[str], strength: float) -> list[dict[str, Any]]:
    from rhmcp.tools import urban_renders
    import os
    if not os.environ.get("FAL_KEY"):
        return [{"view": v, "ok": False, "error": "FAL_KEY not set",
                 "original_b64": "", "rendered_b64": "", "prompt_used": "",
                 "seed": 0, "model": "", "fal_request_id": ""} for v in views]
    results = []
    base_prompt = (state().current_design_language or {}).get(
        "diffusion_prompt", "architectural render, photorealistic, 8k")
    negative = (state().current_design_language or {}).get(
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
        state().current_renders[view] = result
        results.append(result)
    return results


_DEFAULT_LAYER = "Urban::Massing::Tower"
_DEFAULT_CLIMATE = "London"
_DEFAULT_FAR = 3.5


def _current_massing_layer() -> str:
    """Layer urban_generate_massing baked to; falls back to typology, then default."""
    st = state()
    if st.current_massing_layer:
        return st.current_massing_layer
    if st.current_typology:
        return f"Urban::Massing::{st.current_typology}"
    return _DEFAULT_LAYER


def _current_climate_zone(brief: str) -> str:
    """Climate zone parsed from the brief, else the default."""
    if brief:
        try:
            from rhmcp.tools.urban import _parse_urban_prompt_text
            zone = _parse_urban_prompt_text(brief).get("climate_zone")
            if zone:
                return str(zone)
        except Exception:
            pass
    return _DEFAULT_CLIMATE


def _current_far() -> float:
    """FAR from live/cached massing metrics, else the default."""
    try:
        from rhmcp.tools.urban import _urban_get_metrics
        metrics = _urban_get_metrics()
        far = float(metrics.get("far") or 0.0) if metrics.get("ok") else 0.0
        return far if far > 0 else _DEFAULT_FAR
    except Exception:
        return _DEFAULT_FAR


def _step_run_solar(geometry_layer: str, climate_zone: str) -> dict[str, Any]:
    try:
        from rhmcp.tools.urban import _urban_run_solar_internal
        return _urban_run_solar_internal(geometry_layer=geometry_layer, climate_zone=climate_zone)
    except (ImportError, AttributeError) as exc:
        return {"ok": False, "error": f"solar analysis not available: {exc}"}


def _step_export_report(project_name: str, scheme_name: str,
                        include_solar: bool) -> dict[str, Any]:
    from rhmcp.tools import urban_report
    try:
        from rhmcp.tools.urban import _urban_get_metrics
        metrics = _urban_get_metrics()
        solar = state().current_solar if include_solar else None
    except (ImportError, AttributeError):
        metrics = {"ok": False, "source": "unavailable", "gfa_m2": 0.0, "far": 0.0, "unit_count_est": 0, "open_space_pct": 0.0}
        solar = None
    renders = state().current_renders
    dl = state().current_design_language or {}
    html = urban_report._render_html(
        project_name=project_name,
        scheme_name=scheme_name,
        author=None,
        metrics=metrics,
        renders=renders,
        design_language=dl,
        solar=solar,
        params=[],
        include_solar=include_solar and solar is not None,
        include_design_language=bool(dl),
    )
    import os
    pdf_bytes = b""
    if os.environ.get("DOCRAPTOR_API_KEY"):
        try:
            pdf_bytes = urban_report._html_to_pdf_docraptor(html)
        except Exception:
            pass
    pdf_url = html_url = ""
    if os.environ.get("URBAN_AGENT_S3_BUCKET") and os.environ.get("AWS_ACCESS_KEY_ID"):
        try:
            pdf_url, html_url = urban_report._upload_to_s3(
                pdf_bytes, html, project_name, scheme_name)
        except Exception:
            pass
    if not html_url:
        pdf_url, html_url = urban_report._save_local(
            pdf_bytes, html, project_name, scheme_name)
    return {"ok": True, "pdf_url": pdf_url, "html_url": html_url}


def reset() -> None:
    state().pipeline_history = []
    state().current_run = None


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
        """Single-call studio pipeline: brief → design language → AI renders → solar → PDF report.
        Returns PipelineResult with report_url, renders, metrics, step_log.
        Individual step failures..."""
        skip = set(skip_steps or [])
        views = render_views or ["Perspective", "Top", "Front", "Right"]
        brief_text = brief or ""
        run_id = str(uuid.uuid4())[:8]
        t_start = time.time()
        step_log: list[dict[str, Any]] = []
        errors: list[str] = []
        report_url = ""
        renders: list[dict] = []

        state().current_run = {"run_id": run_id, "running": True, "current_step": "design_language",
                        "steps_done": 0, "steps_total": 4}
        climate_zone = _current_climate_zone(brief_text)

        # Step 1 — Design Language (aborting on failure)
        t0 = time.time()
        if "design_language" in skip:
            step_log.append({"step": "design_language", "status": "skipped",
                             "duration_s": 0.0, "summary": "reusing existing design language"})
        else:
            try:
                typology = state().current_typology or "tower"
                dl_result = _step_generate_design_language(
                    brief_text, typology, _current_far(), climate_zone, style_hints)
                if not dl_result.get("ok"):
                    err = dl_result.get("error", "design language generation failed")
                    step_log.append({"step": "design_language", "status": "failed",
                                     "duration_s": round(time.time() - t0, 2),
                                     "summary": err})
                    state().current_run["running"] = False
                    return {"ok": False, "run_id": run_id, "report_url": "",
                            "renders": [], "metrics": {}, "design_language": {},
                            "step_log": step_log, "elapsed_s": round(time.time() - t_start, 2),
                            "errors": [f"design_language: {err}"]}
                step_log.append({"step": "design_language", "status": "ok",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"Design language: {dl_result.get('style_name', '')}"})
            except Exception as exc:
                state().current_run["running"] = False
                return {"ok": False, "run_id": run_id, "report_url": "",
                        "renders": [], "metrics": {}, "design_language": {},
                        "step_log": step_log, "elapsed_s": round(time.time() - t_start, 2),
                        "errors": [f"design_language: {exc}"]}

        state().current_run["steps_done"] = 1
        state().current_run["current_step"] = "renders"

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

        state().current_run["steps_done"] = 2
        state().current_run["current_step"] = "solar"

        # Step 3 — Solar (non-aborting, optional)
        t0 = time.time()
        solar: dict[str, Any] | None = None
        if not include_solar or "solar" in skip:
            step_log.append({"step": "solar", "status": "skipped",
                             "duration_s": 0.0, "summary": "solar analysis skipped"})
        else:
            try:
                solar = _step_run_solar(_current_massing_layer(), climate_zone)
                solar_status = "ok" if solar.get("ok") else "failed"
                step_log.append({"step": "solar", "status": solar_status,
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": f"avg radiation {solar.get('avg_radiation_kwh_m2', 0)} kWh/m²" if solar.get("ok") else solar.get("error", "solar failed")})
                if not solar.get("ok"):
                    errors.append(f"solar: {solar.get('error', 'failed')}")
                    solar = None  # don't pass failed solar to export
            except Exception as exc:
                step_log.append({"step": "solar", "status": "failed",
                                 "duration_s": round(time.time() - t0, 2),
                                 "summary": str(exc)})
                errors.append(f"solar: {exc}")

        state().current_run["steps_done"] = 3
        state().current_run["current_step"] = "export"

        # Step 4 — Export (non-aborting)
        t0 = time.time()
        try:
            export = _step_export_report(project_name, scheme_name,
                                         include_solar and solar is not None)
            report_url = export.get("pdf_url") or export.get("html_url", "")
            if not export.get("ok") or not report_url:
                raise RuntimeError(export.get("error", "Report export did not produce an artifact."))
            step_log.append({"step": "export", "status": "ok",
                             "duration_s": round(time.time() - t0, 2),
                             "summary": f"report exported to {report_url}"})
        except Exception as exc:
            step_log.append({"step": "export", "status": "failed",
                             "duration_s": round(time.time() - t0, 2), "summary": str(exc)})
            errors.append(f"export: {exc}")

        elapsed = round(time.time() - t_start, 2)
        state().current_run["running"] = False
        state().current_run["steps_done"] = 4

        # Collect metrics and design language from session state
        try:
            from rhmcp.tools.urban import _urban_get_metrics
            metrics_out = _urban_get_metrics()
        except (ImportError, AttributeError):
            metrics_out = {}
        try:
            dl_out = state().current_design_language or {}
        except (ImportError, AttributeError):
            dl_out = {}

        result: dict[str, Any] = {
            "ok": not errors,
            "partial": bool(errors),
            "run_id": run_id,
            "scheme_name": scheme_name,
            "report_url": report_url,
            "renders": renders,
            "metrics": metrics_out,
            "design_language": dl_out,
            "step_log": step_log,
            "elapsed_s": elapsed,
            "errors": errors,
        }
        state().pipeline_history.append({
            "run_id": run_id, "scheme_name": scheme_name,
            "timestamp": int(time.time()), "report_url": report_url,
            "steps_completed": len([s for s in step_log if s["status"] == "ok"]),
            "errors": errors,
        })
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Pipeline Status", readOnlyHint=True))
    def urban_pipeline_status() -> dict[str, object]:
        """Return status of the running or last completed pipeline."""
        if state().current_run is None:
            return {"running": False, "current_step": None,
                    "steps_done": 0, "steps_total": 4, "elapsed_s": 0.0, "errors": []}
        return dict(state().current_run)

    @mcp.tool(annotations=ToolAnnotations(title="List Pipeline Runs", readOnlyHint=True))
    def urban_list_pipeline_runs() -> list[dict[str, object]]:
        """List all pipeline runs this session with their report URLs and step summaries."""
        return list(state().pipeline_history)

# Urban Studio Pipeline Implementation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a full AI-driven studio pipeline to rhino_mcp — Claude reads a site brief, generates a design language (style, materials, palette), produces photorealistic AI renders via fal.ai FLUX.1 ControlNet, and exports a branded print-ready PDF report with S3 share link. All four phases are orchestrated by a single `urban_run_studio_pipeline` call.

**Architecture:** Four new MCP tool modules (`urban_design_language`, `urban_renders`, `urban_report`, `urban_pipeline`) sit on top of the existing urban massing tools. Each module is independently usable; the pipeline module orchestrates all four in sequence. External services are cloud APIs (fal.ai, DocRaptor, S3) called from the local MCP server — no backend required. All services degrade gracefully to local fallbacks when env vars are absent.

**Tech Stack:** Python (FastMCP), Anthropic API (claude-sonnet-4-6), fal.ai FLUX.1 Dev Canny, DocRaptor HTML→PDF, boto3 S3, Jinja2, httpx.

**Phase 2 (future):** Thin FastAPI backend wrapping these same services, adding auth, project storage, and a web viewer to graduate to a full SaaS platform. Phase 1 API contracts are designed to make this a configuration swap, not a rewrite.

---

## 1. New Files

| Path | Purpose |
|---|---|
| `src/rhmcp/tools/urban_design_language.py` | 3 MCP tools: generate, update, get design language |
| `src/rhmcp/tools/urban_renders.py` | 3 MCP tools: render views, style preview, get renders |
| `src/rhmcp/tools/urban_report.py` | 3 MCP tools: export report, preview report, list reports |
| `src/rhmcp/tools/urban_pipeline.py` | 3 MCP tools: run pipeline, pipeline status, list runs |
| `src/rhmcp/report_templates/report.html.jinja2` | 7-section branded report template |
| `src/rhmcp/report_templates/report.css` | UrbanAgent visual design tokens + print layout |
| `tests/test_urban_design_language.py` | 6 unit tests, Claude API mocked |
| `tests/test_urban_renders.py` | 7 unit tests, fal.ai httpx mocked |
| `tests/test_urban_report.py` | 8 unit tests, DocRaptor + S3 mocked |
| `tests/test_urban_pipeline.py` | 8 unit tests, all sub-tools mocked |

## 2. Modified Files

| Path | Change |
|---|---|
| `src/rhmcp/tools/urban.py` | `urban_clear_massing` resets `_current_design_language` and `_current_renders` |
| `README.md` | Add Studio Pipeline section: tool list, env vars, workflow, example |

---

## 3. Sub-System ① — Design Language Generator

### `urban_design_language.py`

#### Module-level state

```python
_current_design_language: dict | None = None
```

Set by `urban_generate_design_language`. Read by render and report tools. Reset to `None` by `urban_clear_massing`.

#### `DesignLanguage` schema

```python
{
    "style_name": str,           # e.g. "Contemporary Nordic Mixed-Use"
    "facade_vocabulary": list[str],  # 5–8 descriptors
    "material_palette": list[{      # ordered primary → accent
        "name": str,
        "hex": str,
        "role": str
    }],
    "colour_story": {
        "primary": str,          # hex
        "secondary": str,
        "accent": str
    },
    "landscape_character": str,  # ground-level description
    "diffusion_prompt": str,     # optimised FLUX.1 prompt
    "negative_prompt": str,      # SD negative prompt
    "executive_summary": str     # 2–3 sentences for report cover
}
```

#### `urban_generate_design_language`

```
urban_generate_design_language(
    brief: str,
    typology: str,
    far: float,
    climate_zone: str,
    style_hints: str | None = None,
) -> dict[str, object]
```

**Behaviour:**
1. Builds a system prompt seeding Claude with:
   - Climate zone → biome references (Nordic, Mediterranean, Tropical, Arid, Tropical)
   - FAR range → massing character (≤2.0 low-rise intimate, 2–5 mid-rise urban, >5 high-rise bold)
   - Typology → facade rhythm (courtyard = enclosed courtyard character, tower = iconic singular form)
   - Program mix context if available from `_current_design_language`
2. Calls `anthropic.Anthropic().messages.create(model="claude-sonnet-4-6", ...)` with `response_format` instructing JSON-only output matching the `DesignLanguage` schema.
3. Parses response with `json.loads()`. On `JSONDecodeError`: retries once with stricter prompt. On second failure: returns minimal safe defaults with `ok: false, error`.
4. Stores result in `_current_design_language`.
5. Returns `{ok: true, **design_language}`.

**Env var:** `ANTHROPIC_API_KEY` (already required by the broader project).

#### `urban_update_design_language`

```
urban_update_design_language(
    field: str,
    value: str,
) -> dict[str, object]
```

**Behaviour:**
1. Raises `KeyError` if `field` not in `DesignLanguage` schema keys.
2. Patches `_current_design_language[field] = value`.
3. If `field` in `("material_palette", "facade_vocabulary", "colour_story", "style_name")`: re-derives `diffusion_prompt` by calling `_build_diffusion_prompt(_current_design_language)`.
4. Returns `{ok: true, field, value, diffusion_prompt_updated: bool}`.

#### `urban_get_design_language`

```
urban_get_design_language() -> dict[str, object]
```

Returns `_current_design_language` or zero-safe defaults `{style_name: "", facade_vocabulary: [], material_palette: [], ...}` if none set.

---

## 4. Sub-System ② — AI Render Pipeline

### `urban_renders.py`

#### Module-level state

```python
_current_renders: dict[str, dict] = {}  # view_name → RenderResult
```

#### `RenderResult` schema

```python
{
    "view": str,
    "original_b64": str,    # raw Rhino PNG
    "rendered_b64": str,    # FLUX output PNG (empty string on failure)
    "prompt_used": str,
    "negative_prompt": str,
    "seed": int,
    "strength": float,
    "model": str,           # fal model ID used
    "fal_request_id": str,
    "ok": bool,
    "error": str | None
}
```

#### View-specific prompt suffixes

| View | Suffix appended to `diffusion_prompt` |
|---|---|
| Perspective | `"eye-level street view, urban context, pedestrians, daytime, photorealistic"` |
| Top | `"aerial plan view, rooftop gardens, surrounding streets visible, photorealistic"` |
| Front | `"elevation view, street level, symmetrical facade, architectural quality"` |
| Right / Left | `"side elevation, building profile, clear sky background"` |

#### `urban_render_views`

```
urban_render_views(
    views: list[str] = ["Perspective", "Top", "Front", "Right"],
    strength: float = 0.65,
    style_override: str | None = None,
    seed: int | None = None,
) -> list[dict[str, object]]
```

**Behaviour (per view):**
1. Calls `capture_rhino_view(view=view)` → base64 PNG string.
2. Builds prompt: `design_language["diffusion_prompt"] + " " + _VIEW_SUFFIXES[view] + (" " + style_override if provided)`.
3. POSTs to `https://fal.run/fal-ai/flux-dev-canny` with:
   - `image_url`: `"data:image/png;base64,{b64}"`
   - `prompt`, `negative_prompt`, `strength`, `seed`, `num_images: 1`
   - `Authorization: Key {FAL_KEY}` header
4. Polls `GET https://fal.run/fal-ai/flux-dev-canny/{request_id}` every 2s, timeout 120s.
5. On timeout or HTTP error: retries once with `strength - 0.1`. On second failure: returns `RenderResult` with `ok: false, rendered_b64: "", error: <message>`. Never raises.
6. Stores result in `_current_renders[view]`.

Returns list of `RenderResult` dicts (one per view).

**Env var:** `FAL_KEY`

#### `urban_render_style_preview`

```
urban_render_style_preview(
    style_prompt: str,
    seed: int | None = None,
) -> dict[str, object]
```

Text-to-image via `fal-ai/flux-dev`. No Rhino capture. Returns `{ok, image_b64, prompt_used, seed, fal_request_id}`.

#### `urban_get_renders`

```
urban_get_renders() -> dict[str, object]
```

Returns `_current_renders`. Empty dict if none stored.

---

## 5. Sub-System ③ — Report Generator

### `urban_report.py`

#### Module-level state

```python
_report_history: list[dict] = []  # list of export records this session
```

#### Report sections (report.html.jinja2)

| # | Section | Data source |
|---|---|---|
| 1 | Cover | project_name, scheme_name, author, date, hero render (Perspective), UrbanAgent wordmark |
| 2 | Executive Summary | `design_language.executive_summary`, key stats strip (GFA / FAR / Units / Open Space) |
| 3 | Massing Views | 2×2 grid: Perspective + Top + Front + Right (AI render if available, raw Rhino capture fallback) |
| 4 | Metrics Dashboard | Visual cards: GFA m², FAR, Est. Units, Open Space %, floor count, typology |
| 5 | Solar Analysis | Radiation mesh capture + avg kWh/m² + overshadow worst-case hours + EPW source. Omitted if `include_solar=False` or no solar data |
| 6 | Design Language | Style name, facade vocabulary tags, material palette swatches (hex), landscape character. Omitted if `include_design_language=False` |
| 7 | Parameters Appendix | Full slider table: param, value, units, range |

#### Branding tokens (report.css)

| Token | Value |
|---|---|
| Background | `#0F172A` |
| Card background | `#1E293B` |
| Accent | `#7DD3FC` |
| Body text | `#F1F5F9` |
| Heading font | Inter 700 (Google Fonts, embedded) |
| Body font | Inter 400 |
| Monospace | JetBrains Mono |
| Page size | A4 portrait, 20mm margins |
| Cover | Full-bleed hero image |
| Inner pages | 2-column grid |

#### `urban_export_report`

```
urban_export_report(
    project_name: str,
    scheme_name: str,
    author: str | None = None,
    include_solar: bool = True,
    include_design_language: bool = True,
    format: str = "pdf",
) -> dict[str, object]
```

**Behaviour:**
1. Collects session state: `urban_get_metrics()`, `urban_get_renders()`, `urban_get_design_language()`, solar data from `urban.py` module state.
2. Renders `report.html.jinja2` with Jinja2, base64-inlining all images so the HTML is self-contained.
3. If `format == "pdf"` and `DOCRAPTOR_API_KEY` set: POSTs rendered HTML to `https://docraptor.com/docs` (prince engine, A4). Receives PDF binary.
4. If `URBAN_AGENT_S3_BUCKET` set: uploads PDF to `s3://{bucket}/reports/{project_name}/{scheme_name}/{timestamp}.pdf` via boto3. Generates presigned URL expiring in 7 days. Also uploads HTML version.
5. **Fallback** (no S3/DocRaptor): writes to `~/.urbanagent/reports/{project_name}/{timestamp}/report.pdf` and returns `file://` URL. Never errors due to missing cloud credentials.
6. Appends record to `_report_history`.
7. Returns `{ok, pdf_url, html_url, page_count, file_size_kb, expires_at, local_path}`.

**Env vars:** `DOCRAPTOR_API_KEY`, `URBAN_AGENT_S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

#### `urban_preview_report`

```
urban_preview_report() -> dict[str, object]
```

Renders HTML template only — no PDF conversion, no S3. Writes to `~/.urbanagent/reports/preview_{timestamp}.html`. Returns `{ok, html_path, html_content}`. Used for iteration before final export.

#### `urban_list_reports`

```
urban_list_reports() -> list[dict[str, object]]
```

Returns `_report_history`: list of `{scheme_name, pdf_url, html_url, timestamp, file_size_kb}`.

---

## 6. Sub-System ④ — Studio Pipeline Orchestrator

### `urban_pipeline.py`

#### Module-level state

```python
_pipeline_history: list[dict] = []   # all completed runs this session
_current_run: dict | None = None      # currently executing run
```

#### `StepLog` schema

```python
{
    "step": str,       # "design_language" | "renders" | "solar" | "export"
    "status": str,     # "ok" | "failed" | "skipped"
    "duration_s": float,
    "summary": str     # human-readable one-liner for Claude to narrate
}
```

#### `PipelineResult` schema

```python
{
    "ok": bool,
    "run_id": str,
    "scheme_name": str,
    "report_url": str,
    "html_url": str,
    "renders": dict,            # view → RenderResult
    "metrics": dict,            # gfa, far, units, open_space
    "design_language": dict,    # DesignLanguage
    "solar": dict | None,
    "step_log": list[StepLog],
    "elapsed_s": float,
    "errors": list[str]
}
```

#### `urban_run_studio_pipeline`

```
urban_run_studio_pipeline(
    project_name: str,
    scheme_name: str,
    brief: str | None = None,
    render_views: list[str] = ["Perspective", "Top", "Front", "Right"],
    render_strength: float = 0.65,
    include_solar: bool = True,
    style_hints: str | None = None,
    skip_steps: list[str] = [],
) -> dict[str, object]
```

**Behaviour:**

Step 1 — Design Language (~3s):
- Skip if `"design_language"` in `skip_steps` (reuses `_current_design_language`).
- Calls `urban_generate_design_language(brief=brief or "", typology=_current_typology, far=..., climate_zone=..., style_hints=style_hints)`.
- On failure: aborts pipeline (nothing to build report from).

Step 2 — AI Renders (~40–90s):
- Skip if `"renders"` in `skip_steps`.
- Calls `urban_render_views(views=render_views, strength=render_strength)`.
- On per-view failure: logs error, continues. Report falls back to raw captures.

Step 3 — Solar (~60s, optional):
- Skip if `include_solar=False` or `"solar"` in `skip_steps`.
- Calls `urban_run_analysis(analysis_type="solar", geometry_layer=...)`.
- On failure: logs warning, solar section omitted from report.

Step 4 — Export (~10s):
- Always runs unless Step 1 failed.
- Calls `urban_export_report(project_name, scheme_name, ...)`.

Returns `PipelineResult`. Appends to `_pipeline_history`.

**Typical runtimes:**
- With solar: ~2–3 min total
- Without solar: ~1–2 min total

#### `urban_pipeline_status`

```
urban_pipeline_status() -> dict[str, object]
```

Returns `{running: bool, current_step: str | None, steps_done: int, steps_total: int, elapsed_s: float, errors: list[str]}`.

#### `urban_list_pipeline_runs`

```
urban_list_pipeline_runs() -> list[dict[str, object]]
```

Returns `_pipeline_history`: `{run_id, scheme_name, timestamp, report_url, steps_completed, errors}` per run. Allows Claude to compare across iterations.

---

## 7. Environment Variables

| Variable | Required for | Fallback |
|---|---|---|
| `ANTHROPIC_API_KEY` | Design language generation | None — step fails |
| `FAL_KEY` | AI renders | None — renders skipped, raw captures used |
| `DOCRAPTOR_API_KEY` | PDF conversion | Local WeasyPrint if installed, else HTML only |
| `URBAN_AGENT_S3_BUCKET` | Report cloud storage | Local `~/.urbanagent/reports/` |
| `AWS_ACCESS_KEY_ID` | S3 upload | — |
| `AWS_SECRET_ACCESS_KEY` | S3 upload | — |

All tools degrade gracefully when cloud credentials are absent. `urban_export_report` always produces a local file; S3 and DocRaptor are enhancements.

---

## 8. Testing Strategy

All tests mock external services. No real API calls in the test suite.

### `tests/test_urban_design_language.py`

Mock target: `anthropic.Anthropic` constructor (patch at import site).

- `test_generate_returns_all_schema_keys` — response contains all 8 DesignLanguage fields
- `test_diffusion_prompt_includes_climate_terms` — climate_zone="London" → prompt contains "British"/"Northern European"
- `test_diffusion_prompt_includes_typology_terms` — typology="courtyard" → prompt contains "courtyard"
- `test_update_patches_single_field` — update style_name, all other keys preserved
- `test_update_rederives_diffusion_prompt` — update material_palette → diffusion_prompt changes
- `test_get_returns_zero_defaults_when_none_set` — empty module state → all keys present with safe defaults

### `tests/test_urban_renders.py`

Mock target: `httpx.AsyncClient.post` and `.get`.

- `test_render_views_calls_capture_per_view` — 4 views → 4 capture_rhino_view calls
- `test_prompt_includes_design_language_prompt` — diffusion_prompt from design language included
- `test_view_suffix_appended_per_view` — Perspective view → "eye-level street view" in prompt
- `test_fal_failure_returns_ok_false_with_original_b64` — HTTP 500 → ok:false, original_b64 non-empty
- `test_style_override_appended_to_prompt` — style_override="brutalist" → in prompt_used
- `test_style_preview_calls_flux_dev_not_canny` — no capture_rhino_view called
- `test_get_renders_returns_empty_when_none_stored` — empty module state → {}

### `tests/test_urban_report.py`

Mock targets: `requests.post` (DocRaptor), `boto3.client`.

- `test_export_calls_docraptor_with_rendered_html` — HTML contains project_name
- `test_s3_upload_uses_correct_key_format` — key matches `reports/{project}/{scheme}/{ts}.pdf`
- `test_presigned_url_returned_with_7_day_expiry` — ExpiresIn=604800
- `test_solar_section_omitted_when_flag_false` — rendered HTML lacks "Solar Analysis"
- `test_design_language_section_omitted_when_flag_false` — rendered HTML lacks "Design Language"
- `test_falls_back_to_local_when_s3_not_configured` — no AWS env vars → pdf_url starts with "file://"
- `test_preview_writes_html_without_api_calls` — no DocRaptor/S3 calls
- `test_render_fallback_uses_original_b64` — no renders stored → original_b64 used in template

### `tests/test_urban_pipeline.py`

Mock targets: all 4 sub-tool functions imported directly.

- `test_pipeline_calls_all_four_steps` — all step functions called once
- `test_skip_renders_skips_urban_render_views` — skip_steps=["renders"] → render_views not called
- `test_include_solar_false_skips_analysis` — urban_run_analysis not called
- `test_render_failure_does_not_abort_pipeline` — render_views raises → export still called
- `test_step_log_contains_entry_per_step` — step_log has 4 entries (or 3 if solar skipped)
- `test_result_contains_report_url` — PipelineResult.report_url non-empty
- `test_list_runs_accumulates_across_calls` — 3 pipeline runs → history length 3
- `test_design_language_failure_aborts_pipeline` — generate_design_language raises → ok:false

---

## 9. README Section to Add

Add `## Studio Pipeline` section to `README.md` covering:

- Overview: brief → design language → AI renders → PDF report in one call
- Prerequisites: `FAL_KEY`, `DOCRAPTOR_API_KEY`, `URBAN_AGENT_S3_BUCKET` (all optional — degrades gracefully)
- Tool reference table: all 12 new tools with parameters
- Example conversation: brief → `urban_run_studio_pipeline` → report URL
- Env var setup table
- Phase 2 SaaS note (future)

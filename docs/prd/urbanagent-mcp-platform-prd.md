# UrbanAgent MCP Platform PRD

Source: original PRD RTF supplied by the user, renamed in-product to UrbanAgent to avoid collision with other similarly named systems.

## Product Vision

Build a proprietary AI-powered urban design platform that converts natural-language prompts into editable urban massing models, metrics, visualizations, and branded client deliverables inside Rhino and Grasshopper.

The platform is delivered through MCP so customers can access the functionality without receiving source code, Grasshopper definitions, prompts, or optimization logic.

## Goals

- Convert prompts into structured urban parameters: FAR, GFA, use mix, and height strategy.
- Generate site layouts: roads, blocks, parcels, and open space.
- Generate 3D massing typologies.
- Calculate urban metrics and validate targets.
- Optimize plans iteratively.
- Generate AI-rendered design visualizations.
- Produce branded client PDF reports with AI renders, metrics, and design language.
- Export 3DM, GLB, GeoJSON, and PDF outputs.
- Save project versions.

## MVP MCP Tools

| Tool | Status |
|---|---|
| `parse_urban_prompt` | Implemented |
| `generate_site_layout` | Implemented |
| `generate_massing` | Implemented |
| `calculate_urban_metrics` | Implemented |
| `optimize_plan` | Implemented |
| `render_urban_preview` | Implemented |
| `export_model` | Implemented |
| `save_project_version` | Implemented |
| `create_urban_scheme` | Implemented |
| `urban_generate_design_language` | Implemented |
| `urban_render_views` | Implemented |
| `urban_export_report` | Implemented |
| `urban_run_studio_pipeline` | Implemented |

## Functional Requirements

| Requirement | MVP status | Implementation |
|---|---|---|
| FR-1 Prompt Parsing | Implemented | `parse_urban_prompt` extracts FAR, site dimensions, program mix, typology, climate zone, and missing fields. |
| FR-2 Site Import: Rhino curves, GeoJSON, GIS | Implemented for MVP | `create_urban_scheme` accepts GeoJSON-like `site_boundary` input and derives site dimensions from bbox/coordinates. Rhino geometry import remains available through the existing Rhino object tools. |
| FR-3 Layout Generation | Implemented | `generate_site_layout` produces parcel/block metadata and can bake a `street_grid` Grasshopper definition. |
| FR-4 Massing Generation | Implemented | `generate_massing` / `urban_generate_massing` drive packaged Grasshopper typologies and bake geometry. Supported typologies: `tower`, `podium_tower`, `courtyard`, `perimeter_block`, `street_grid`. |
| FR-5 Metrics Calculation | Implemented | `calculate_urban_metrics` and the massing tools calculate GFA, FAR, units, open space, and FAR-target validation. |
| FR-6 Optimization | Implemented for MVP | `optimize_plan` provides deterministic FAR-fit parameter recommendations and can apply them. |
| FR-7 Design Language | Implemented | `urban_generate_design_language` calls the Claude API to generate a complete design language: style name, facade vocabulary, material palette with hex codes, colour story, landscape character, diffusion prompt, and executive summary. `urban_update_design_language` patches any field. |
| FR-8 AI Rendering | Implemented | `urban_render_views` captures Rhino viewports and AI-renders them via fal.ai FLUX.1 ControlNet img2img using the session design language as the diffusion prompt. Retries with reduced strength on first failure; falls back to raw Rhino captures on double failure. `urban_render_style_preview` generates mood board images without needing a massing model. |
| FR-9 Report Generation | Implemented | `urban_export_report` assembles all session state (metrics, renders, solar, design language) into a branded Jinja2 HTML template, converts to PDF via DocRaptor, uploads to S3, and returns a 7-day presigned URL. Falls back to local `~/.urbanagent/reports/` when cloud credentials are absent. `urban_preview_report` provides fast HTML-only iteration. |
| FR-10 Studio Pipeline | Implemented | `urban_run_studio_pipeline` is a single-call orchestrator: design language → AI renders → solar analysis → PDF export. Steps are skippable via `skip_steps`. Design language failure aborts; render/solar/export failures are logged but the pipeline continues. Returns a `PipelineResult` with `report_url`, `renders`, `metrics`, `design_language`, `step_log`, `elapsed_s`, and `errors`. |
| FR-11 Export | Implemented for MVP | `export_model` supports 3DM, GLB/GLTF, GeoJSON, and PDF export hooks. |
| FR-12 Project Versioning | Implemented | `save_project_version` writes a timestamped model export plus `version.json` manifest. |
| FR-13 Authentication and Billing | Platform-ready boundary | The local Rhino MCP server exposes the tool surface; authentication, billing, tenant isolation, and rate limiting belong in the remote MCP gateway layer before commercial deployment. |

## Current Scope vs Future SaaS

Current scope is the local Rhino MCP MVP: prompt parsing, site/layout/massing tools, Grasshopper definitions, metrics, AI design language, AI renders, PDF report generation, exports, and version manifests running against the user's Rhino environment.

SaaS is a future possibility, not current implementation scope. If the project moves toward a hosted commercial product, the future architecture can add:

- Client layer: Rhino/Grasshopper, Rhino editor, Claude Desktop/ChatGPT MCP clients, web dashboard.
- Remote MCP server: tool registry, authentication, orchestration, audit logging, rate limiting.
- Compute services: FastAPI/Python, Rhino Compute or Rhino.Inside, Grasshopper definitions, optimization engine.
- Storage: PostgreSQL/PostGIS, object storage, Redis cache.

This repository intentionally keeps authentication, billing, multi-tenant isolation, and hosted remote deployment out of the MVP. Those belong in a later SaaS gateway if the project becomes commercial.

## MVP Scope

Phase 1 (implemented):

- Prompt parsing
- Layout generation
- Massing (5 typologies)
- Metrics
- AI design language generation (Claude API)
- AI render pipeline (fal.ai FLUX.1 ControlNet)
- Branded PDF report generation (DocRaptor + S3)
- Studio Pipeline single-call orchestrator
- 3DM/GLB/GeoJSON/PDF export hooks
- MCP integration
- GeoJSON-style site boundary dimensions
- Version manifests

Future SaaS / Phase 2 Possibilities:

- Solar analysis integration in pipeline (stub exists, `urban_run_analysis` wiring)
- Deeper optimization algorithms
- Production rendering queues
- Billing integration
- Remote tenant infrastructure

## External Service Dependencies

| Service | Purpose | Required | Fallback |
|---|---|---|---|
| Claude API (`ANTHROPIC_API_KEY`) | Design language generation | For design language step | Returns error, pipeline aborts |
| fal.ai (`FAL_KEY`) | AI viewport renders | For render step | Returns raw Rhino captures |
| DocRaptor (`DOCRAPTOR_API_KEY`) | HTML→PDF conversion | For PDF export | Saves HTML locally |
| AWS S3 (`URBAN_AGENT_S3_BUCKET` + AWS credentials) | Report cloud storage | For share links | Saves to `~/.urbanagent/reports/` |

## Success Metrics

- Time to first concept under 5 minutes.
- FAR accuracy within 2 percent for generated schemes.
- 95 percent successful job completion.
- Full studio pipeline (design language + 4 AI renders + PDF report) under 3 minutes.
- Commercial SaaS readiness, if that path is pursued later.

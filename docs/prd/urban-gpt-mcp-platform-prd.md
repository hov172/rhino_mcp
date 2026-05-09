# UrbanGPT-Style MCP Platform PRD

Source: `/Users/helpdesk/Downloads/UrbanGPT_MCP_Platform_PRD.rtf`

## Product Vision

Build a proprietary AI-powered urban design platform that converts natural-language prompts into editable urban massing models, metrics, and visualizations inside Rhino and Grasshopper.

The platform is delivered through MCP so customers can access the functionality without receiving source code, Grasshopper definitions, prompts, or optimization logic.

## Goals

- Convert prompts into structured urban parameters: FAR, GFA, use mix, and height strategy.
- Generate site layouts: roads, blocks, parcels, and open space.
- Generate 3D massing typologies.
- Calculate urban metrics and validate targets.
- Optimize plans iteratively.
- Produce render previews.
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

## Functional Requirements

| Requirement | MVP status | Implementation |
|---|---|---|
| FR-1 Prompt Parsing | Implemented | `parse_urban_prompt` extracts FAR, site dimensions, program mix, typology, climate zone, and missing fields. |
| FR-2 Site Import: Rhino curves, GeoJSON, GIS | Implemented for MVP | `create_urban_scheme` accepts GeoJSON-like `site_boundary` input and derives site dimensions from bbox/coordinates. Rhino geometry import remains available through the existing Rhino object tools. |
| FR-3 Layout Generation | Implemented | `generate_site_layout` produces parcel/block metadata and can bake a `street_grid` Grasshopper definition. |
| FR-4 Massing Generation | Implemented | `generate_massing` / `urban_generate_massing` drive packaged Grasshopper typologies and bake geometry. |
| FR-5 Metrics Calculation | Implemented | `calculate_urban_metrics` and the massing tools calculate GFA, FAR, units, open space, and FAR-target validation. |
| FR-6 Optimization | Implemented for MVP | `optimize_plan` provides deterministic FAR-fit parameter recommendations and can apply them. |
| FR-7 Rendering | Implemented for MVP | `render_urban_preview` returns metrics plus a viewport `Image`. Production rendering remains a platform extension. |
| FR-8 Export | Implemented for MVP | `export_model` supports 3DM, GLB/GLTF, GeoJSON, and PDF export hooks. |
| FR-9 Project Versioning | Implemented | `save_project_version` writes a timestamped model export plus `version.json` manifest. |
| FR-10 Authentication and Billing | Platform-ready boundary | The local Rhino MCP server exposes the tool surface; authentication, billing, tenant isolation, and rate limiting belong in the remote MCP gateway layer before commercial deployment. |

## Current Scope vs Future SaaS

Current scope is the local Rhino MCP MVP: prompt parsing, site/layout/massing tools, Grasshopper definitions, metrics, previews, exports, and version manifests running against the user's Rhino environment.

SaaS is a future possibility, not current implementation scope. If the project moves toward a hosted commercial product, the future architecture can add:

- Client layer: Rhino/Grasshopper, Rhino editor, Claude Desktop/ChatGPT MCP clients, web dashboard.
- Remote MCP server: tool registry, authentication, orchestration, audit logging, rate limiting.
- Compute services: FastAPI/Python, Rhino Compute or Rhino.Inside, Grasshopper definitions, optimization engine.
- Storage: PostgreSQL/PostGIS, object storage, Redis cache.

This repository intentionally keeps authentication, billing, multi-tenant isolation, and hosted remote deployment out of the MVP. Those belong in a later SaaS gateway if the project becomes commercial.

## MVP Scope

Phase 1:

- Prompt parsing
- Layout generation
- Massing
- Metrics
- 3DM/GLB/GeoJSON/PDF export hooks
- MCP integration
- GeoJSON-style site boundary dimensions
- Version manifests

Future SaaS / Phase 2 Possibilities:

- Deeper optimization algorithms
- Production rendering queues
- Billing integration
- Remote tenant infrastructure

## Success Metrics

- Time to first concept under 5 minutes.
- FAR accuracy within 2 percent for generated schemes.
- 95 percent successful job completion.
- Commercial SaaS readiness, if that path is pursued later.

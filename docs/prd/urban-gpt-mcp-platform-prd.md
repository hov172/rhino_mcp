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

- FR-1 Prompt Parsing
- FR-2 Site Import: Rhino curves, GeoJSON, GIS
- FR-3 Layout Generation
- FR-4 Massing Generation
- FR-5 Metrics Calculation
- FR-6 Optimization
- FR-7 Rendering
- FR-8 Export
- FR-9 Project Versioning
- FR-10 Authentication and Billing

## Architecture Target

The long-term commercial architecture remains remote-first:

- Client layer: Rhino/Grasshopper, Rhino editor, Claude Desktop/ChatGPT MCP clients, web dashboard.
- Remote MCP server: tool registry, authentication, orchestration, audit logging, rate limiting.
- Compute services: FastAPI/Python, Rhino Compute or Rhino.Inside, Grasshopper definitions, optimization engine.
- Storage: PostgreSQL/PostGIS, object storage, Redis cache.

This repository implements the Rhino-side MVP tool surface and local MCP workflow. Authentication, billing, multi-tenant isolation, and remote deployment are platform-layer work outside the local Rhino plugin/server.

## MVP Scope

Phase 1:

- Prompt parsing
- Layout generation
- Massing
- Metrics
- 3DM/GLB/GeoJSON/PDF export hooks
- MCP integration

Phase 2:

- Deeper optimization
- Production rendering
- Billing
- Remote tenant infrastructure

## Success Metrics

- Time to first concept under 5 minutes.
- FAR accuracy within 2 percent for generated schemes.
- 95 percent successful job completion.
- Monthly recurring revenue readiness for commercial deployment.

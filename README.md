<div align="center">
  <img src="docs/images/readme_header_logo.png" alt="Rhino MCP Banner" width="100%" />
</div>

# Rhino MCP

Control Rhino 3D from Claude, Cursor, Codex, and any other MCP-capable AI tool. Create geometry, manipulate objects, run Grasshopper definitions, manage layers and materials, install plugins, bake results, generate AI 3D models, read design documents (PDFs, drawings, floor plans, spreadsheets, Word docs, SVGs, images), and more — all through natural language.

---

## Table of Contents

- [Quick Start](#quick-start)
  - [Path A — Manual setup with Claude Desktop](#path-a--manual-setup-with-claude-desktop)
  - [Path B — Docker setup with Claude Desktop](#path-b--docker-setup-with-claude-desktop)
  - [Path C — macOS Installer (.pkg)](#path-c--macos-installer-pkg)
- [What You Can Do](#what-you-can-do)
- [Urban Massing Workflow](#urban-massing-workflow)
- [Studio Pipeline](#studio-pipeline)
- [Architecture Overview](#architecture-overview)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Upgrading from a Previous Version](#upgrading-from-a-previous-version)
  - [1. Install the Rhino Plugin](#1-install-the-rhino-plugin)
  - [2. Install the Python MCP Server](#2-install-the-python-mcp-server)
  - [3. Configure API Keys (Studio Pipeline)](#3-configure-api-keys-studio-pipeline)
  - [macOS Installer (.pkg)](#macos-installer-pkg-alternative-to-steps-1--3)
  - [Docker Quick-Start (alternative to steps 2 & 3)](#docker-quick-start-alternative-to-steps-2--3)
- [Starting the Service](#starting-the-service)
- [Connecting AI Clients](#connecting-ai-clients)
  - [Claude Desktop](#claude-desktop)
  - [Claude Code (CLI)](#claude-code-cli)
  - [ChatGPT Desktop](#chatgpt-desktop)
  - [Cursor](#cursor)
  - [Windsurf](#windsurf)
  - [GitHub Copilot (VS Code)](#github-copilot-vs-code)
  - [Codex CLI](#codex-cli)
  - [Gemini CLI](#gemini-cli)
  - [Docker / HTTP Transport](#docker--http-transport)
- [Backend Selection](#backend-selection)
  - [Session & Instance Management](#session--instance-management)
- [Environment Variables](#environment-variables)
- [Tool Profiles](#tool-profiles)
- [Compact Mode](#compact-mode)
- [Remote Host Support](#remote-host-support)
- [Telemetry](#telemetry)
- [Third-Party Plugin Support](#third-party-plugin-support)
  - [Automatic Installation via Yak](#automatic-installation-via-yak)
  - [Manual Installation](#manual-installation)
  - [File-based Installation](#file-based-installation)
  - [Checking Plugin Status](#checking-plugin-status)
- [All 358 Tools](#all-358-tools)
  - [Plugin Management](#plugin-management)
  - [Grasshopper — Canvas](#grasshopper--canvas)
  - [Grasshopper — Parameters](#grasshopper--parameters)
  - [Grasshopper — Solution & Baking](#grasshopper--solution--baking)
  - [Grasshopper — Definition Management](#grasshopper--definition-management)
  - [Grasshopper 2 (GH2)](#grasshopper-2-gh2)
  - [Grasshopper — Intelligence (GH1 Analysis, Refactor & Migration)](#grasshopper--intelligence-gh1-analysis-refactor--migration)
  - [Grasshopper — Pufferfish (Geometry Morphing)](#grasshopper--pufferfish-geometry-morphing)
  - [Grasshopper — Weaverbird (Mesh Subdivision)](#grasshopper--weaverbird-mesh-subdivision)
  - [Grasshopper — LunchBox (Paneling)](#grasshopper--lunchbox-paneling)
  - [Grasshopper — Anemone (Looping)](#grasshopper--anemone-looping)
  - [Grasshopper — Human & Elefront (Attributes)](#grasshopper--human--elefront-attributes)
  - [Grasshopper — Kangaroo Physics](#grasshopper--kangaroo-physics)
  - [Grasshopper — Ladybug Tools & Honeybee](#grasshopper--ladybug-tools--honeybee)
  - [Geometry Creation](#geometry-creation)
  - [Object Editing & Selection](#object-editing--selection)
  - [Layers](#layers)
  - [Materials](#materials)
  - [PBR Materials & Rendering](#pbr-materials--rendering)
  - [V-Ray Rendering](#v-ray-rendering)
  - [Enscape Real-Time Rendering](#enscape-real-time-rendering)
  - [Views & Viewport](#views--viewport)
  - [Document & File I/O](#document--file-io)
  - [Document Reading](#document-reading)
  - [Scripting](#scripting)
  - [Boolean Operations](#boolean-operations)
  - [Curve Operations](#curve-operations)
  - [AI Generation](#ai-generation)
  - [Studio Pipeline Tools](#studio-pipeline-tools)
  - [Asset Libraries (Poly Haven & Sketchfab)](#asset-libraries-poly-haven--sketchfab)
  - [VisualARQ (Architectural BIM)](#visualarq-architectural-bim)
  - [Lands Design (Landscape)](#lands-design-landscape)
  - [Annotations](#annotations)
  - [Blocks (Instance Definitions)](#blocks-instance-definitions)
  - [Groups](#groups)
  - [Analysis & Measurement](#analysis--measurement)
  - [User Data (Object & Document Attributes)](#user-data-object--document-attributes)
  - [Surface Operations](#surface-operations)
  - [Mesh Operations](#mesh-operations)
  - [Advanced Transforms](#advanced-transforms)
  - [Extended Curve Operations](#extended-curve-operations)
  - [Extended Selection](#extended-selection)
  - [Extended Material Tools](#extended-material-tools)
  - [Extended View Tools](#extended-view-tools)
  - [Extended Document Tools](#extended-document-tools)
  - [Reference-Compatible Aliases](#reference-compatible-aliases)
- [Skills (prompt packages for ChatGPT, Codex, Claude)](#skills)
- [Studio Pipeline Env Vars](#studio-pipeline-env-vars)
- [Building the Plugin from Source](#building-the-plugin-from-source)
- [Running Tests](#running-tests)
- [References](#references)

---

## Quick Start

**Version 0.19.0:** fixes the Grasshopper 2 wiring and graph contracts, makes script components honour requested ports, implements environment maps, derives the studio pipeline's solar inputs from the baked massing, and removes every parameter that was accepted but never applied. Tools now report `applied` / `not_applied`. Ships a `skills/` folder of Agent Skills. See the [0.19.0 upgrade guide](docs/upgrade-0.19.0.md). The [secure-operation requirements](docs/secure-operation.md) and macOS registration fixes remain in effect.

> **Two separate pieces — both are required:**
>
> | Piece | What it is | Where it runs |
> |---|---|---|
> | `rhino-mcp.rhp` | Rhino plugin — opens a socket on port 1999 | Inside Rhino 3D |
> | This repo (`rhmcp`) | Python MCP server — talks to AI clients | Outside Rhino, as a separate process |
>
> The plugin and the Python server communicate over a local TCP socket. Neither works without the other.

Two paths to get up and running. Both require the Rhino plugin — only the server setup differs.

| Choose this path | When to use it |
|---|---|
| **Path A — Manual setup** | Best for development, local editing, and users already comfortable with Python/uv. Claude Desktop starts the MCP server with stdio. |
| **Path B — Docker setup** | Best when you want isolated Python dependencies or an HTTP MCP endpoint for multiple clients. Rhino still runs on the host machine. |
| **Path C — macOS Installer** | Best for macOS users who want zero-terminal setup. Double-click the `.pkg` (Apple Silicon or Intel, Rhino 7/8/9), and the installer handles Python, the MCP server, and AI client configuration automatically. |

For first-time installs, use `RHINO_MCP_BACKEND=plugin`. The plugin backend is the full-featured path and is required for Grasshopper support.

---

### Path A — Manual setup with Claude Desktop

**Prerequisites:** Rhino 7 or 8, Python 3.10+, [uv](https://docs.astral.sh/uv/) (`pip install uv`), git.

#### Step 1 — Clone the repo

```bash
git clone https://github.com/hov172/rhino_mcp.git
cd rhino_mcp
uv sync          # installs all Python dependencies from uv.lock
```

#### Step 2 — Install the Rhino plugin

The plugin file is included in the repo at `rhino_plugin/package/rhino-mcp.rhp`. Copy it to the Rhino plug-ins folder:

```bash
# macOS — user plug-ins folder (no admin rights needed)
mkdir -p "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp"
cp rhino_plugin/package/rhino-mcp.rhp rhino_plugin/package/*.json rhino_plugin/package/*.dll \
   "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/"
```

```powershell
# Windows
Copy-Item rhino_plugin\package\rhino-mcp.rhp `
  "$env:APPDATA\McNeel\Rhinoceros\8.0\Plug-ins\"
```

Restart Rhino. The plugin loads automatically and starts its socket server on `127.0.0.1:1999`.

> **This is the only file that goes into Rhino.** The `rhino_plugin/package/rhino-mcp.rhp` file is the Rhino plugin binary. The rest of the repo (the `src/` folder) is the Python MCP server — a completely separate process that never touches Rhino's plug-ins folder.
>
> **Don't have the repo yet?** You can also download `rhino-mcp.rhp` directly from the [latest release](https://github.com/hov172/rhino_mcp/releases/latest) and copy it from `~/Downloads/` instead.

#### Step 3 — Verify the Python MCP server

> **This is the MCP server — not another plugin.** It runs as a separate Python process outside Rhino and exposes the 358 tools to your AI client. Claude Desktop spawns it automatically from the cloned folder.

```bash
uv run python -m rhmcp --help
```

You should see the argument list printed. If you see it, the server is ready.

To verify the documented tool count from source:

```bash
uv run python -c "from rhmcp.tools_helpers.compact_registry import CompactRegistry; r=CompactRegistry(); r.load_from_modules(None); print(len(r._tools))"
```

Expected output: `358`.

#### Step 4 — Tell Claude Desktop how to start the server

This is the key step. Claude Desktop reads a config file and **automatically spawns the MCP server as a child process** every time you open it — you never start the server manually.

Edit the config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add this (replace `/path/to/rhino-mcp` with the actual path where you cloned the repo):

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "",
        "URBAN_AGENT_S3_BUCKET": ""
      }
    }
  }
}
```

The `command` + `args` lines are literally the shell command Claude Desktop runs to start the server. The `env` block sets environment variables for that process — this is how API keys are passed in without touching your system environment.

> **Minimum required:** only `RHINO_MCP_BACKEND`, `RHINO_MCP_HOST`, and `RHINO_MCP_PORT` are needed for basic Rhino tools. Add `ANTHROPIC_API_KEY` for design language generation and `FAL_KEY` for AI renders. Leave others blank or omit them.

#### Step 5 — Start Rhino

1. Open Rhino 3D.
2. The plugin starts its socket server automatically — you should see `Rhino MCP listening on 127.0.0.1:1999` in the command history.
3. If the auto-start message doesn't appear, type `MCPStart` manually. Use `MCPStatus` to verify at any time. Type `MCPHelp` to open the full documentation in your browser.

#### Step 6 — Restart Claude Desktop and start using it

Fully quit Claude Desktop (don't just close the window) and reopen it. Claude Desktop reads the config on launch, spawns the MCP server in the background, and the 358 Rhino tools become available automatically.

Test it by typing in Claude:

> *"Create a sphere with radius 5 at the origin"*

You should see a sphere appear in Rhino.

**Connection flow:**
```
Claude Desktop → spawns → python -m rhmcp (stdio)
                               ↓
                          127.0.0.1:1999 (Rhino plugin)
                               ↓
                          Rhino 3D geometry
```

---

### Path B — Docker setup with Claude Desktop

Prepare the certificates and shared plugin secret described in [secure operation](docs/secure-operation.md#tls). Set `RHINO_MCP_CERT_DIR` to that local certificate directory. The HTTP certificate must cover `localhost`; the plugin certificate must cover `host.docker.internal`.

Docker bundles the Python server and all dependencies into a self-contained image. No Python, no uv, no cloning required on the machine running the container.

**Prerequisites:** Rhino 7 or 8, Docker Desktop.

#### Step 1 — Install the Rhino plugin

Same as Path A Step 1 above. The plugin must run inside Rhino on your machine — it cannot be containerized.

#### Step 2 — Build and run the Docker image

```bash
# Clone just to get the Dockerfile (or copy it manually)
git clone https://github.com/hov172/rhino_mcp.git
cd rhino_mcp

# Build
docker build -t rhino-mcp .

# Run — paste your real API keys
docker run -d \
  -p 8000:8000 \
  -v "$RHINO_MCP_CERT_DIR:/certs:ro" \
  -e RHINO_MCP_HTTP_TLS_CERT=/certs/http-server.pem \
  -e RHINO_MCP_HTTP_TLS_KEY=/certs/http-server-key.pem \
  -e RHINO_MCP_HTTP_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_SECRET="$RHINO_MCP_PLUGIN_SECRET" \
  -e RHINO_MCP_AUTH_TOKEN="replace-with-a-unique-random-token-at-least-32-chars" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e FAL_KEY="..." \
  --name rhino-mcp \
  rhino-mcp
```

The container starts the MCP server in HTTP mode and defaults `RHINO_MCP_HOST=host.docker.internal`, which resolves to the Docker host on macOS and Windows automatically.

**Linux only** — add one extra flag:

```bash
docker run -d -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -v "$RHINO_MCP_CERT_DIR:/certs:ro" \
  -e RHINO_MCP_HTTP_TLS_CERT=/certs/http-server.pem \
  -e RHINO_MCP_HTTP_TLS_KEY=/certs/http-server-key.pem \
  -e RHINO_MCP_HTTP_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_SECRET="$RHINO_MCP_PLUGIN_SECRET" \
  -e RHINO_MCP_AUTH_TOKEN="replace-with-a-unique-random-token-at-least-32-chars" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e FAL_KEY="..." \
  --name rhino-mcp \
  rhino-mcp
```

Verify the server is up (the `/health` endpoint needs no auth):

```bash
curl --cacert "$RHINO_MCP_CERT_DIR/ca.pem" https://localhost:8000/health
```

All other endpoints require the bearer token: `Authorization: Bearer <your RHINO_MCP_AUTH_TOKEN>`. If you didn't set `RHINO_MCP_AUTH_TOKEN`, a random token was generated at startup — find it with `docker logs rhino-mcp`.

#### Step 3 — Tell Claude Desktop to connect via URL

In HTTP mode the server is already running — Claude Desktop connects to it rather than spawning it. Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rhino": {
      "url": "https://localhost:8000/",
      "headers": {
        "Authorization": "Bearer replace-with-a-unique-random-token-at-least-32-chars"
      }
    }
  }
}
```

No `command`, no `args`, no `env` — the API keys were set when you ran the container. The `Authorization` value must match the `RHINO_MCP_AUTH_TOKEN` you passed to `docker run`.

#### Step 4 — Start Rhino and activate the plugin

Same as Path A Step 4. Open Rhino — the plugin auto-starts and prints `Rhino MCP listening on 127.0.0.1:1999`. Run `MCPStatus` to confirm. Type `MCPHelp` to open the docs.

#### Step 5 — Restart Claude Desktop and start using it

Fully quit and reopen Claude Desktop. It connects to the running container and the 358 tools appear.

**Connection flow:**
```
Claude Desktop → HTTP → localhost:8000 (Docker container)
                               ↓
                    host.docker.internal:1999 (Rhino plugin)
                               ↓
                          Rhino 3D geometry
```

---

### Path C — macOS Installer (.pkg)

The `.pkg` installer is the fastest way to get up and running on macOS. It requires no terminal, no Python install, and no manual config editing.

**Requirements:** macOS 13 Ventura or later · Rhino 8.17+ · Apple Silicon or Intel. GH2 tools require Rhino 9 with GH2 loaded.

**What it installs:**
- A self-contained Python 3.13 runtime and virtual environment under `/Users/Shared/rhino_mcp/` (shared across all users on the machine)
- The `rhino-mcp.rhp` plugin and dependencies into version-specific `MacPlugIns` bundles for detected Rhino 8 and 9 installations
- The `rhino` MCP server entry into Claude Desktop and Claude Code automatically

**Steps:**
1. Download the [signed and notarized 0.19.0 installer](https://github.com/hov172/rhino_mcp/releases/download/v0.19.0/rhino-mcp-0.19.0-universal-signed.pkg)
2. Quit Rhino completely, then double-click the `.pkg` and follow the installer prompts
3. Launch Rhino — the plugin loads automatically
4. Launch your AI client — the MCP server is already configured

> The installer backs up conflicting legacy copies and repairs cached plugin paths. If no GUI user is logged in during installation, run `/usr/local/bin/rhino-mcp-configure` after login with Rhino closed. See the [upgrade guide](docs/upgrade-0.17.1.md) for backup locations and verification.

The [signed 0.19.0 uninstaller](https://github.com/hov172/rhino_mcp/releases/download/v0.19.0/rhino-mcp-0.19.0-universal-uninstaller-signed.pkg) is available in the same release.

---

## What You Can Do

| Category | Examples |
|---|---|
| **Plugin Management** | Check if a plugin is installed, automatically install via Yak, install from `.gha`/`.rhp`/`.rhi` files, list all loaded plugins, introspect any plugin's commands |
| **Grasshopper** | Place components, draw wires, set sliders/panels, run solutions, bake geometry to Rhino doc, add script components |
| **Grasshopper 2 (GH2)** | Start GH2 editor, get canvas graph, atomically apply a full graph (components + wires), place components/sliders, connect wires, describe components, search component library, solve, clear canvas. `gh2_apply_graph` is the recommended way to build complex GH2 definitions in one round-trip. **Requires Rhino 9** (not available in stable Rhino 8). |
| **GH — Pufferfish** | Tween curves, morph geometry between surfaces, blend surfaces, twist and bend objects |
| **GH — Weaverbird** | Catmull-Clark / Loop / Butterfly subdivision, mesh frame, mesh thickening, face extrusion |
| **GH — LunchBox** | Quad, triangle, diamond, and hexagonal paneling on surfaces; space frame generation |
| **GH — Anemone** | Set up iterative feedback loops (Loop Start + Loop End), configure max iterations |
| **GH — Human & Elefront** | Bake with full attribute control (layer, name, user text), reference objects by filter, set/get user text on Rhino objects |
| **GH — Kangaroo** | Set up physics solvers, add and wire physics goals (Length, Angle, Anchor, Spring, Pressure, Load, Hinge, etc.), run simulations |
| **GH — Ladybug / Honeybee** | Load EPW weather data, sun path, radiation analysis, wind rose, UTCI comfort; create Honeybee rooms, add windows, run energy simulations |
| **UrbanAgent Platform** | Parse urban prompts, generate site layouts and massing, calculate/validate metrics, optimize FAR, render previews, export models, save versions, and orchestrate full schemes. **Studio Pipeline:** generate design language (Claude API), AI-render viewports (fal.ai FLUX.1), export branded PDF reports (DocRaptor + S3), run all steps with a single `urban_run_studio_pipeline` call |
| **Geometry** | Create boxes, spheres, cylinders, cones, tori, curves, surfaces, meshes, text, arcs, ellipses, planes, and more |
| **Modeling** | Boolean union/difference/intersection, loft, extrude, sweep, offset, pipe, project/intersect/split curves |
| **Document Reading** | Read PDF files page-by-page as images; extract vector paths and dimension annotations from CAD-exported PDFs; calibrate pixel-to-real-world scale; read images (JPG, PNG, TIFF, HEIC, WebP); read CSV/Excel spreadsheets; parse SVG drawings; extract text and tables from Word (.docx) documents — all without leaving the MCP session |
| **Objects** | Select, move, rotate, scale, rename, change layer/color, delete, undo/redo. Filter by bounding box spatial region. Apply attribute changes to all objects at once with `apply_to_all` |
| **Layers** | List, create, delete, set current, change color/visibility/lock |
| **Materials** | Create, assign, and delete standard and PBR materials; set environment maps; configure render settings |
| **V-Ray** | Start/stop IPR, render to file, create and apply V-Ray materials, add lights (Rectangle/Sphere/IES/Dome/Sun), set HDRI environment, configure GI presets, export `.vrscene` |
| **Enscape** | Launch Enscape window, capture screenshots, export 360° panoramas, export standalone executables, set time of day and atmosphere, save named views |
| **Views** | Capture the active viewport — **Claude receives the image and can see the scene**; set named views, camera position, target, and lens length; save PNG to disk |
| **Files** | Save and export to `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg`. Import any Rhino-supported format with automatic display setup: DWG/DXF → Wireframe + black background + AutoCAD colours; FBX/OBJ/STL/STEP → Shaded mode. Zoom to extents applied on every import. |
| **Scripting** | Run arbitrary Rhino Python (RhinoScriptSyntax / RhinoCommon) or C# (Roslyn) directly. Failed plugin operations use Rhino undo records to restore document edits; external side effects are outside this recovery scope. Use `verified_functions` to suppress the API-hallucination warning. Execution gates (`RHINO_MCP_ENABLE_RHINOSCRIPT`, `RHINO_MCP_ENABLE_CSHARP`, `RHINO_MCP_ENABLE_RUN_COMMAND`) let operators disable these tools. |
| **AI Generation** | Generate 3D models from text or images via Hunyuan3D, import results into Rhino |
| **Asset Libraries** | Search and import Poly Haven textures/HDRIs, download Sketchfab models |
| **VisualARQ (BIM)** | Create walls, doors, windows, slabs, columns, stairs, railings, levels; query BIM properties; export IFC |
| **Lands Design** | Place plants and trees from species library, generate terrain from contours, create paths and water features, export plant schedules |
| **Multi-Rhino instances** | Discover all running Rhino processes with `get_rhino_instances` (slot registry), launch new ones with `launch_rhino`, and pass `rhino_id` to any tool to target a specific instance. |
| **Remote host** | Run Rhino on a separate workstation or VM — set `RHINO_MCP_BIND_HOST=0.0.0.0` **and** `RHINO_MCP_PLUGIN_SECRET` on the Rhino machine, the same secret on the client machine, and point the MCP client at its IP |
| **Telemetry** | Optional per-call usage log (JSONL on disk, opt-in, never leaves the machine) for debugging slow tools and measuring usage patterns |

---

## Urban Massing Workflow

Rhino MCP includes an agent-led urban massing workflow for early site studies. Claude can collect a short brief, choose a typology, open the matching Grasshopper definition under `grasshopper/urban/`, set named sliders, solve the definition, bake the generated geometry into Rhino, and read back planning metrics.

Supported massing typologies are `tower`, `podium_tower`, `courtyard`, `perimeter_block`, and `street_grid`. The workflow is driven by `urban_generate_massing`, which accepts the site origin, site dimensions, and typology-specific parameter overrides such as floor count, setbacks, footprint size, program mix, road width, or grid rotation. Results are baked to layers like `Urban::Massing::tower`.

### Core Urban Massing Tools

| Tool | Key Parameters | Description |
|---|---|---|
| `urban_generate_massing` | `typology`, `site_origin`, `site_width`, `site_depth`, `params`, `layer_prefix` | Generate parametric 3D massing by driving a Grasshopper definition. `params` is a dict of slider overrides (e.g. `{"floor_count": 20}`). Returns `{ok, typology, layer, gfa_m2, far, unit_count_est, open_space_pct}`. |
| `urban_get_metrics` | — | Read `gfa_m2`, `far`, `unit_count_est`, `open_space_pct` from the currently open Grasshopper massing definition. Returns zeros if none is open. |
| `urban_update_param` | `param_name`, `value` | Update a single Grasshopper slider and re-solve without regenerating the full massing. |
| `urban_capture_and_evaluate` | — | Capture the active viewport and return metrics together in one round-trip. |
| `urban_run_analysis` | `epw_path`, `analysis_type`, `period` | Open the Ladybug solar-analysis definition and return radiation/sun-hour values. |
| `urban_clear_massing` | `layer_prefix` | Delete all objects on `Urban::Massing::*` layers and close any open GH definition. |

### PRD-Facing Urban Tools

The orchestrator-level API uses product-level names and accepts GeoJSON-style `site_boundary` input, deriving site dimensions from its bbox/coordinates when not explicitly provided.

| Tool | Key Parameters | Description |
|---|---|---|
| `parse_urban_prompt` | `prompt` | Parse a natural-language brief into structured site + typology params. |
| `generate_site_layout` | `site_boundary`, `program_mix`, `constraints` | Generate a complete site layout from GeoJSON boundary and program requirements. |
| `generate_massing` | `site_boundary`, `typology`, `params` | High-level massing generation wrapper that accepts GeoJSON site input. |
| `calculate_urban_metrics` | — | Calculate and return comprehensive urban metrics for the current massing. |
| `optimize_plan` | `objectives`, `constraints`, `iterations` | Run iterative optimisation toward FAR, unit count, or open-space targets. |
| `render_urban_preview` | — | Capture and return a quick Rhino viewport preview of current massing. |
| `export_model` | `path`, `format` | Export the current massing to a file (3dm, obj, stl, etc.). |
| `save_project_version` | `project_name`, `version_name`, `notes` | Save a named snapshot of the current massing + metrics for comparison. |
| `create_urban_scheme` | `scheme_name`, `typology`, `site_boundary`, `params` | Create a complete named urban scheme in one call (layout + massing + metrics). |

Prerequisites are the plugin backend, Rhino with Grasshopper open, and the urban Grasshopper definitions present in `grasshopper/urban/`. Ladybug-based analysis additionally requires Ladybug Tools and local EPW weather files.

---

## Studio Pipeline

One call takes you from a site brief to a branded PDF report with AI renders.

### Workflow

```
Brief → urban_generate_design_language → urban_render_views → urban_export_report
           or run everything at once:
urban_run_studio_pipeline(project_name, scheme_name, brief, render_views, include_solar)
```

### Prerequisites

| Feature | Requirement |
|---|---|
| Design language | `ANTHROPIC_API_KEY` |
| AI renders | `FAL_KEY` (fal.ai account) |
| PDF export | `DOCRAPTOR_API_KEY` (optional — falls back to local HTML) |
| Cloud storage | `URBAN_AGENT_S3_BUCKET` + AWS credentials (optional — falls back to `~/.urbanagent/reports/`) |

All cloud services are optional. Without them, reports are saved locally and renders are skipped with raw Rhino captures used as fallback.

### Tools

| Tool | Description |
|---|---|
| `urban_generate_design_language` | Generate style name, materials, colour story, diffusion prompt from site brief |
| `urban_update_design_language` | Patch a single field (re-derives diffusion prompt on material/style changes) |
| `urban_get_design_language` | Read current session design language |
| `urban_render_views` | Capture Rhino viewports + AI-render via fal.ai FLUX.1 ControlNet |
| `urban_render_style_preview` | Quick text-to-image mood board preview (no massing needed) |
| `urban_get_renders` | Read all renders from current session |
| `urban_export_report` | Export branded PDF report with S3 share link |
| `urban_preview_report` | Render HTML preview (no PDF/S3, fast iteration) |
| `urban_list_reports` | List all reports exported this session |
| `urban_run_studio_pipeline` | Single-call orchestrator: runs all steps in sequence |
| `urban_pipeline_status` | Check running/completed pipeline status |
| `urban_list_pipeline_runs` | History of pipeline runs this session |

### Example conversation

```
User: Design a podium tower for a 100m×80m site in Shoreditch. FAR 3.5, 70% residential.

Claude: [calls urban_generate_massing + urban_generate_design_language]
        → "Contemporary Brick Residential" — warm brick, dark steel trim, planted podium
        [calls urban_render_views(["Perspective","Top","Front","Right"])]
        → 4 AI-rendered views
        [calls urban_export_report(project_name="Shoreditch", scheme_name="V1")]
        → https://s3.example.com/reports/Shoreditch/V1/1234567890.pdf
        "Report ready. Scheme shows 28,000m² GFA, FAR 3.5, ~280 units, 22% open space."
```

### Env var setup

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export FAL_KEY=...
export DOCRAPTOR_API_KEY=...
export URBAN_AGENT_S3_BUCKET=my-urbanagent-reports
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

---

## Architecture Overview

```
AI Client (Claude / Cursor / Codex)
       │  MCP (stdio)
       ▼
  Python MCP Server (rhmcp)      ← this repo, runs anywhere
       │  TCP JSON socket  :1999
       ▼
  rhino-mcp.rhp (plugin)         ← runs inside Rhino 7/8
       │
       ▼
  Rhino 3D + Grasshopper
```

The **Python MCP server** exposes all tools to the AI client via the Model Context Protocol over stdio. It connects to the **Rhino plugin** over a local TCP socket. All Rhino-side operations (including all Grasshopper canvas mutations) execute on Rhino's main UI thread via `RhinoApp.InvokeOnUiThread`, keeping the document consistent and undo-safe.

The Python server maintains a **persistent TCP connection** to the Rhino plugin (keep-alive enabled by default) so tool calls don't pay a fresh TCP handshake on every invocation. Disable with `RHINO_MCP_KEEPALIVE=0` if needed.

A `rhinocode` fallback path (Rhino 8.11+ only) is also available for most non-Grasshopper tools when the plugin is not loaded.

---

## Requirements

| Component | Minimum version |
|---|---|
| Rhino 3D | **Rhino 7** (Rhino 8 recommended; script components and Kangaroo require Rhino 8) |
| Python | 3.10 or later |
| uv | any recent version (`pip install uv`) |
| .NET SDK | 8.0+ (only needed if building the plugin from source) |

---

## Installation

### Upgrading from a Previous Version

> **Important:** Having two copies of the plugin installed at the same time causes a **port conflict** — both try to bind port 1999 on load, the second one fails silently, and Rhino gives no error. The result is that MCP commands either go to the wrong version or fail with `connection refused`, with no obvious indication of why.

#### How to tell if you have a conflict

Run `MCPStatus` in the Rhino command line. If it says the server is running but MCP calls still fail, or if you see unexpected tool behaviour after upgrading, a stale copy is almost certainly the cause.

You can also check what is loaded: in Rhino, go to **Tools → Options → Plug-ins** and search for "rhino-mcp". If two entries appear, or if the path shown is old, remove both and reinstall from scratch.

#### Step 1 — Remove ALL old copies

Check **both** install locations — you may have installed once via `.rhp` copy and once via Yak.

**macOS:**

```bash
# Manual .rhp install location
rm -f "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/rhino-mcp.rhp"

# Yak / PackageManager install location
rm -rf "$HOME/Library/Application Support/McNeel/Rhinoceros/packages/8.0/rhino-mcp"
```

> If the `rm` commands fail with "Operation not permitted" (macOS sandbox), open Finder, press `⌘⇧G`, paste the path, and delete the file/folder manually.

**Windows:**

```powershell
# Manual .rhp install location
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\8.0\Plug-ins\rhino-mcp.rhp" -ErrorAction SilentlyContinue

# Yak / PackageManager install location
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\packages\8.0\rhino-mcp" -Recurse -ErrorAction SilentlyContinue
```

> **Not sure which install method you used?** Remove both. If neither path exists, nothing happens.

#### Step 2 — Close Rhino completely

Do not just close the Rhino window — quit the process. On macOS: `⌘Q` or right-click the Dock icon → Quit. On Windows: close all Rhino windows, then check Task Manager to confirm `Rhino.exe` is gone. Rhino keeps plugins in memory until the process exits — a full quit is required.

#### Step 3 — Install the new version

Follow the [Install the Rhino Plugin](#1-install-the-rhino-plugin) instructions below using the latest `.rhp` or `.yak` from [GitHub Releases](https://github.com/hov172/rhino_mcp/releases).

#### Step 4 — Restart Rhino and verify

After restarting Rhino you should see `Rhino MCP listening on 127.0.0.1:1999` in the command history. If it doesn't appear automatically, type `MCPStart` manually.

Run `MCPStatus` — it should print the address and port. Run `ping` from the MCP client side (`uv run python -m rhmcp ping`) to confirm end-to-end connectivity.

If you still see a port error after doing all this, open **Tools → Options → Plug-ins**, search "rhino-mcp", and check the path. If it points to an old location you missed, delete that file and restart Rhino again.

---

### Quick install options

- **Rhino PackageManager (recommended, once published):** In Rhino: `_PackageManager` → search **rhino-mcp** → Install → Restart Rhino.
- **Local script (from this repo):** `./scripts/install-plugin-local.sh` (macOS) or `.\scripts\install-plugin-local.ps1` (Windows). Requires a built `.yak` file in `rhino_plugin/package/` — run `./scripts/package-plugin.sh` first if needed.
- **GitHub Releases:** Download the `.rhp` or `.yak` from the [GitHub Releases](https://github.com/hov172/rhino_mcp/releases) page and drag it onto Rhino's viewport, or install via `_PackageManager` → Install from File.

### 1. Install the Rhino Plugin (`rhino-mcp.rhp`)

The plugin is a `.rhp` file that runs a TCP socket server inside Rhino on port 1999. **It has no MCP protocol knowledge** — it only listens for commands from the Python server. There are three ways to install it.

#### Option A — Copy the pre-built `.rhp` directly (fastest)

On macOS, extract the plugin ZIP from the [latest release](https://github.com/hov172/rhino_mcp/releases/latest) and copy its assembly and dependencies into the bundle below. Quit Rhino before installation. Windows users can install the `.rhp` directly.

```bash
# macOS — user plug-ins folder (no admin rights needed)
mkdir -p "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp"
cp rhino-mcp.rhp *.json *.dll \
   "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/MacPlugIns/rhino-mcp.rhp/"
```

```powershell
# Windows — adjust Rhino version path as needed
Copy-Item rhino-mcp.rhp `
  "$env:APPDATA\McNeel\Rhinoceros\8.0\Plug-ins\"
```

Then restart Rhino. The plugin loads automatically on startup.

#### Option B — Install via Yak CLI

Download the `.yak` file from the [latest release](https://github.com/hov172/rhino_mcp/releases/latest), then run (replace the filename with the one you downloaded):

```bash
# macOS
"/Applications/Rhino 8.app/Contents/Resources/bin/yak" install --source ~/Downloads/rhino-mcp-*.yak
```

```powershell
# Windows
& "C:\Program Files\Rhino 8\System\yak.exe" install --source "$env:USERPROFILE\Downloads\rhino-mcp-*.yak"
```

Restart Rhino after the install completes.

#### Option C — Build from source

```bash
# Requires .NET 8 SDK
dotnet build -c Release rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj
```

The build output is placed at `rhino_plugin/RhinoMCPPlugin/bin/Release/net8.0/rhino-mcp.rhp` and is automatically copied to `/Applications/Rhino 8.app/Contents/PlugIns/` on macOS by the PostBuild step.

---

### 2. Install the Python MCP Server (this repo)

> **This is not a Rhino plugin.** It is a standalone Python process that your AI client (Claude Desktop, Cursor, etc.) launches or connects to. It translates MCP tool calls into socket commands and sends them to the Rhino plugin on port 1999.

```bash
# Clone the repo
git clone https://github.com/hov172/rhino_mcp.git
cd rhino_mcp

# Install all dependencies (recommended)
uv sync

# Or with pip
pip install -e .
```

Verify the install:

```bash
uv run python -m rhmcp --help
```

---

### 3. Configure API Keys (Studio Pipeline)

The Studio Pipeline features require API keys for three external services. All are optional — the pipeline degrades gracefully without them — but you need at least `ANTHROPIC_API_KEY` to generate design language.

| Key | Where to get it | Required for |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Design language generation (`urban_generate_design_language`) |
| `FAL_KEY` | [fal.ai/dashboard](https://fal.ai/dashboard) | AI viewport renders (`urban_render_views`, `urban_render_style_preview`) |
| `DOCRAPTOR_API_KEY` | [docraptor.com](https://docraptor.com/) | PDF report export (optional — falls back to local HTML) |
| `URBAN_AGENT_S3_BUCKET` + AWS credentials | AWS Console | Cloud storage for report share links (optional — falls back to `~/.urbanagent/reports/`) |

**macOS / Linux — add to `~/.zshrc` or `~/.bashrc` for persistence:**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export FAL_KEY="..."
export DOCRAPTOR_API_KEY="..."          # optional
export URBAN_AGENT_S3_BUCKET="my-bucket"  # optional
export AWS_ACCESS_KEY_ID="..."           # optional
export AWS_SECRET_ACCESS_KEY="..."       # optional
```

**Windows — set permanently via PowerShell:**

```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
[System.Environment]::SetEnvironmentVariable("FAL_KEY", "...", "User")
```

**Or pass them directly in your AI client config** (see [Connecting AI Clients](#connecting-ai-clients) below — all client configs include an `env` block for this).

> **Without any API keys:** The base Rhino tools (geometry, Grasshopper, rendering, BIM) work with no keys at all. Only the Studio Pipeline steps (design language, AI renders, PDF export) require external services.

---

### Docker Quick-Start (alternative to steps 2 & 3)

Prepare the certificates and shared plugin secret described in [secure operation](docs/secure-operation.md#tls). Set `RHINO_MCP_CERT_DIR` to that local certificate directory. The HTTP certificate must cover `localhost`; the plugin certificate must cover `host.docker.internal`.

Docker bundles the Python server and all dependencies into a self-contained image. You still need the Rhino plugin (step 1) — it runs inside Rhino on your machine and cannot be containerized.

**Build the image:**

```bash
docker build -t rhino-mcp .
```

**Run it:**

```bash
docker run -d \
  -p 8000:8000 \
  -v "$RHINO_MCP_CERT_DIR:/certs:ro" \
  -e RHINO_MCP_HTTP_TLS_CERT=/certs/http-server.pem \
  -e RHINO_MCP_HTTP_TLS_KEY=/certs/http-server-key.pem \
  -e RHINO_MCP_HTTP_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_SECRET="$RHINO_MCP_PLUGIN_SECRET" \
  -e RHINO_MCP_AUTH_TOKEN="replace-with-a-unique-random-token-at-least-32-chars" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e FAL_KEY="..." \
  -e DOCRAPTOR_API_KEY="..." \
  -e URBAN_AGENT_S3_BUCKET="my-bucket" \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  --name rhino-mcp \
  rhino-mcp
```

The container defaults to `RHINO_MCP_HOST=host.docker.internal`, which on **macOS and Windows** resolves automatically to the Docker host where Rhino is running. **Linux** requires one extra flag:

```bash
docker run -d -p 8000:8000 --add-host=host.docker.internal:host-gateway \
  -v "$RHINO_MCP_CERT_DIR:/certs:ro" \
  -e RHINO_MCP_HTTP_TLS_CERT=/certs/http-server.pem \
  -e RHINO_MCP_HTTP_TLS_KEY=/certs/http-server-key.pem \
  -e RHINO_MCP_HTTP_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_TLS_CA=/certs/ca.pem \
  -e RHINO_MCP_PLUGIN_SECRET="$RHINO_MCP_PLUGIN_SECRET" \
  -e RHINO_MCP_AUTH_TOKEN="replace-with-a-unique-random-token-at-least-32-chars" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  rhino-mcp
```

Once running, point your AI client at `https://localhost:8000/` — see [Docker / HTTP Transport](#docker--http-transport) below.

**Both paths work independently.** Existing manual stdio setups are unaffected by the Docker option.

---

### macOS Installer (.pkg) (alternative to steps 1–3)

The `.pkg` installer replaces steps 1, 2, and 3 entirely on macOS. See [Path C — macOS Installer (.pkg)](#path-c--macos-installer-pkg) for requirements and steps.

**What gets installed and where:**

| Path | Contents |
|---|---|
| `/Users/Shared/rhino_mcp/python-arm64/` or `python-x86_64/` | Bundled Python 3.13 runtime (matched to machine arch) |
| `/Users/Shared/rhino_mcp/.venv/` | Virtual environment with `rhmcp` installed (symlink to arch-specific venv) |
| `/Users/Shared/rhino_mcp/plugin/rhino-mcp.rhp` | Rhino plugin source used during per-user configuration |
| `/Users/Shared/rhino_mcp/VERSION` | Installed version string |
| `/usr/local/bin/rhino-mcp-configure` | Per-user configuration script (re-run manually if needed) |
| `~/Library/Application Support/McNeel/Rhinoceros/<ver>/MacPlugIns/rhino-mcp.rhp/` | Plugin bundle and dependencies for installed Rhino 8/9 |

**Re-running configuration manually:**

If auto-configuration was skipped (headless install, new user account), run:

```bash
/usr/local/bin/rhino-mcp-configure
```

This installs the plugin for all detected Rhino versions and writes the `rhino` MCP server entry into Claude Desktop and Claude Code configs.

---

## Starting the Service

### Step 1 — Start Rhino and activate the plugin

1. **Open Rhino 3D** (version 7 or 8).
2. The plugin starts its socket server automatically on load. You should see this in the Rhino command history:
   ```
   Rhino MCP listening on 127.0.0.1:1999
   ```

3. **If the auto-start message doesn't appear** (e.g. port conflict on first launch), run `MCPStart` manually:

   ```
   MCPStart
   ```

   Use `MCPStatus` at any time to confirm the server is running. If you see `already listening`, the auto-start succeeded and no further action is needed. Type `MCPHelp` to open the full documentation in your browser.

4. *(Optional — for Grasshopper tools)* Open Grasshopper:

   ```
   Grasshopper
   ```

   Grasshopper must be open at least once before GH tools will work. After the first open, `gh_new_definition` will open it automatically on demand.

### Rhino plugin commands

| Command | Description |
|---|---|
| `MCPStart` | Start the socket server manually (fallback if auto-start fails) |
| `MCPStop` | Stop the socket server |
| `MCPStatus` | Print the current server status and bind address |
| `MCPHelp` | Open the full documentation in your browser |

---

### Step 2 — Start the MCP server

The MCP server communicates over **stdio** with the AI client. You do not run it manually in most setups — the client starts it automatically. But you can verify it works:

```bash
# From the repo root
uv run python -m rhmcp
```

To point it at a non-default Rhino host/port:

```bash
RHINO_MCP_HOST=127.0.0.1 RHINO_MCP_PORT=1999 uv run python -m rhmcp
```

---

## Connecting AI Clients

> **Do I need API keys?**
>
> There are two completely separate things that look similar but are not the same:
>
> - **Your AI account login** (Claude account, ChatGPT account, OpenAI key for Codex) — this powers the AI conversation. If you are logged into the desktop app, this is already handled. You do not put it in the MCP config.
>
> - **Studio Pipeline API keys** (`ANTHROPIC_API_KEY`, `FAL_KEY`, etc.) — these are used by the **MCP server process itself** to call external services. Your app login is not shared with the server process — it needs its own credentials for those services.
>
> **If you only use Rhino tools** (geometry, Grasshopper, layers, materials, rendering, BIM) you need **no API keys at all** — just the three connection variables:
> ```json
> "env": { "RHINO_MCP_BACKEND": "plugin", "RHINO_MCP_HOST": "127.0.0.1", "RHINO_MCP_PORT": "1999" }
> ```
>
> **Add a key only when you need that specific feature:**
>
> | Key | Get it from | Unlocks |
> |---|---|---|
> | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | `urban_generate_design_language` — AI design language generation |
> | `FAL_KEY` | [fal.ai/dashboard](https://fal.ai/dashboard) | `urban_render_views`, `urban_render_style_preview` — AI viewport renders |
> | `DOCRAPTOR_API_KEY` | [docraptor.com](https://docraptor.com/) | `urban_export_report` — PDF conversion (falls back to local HTML without it) |
> | `URBAN_AGENT_S3_BUCKET` + AWS credentials | AWS Console | `urban_export_report` — cloud share links (falls back to `~/.urbanagent/reports/` without it) |
>
> All Studio Pipeline keys are optional — the pipeline degrades gracefully. Without any keys the report still exports as a local HTML file.

---

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "...",
        "URBAN_AGENT_S3_BUCKET": "my-bucket",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

Replace `/path/to/rhino-mcp` with the absolute path to the cloned repo. Omit any Studio Pipeline keys you don't need — the pipeline degrades gracefully. Restart Claude Desktop after editing.

---

### Claude Code (CLI)

Add to your project's `.mcp.json` or `~/.claude/mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "DYLD_LIBRARY_PATH": "/opt/homebrew/lib",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "...",
        "URBAN_AGENT_S3_BUCKET": "my-bucket",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

> **`DYLD_LIBRARY_PATH`** is required on macOS for SVG-to-PNG rendering (`read_svg`) when running the server **without Docker**. It points to Homebrew's library directory where libcairo lives. Install cairo first if needed: `brew install cairo`. On Linux or Windows omit this variable. **Docker users:** libcairo is bundled in the image — no Homebrew or `DYLD_LIBRARY_PATH` needed.

Or start Claude Code with the server inline (API keys picked up from your shell environment):

```bash
claude --mcp-server "rhino:uv run --directory /path/to/rhino-mcp python -m rhmcp"
```

---

### ChatGPT Desktop

Edit `~/Library/Application Support/ChatGPT/mcp.json` (macOS) or `%APPDATA%\ChatGPT\mcp.json` (Windows). Create the file if it doesn't exist:

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "...",
        "URBAN_AGENT_S3_BUCKET": "my-bucket",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

Replace `/path/to/rhino-mcp` with the absolute path to the cloned repo. Restart ChatGPT Desktop after saving.

> **Note:** Requires ChatGPT Desktop 1.2025.x or newer with MCP enabled.

---

### Cursor

In Cursor Settings → MCP → Add Server:

```json
{
  "rhino": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
    "env": {
      "RHINO_MCP_BACKEND": "plugin",
      "RHINO_MCP_HOST": "127.0.0.1",
      "RHINO_MCP_PORT": "1999",
      "ANTHROPIC_API_KEY": "sk-ant-...",
      "FAL_KEY": "...",
      "DOCRAPTOR_API_KEY": "...",
      "URBAN_AGENT_S3_BUCKET": "my-bucket",
      "AWS_ACCESS_KEY_ID": "...",
      "AWS_SECRET_ACCESS_KEY": "..."
    }
  }
}
```

---

### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json` (macOS/Linux) or `%APPDATA%\Codeium\windsurf\mcp_config.json` (Windows):

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "...",
        "URBAN_AGENT_S3_BUCKET": "my-bucket",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

Or via Windsurf Settings → MCP Servers → Add. Restart Windsurf after saving.

---

### GitHub Copilot (VS Code)

Add to your workspace `.vscode/mcp.json` (per-project) or user `settings.json` (global):

**`.vscode/mcp.json`** (recommended — commit alongside your project):

```json
{
  "servers": {
    "rhino": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}",
        "FAL_KEY": "${env:FAL_KEY}"
      }
    }
  }
}
```

> VS Code MCP supports `${env:VAR}` substitution so API keys are read from your shell environment rather than hardcoded.

**Global** — add to `settings.json` under `"github.copilot.mcp"`:

```json
"github.copilot.mcp": {
  "servers": {
    "rhino": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999"
      }
    }
  }
}
```

---

### Codex CLI

Add to `~/.codex/config.toml` (create the file if it doesn't exist):

```toml
[mcp_servers.rhino]
command = "uv"
args = ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"]

[mcp_servers.rhino.env]
RHINO_MCP_BACKEND = "plugin"
RHINO_MCP_HOST = "127.0.0.1"
RHINO_MCP_PORT = "1999"
ANTHROPIC_API_KEY = "sk-ant-..."
FAL_KEY = "..."
```

Replace `/path/to/rhino-mcp` with the absolute path to the cloned repo. Codex reads this config automatically on start.

---

### Gemini CLI

Add to `~/.gemini/settings.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999",
        "FAL_KEY": "...",
        "DOCRAPTOR_API_KEY": "...",
        "URBAN_AGENT_S3_BUCKET": "my-bucket",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

Replace `/path/to/rhino-mcp` with the absolute path to the cloned repo. Restart Gemini CLI after saving.

---

### Docker / HTTP Transport

Prepare the certificates and shared plugin secret described in [secure operation](docs/secure-operation.md#tls). Set `RHINO_MCP_CERT_DIR` to that local certificate directory. The HTTP certificate must cover `localhost`; the plugin certificate must cover `host.docker.internal`.

When the server is running in Docker (or started manually with `--transport http`), AI clients connect to a URL instead of spawning a process. API keys are set on the container at `docker run` time — no `env` block needed in the client config.

Every request (except `GET /health`) must carry `Authorization: Bearer <token>`. Set a stable token with `RHINO_MCP_AUTH_TOKEN` when starting the container/server; otherwise a random one is generated and printed to stderr on each start (`docker logs rhino-mcp`).

**Claude Desktop** — edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rhino": {
      "url": "https://localhost:8000/",
      "headers": {
        "Authorization": "Bearer <your RHINO_MCP_AUTH_TOKEN>"
      }
    }
  }
}
```

**Claude Code (CLI):**

```bash
claude --mcp-server "rhino:https://localhost:8000/"
```

**Cursor** — Settings → MCP → Add Server, type `http`, URL `https://localhost:8000/`.

**Windsurf** — add a server with type `sse` and URL `https://localhost:8000/`.

**GitHub Copilot (VS Code)** — in `.vscode/mcp.json` use `"type": "http"` and `"url": "https://localhost:8000/"`.

**Codex CLI:**

```bash
codex --mcp-server "https://localhost:8000/"
```

> The manual stdio setup and Docker/HTTP setup can coexist. Point different clients at whichever they prefer — the Rhino plugin on port 1999 handles both.

---

## Backend Selection

The MCP server supports three backend modes:

| Mode | Description | Use case |
|---|---|---|
| `plugin` | TCP socket to rhino-mcp.rhp | **Recommended.** Full feature set including Grasshopper. Works with Rhino 7 and 8. |
| `rhinocode` | Rhino 8.11+ official CLI | No plugin required. Does not support Grasshopper. Slower for complex operations. |
| `auto` | Try plugin first, fall back to rhinocode | Good default when plugin availability is uncertain. |

Set the backend via environment variable:

```bash
export RHINO_MCP_BACKEND=plugin    # or rhinocode, auto
```

Use `get_rhino_backend_status` from any AI client to check which backends are currently reachable.

Backend selection rule of thumb:

| Need | Backend |
|---|---|
| Grasshopper, GH2, plugin commands, or best feature coverage | `plugin` |
| Rhino 8.11+ script execution without installing the plugin | `rhinocode` |
| Mixed environments where the plugin may not always be loaded | `auto` |

When debugging connection failures, set `RHINO_MCP_BACKEND=plugin` temporarily. That prevents silent fallback to `rhinocode` and returns the socket error directly.

### Session & Instance Management

| Tool | Description |
|---|---|
| `get_rhino_instances` | Discover all running Rhino MCP instances via the slot registry. Returns a list of `{id, host, port, version, rhino_version, pid, started_at}`. Pass the returned `id` as `rhino_id` to any other tool to target that instance. Works with the C# `SlotAnnouncer` — requires the plugin to be loaded in each Rhino process. |
| `launch_rhino` | Launch a new Rhino process and wait for it to announce its slot (up to 60 s). Finds the Rhino executable via `RHINO_MCP_RHINO_PATH` or standard install paths. Returns `{ok, id, pid}` of the new instance. |
| `get_rhinocode_instances` | List all running Rhino processes via the rhinocode CLI. Returns `id`, `name`, and `version`. Use when the plugin is not loaded and you only need the rhinocode backend. |
| `get_rhino_backend_status` | Report which backends are currently reachable: plugin socket (port 1999) and rhinocode CLI. Shows the selected backend mode and any connection errors. |
| `health_check` | Ping the Rhino plugin socket and report `ok`, `latency_ms`, and the Rhino version. Call it first in any session to confirm Rhino and the plugin are up. |
| `get_rhino_commands` | List all available Rhino command names, optionally filtered by substring (e.g. `filter="circle"`). `loaded_only=true` (default) restricts to currently loaded plugins; set `false` to include unloaded plugins. Use this before `run_rhino_command` to discover exact spellings. |
| `list_rhino_plugins` | List plugins loaded in the current Rhino session, routed through the active backend. |
| `load_rhino_plugin` | Load a Rhino plugin by GUID or file path. Use when a plugin is installed but not yet loaded in the current Rhino session. |

---

## Environment Variables

### Python MCP Server

| Variable | Default | Description |
|---|---|---|
| `RHINO_MCP_BACKEND` | `auto` | Backend mode: `plugin`, `rhinocode`, or `auto` |
| `ANTHROPIC_API_KEY` | *(unset)* | Required for `urban_generate_design_language` and the studio pipeline design step |
| `FAL_KEY` | *(unset)* | Required for `urban_render_views` and `urban_render_style_preview` (fal.ai account) |
| `DOCRAPTOR_API_KEY` | *(unset)* | Optional — enables PDF conversion in `urban_export_report`. Falls back to local HTML when unset. |
| `URBAN_AGENT_S3_BUCKET` | *(unset)* | Optional — S3 bucket name for report uploads. Falls back to `~/.urbanagent/reports/` when unset. |
| `AWS_ACCESS_KEY_ID` | *(unset)* | Optional — AWS credentials for S3 report uploads. |
| `AWS_SECRET_ACCESS_KEY` | *(unset)* | Optional — AWS credentials for S3 report uploads. |
| `RHINO_MCP_HOST` | `127.0.0.1` | IP/hostname of the machine running Rhino (used by the Python side to connect) |
| `RHINO_MCP_PORT` | `1999` | Plugin socket port |
| `RHINO_MCP_SOCKET_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `RHINO_MCP_SOCKET_RETRIES` | `2` | Extra retry attempts on socket connection failure (total = retries + 1) |
| `RHINOCODE` | *(auto-detected)* | Path to rhinocode binary if not on `PATH` |
| `RHINO_MCP_TELEMETRY` | *(unset)* | Set to `1`, `true`, or `yes` to enable usage telemetry |
| `RHINO_MCP_TELEMETRY_LOG` | `~/.rhino_mcp_telemetry.jsonl` | Path for the telemetry log file (JSONL format) |
| `RHINO_MCP_READ_ROOTS` | `~` (home dir) | Colon-separated paths `read_*` tools may access. Default restricts reads to home directory. |
| `RHINO_MCP_RATE_LIMIT_RPM` | `120` | HTTP transport: maximum requests per minute per authenticated identity; `0` disables, negative values are rejected. |
| `RHINO_MCP_USE_SLOT_REGISTRY` | *(unset)* | Set to `1` to always route `plugin_result()` via the slot registry (auto-discover Rhino instances). Default: off (uses `RHINO_MCP_HOST`/`RHINO_MCP_PORT` directly). |
| `RHINO_MCP_RHINO_PATH` | *(auto-detected)* | Override path to the Rhino executable used by `launch_rhino`. Default: searches standard install locations. |
| `RHMCP_PROFILE` | `full` | Tool profile to load at startup: `core`, `grasshopper`, `rendering`, `urban`, `bim`, or `full`. Equivalent to `--profile` CLI flag. See [Tool Profiles](#tool-profiles). |
| `RHMCP_COMPACT` | `1` | Compact mode enabled by default. Set to `0` to load all schemas upfront. See [Compact Mode](#compact-mode). |
| `RHINO_MCP_KEEPALIVE` | `1` | Reuse a single persistent TCP connection to the Rhino plugin. Set to `0` to open a new connection per call (slower, useful for debugging). |
| `RHINO_MCP_ENABLE_RHINOSCRIPT` | `1` | Set to `0` to block Python execution, including built-in script-backed operations and GH Python script creation. Set in both MCP and Rhino environments. |
| `RHINO_MCP_ENABLE_CSHARP` | `1` | Set to `0` to block C# execution and GH C# script creation. Set in both MCP and Rhino environments. |
| `RHINO_MCP_ENABLE_RUN_COMMAND` | `1` | Set to `0` to block command macros at backend and plugin dispatch. Set in both MCP and Rhino environments. |
| `RHINO_MCP_ALLOW_REMOTE` | `0` | Set to `1` to allow the Python server to connect to a non-loopback Rhino host (required when `RHINO_MCP_HOST` is a remote address or `host.docker.internal`). See [Remote Host Support](#remote-host-support). |
| `RHINO_MCP_AUTH_TOKEN` | *(unset)* | Owner bearer token of at least 32 characters for HTTP. Ignored when `RHINO_MCP_AUTH_CONFIG` is set. When set, clients authenticate with `Authorization: Bearer <token>` and the token survives restarts — set this for Docker / Cloud Run deployments. Unset = a random token is generated at startup and printed to stderr. |

### Remote transport and workflow settings

See [secure operation](docs/secure-operation.md) for complete configuration examples.

| Variable | Default | Description |
|---|---|---|
| `RHINO_MCP_AUTH_CONFIG` | *(unset)* | JSON file with identity tokens and tool/project/instance grants; overrides the owner token. |
| `RHINO_MCP_HTTP_TLS_CERT` / `RHINO_MCP_HTTP_TLS_KEY` | *(unset)* | PEM certificate and private key, required for non-loopback HTTP binding. |
| `RHINO_MCP_HTTP_ALLOWED_HOSTS` | *(loopback hosts)* | Comma-separated allowed hostnames, including port patterns such as `rhino.example.internal:*`. |
| `RHINO_MCP_HTTP_ALLOWED_ORIGINS` | *(loopback origins)* | Comma-separated allowed browser origins. |
| `RHINO_MCP_HTTP_TLS_CA` | *(HTTP certificate)* | Trust file used by the Docker health check. |
| `RHINO_MCP_HTTP_TLS_SERVER_NAME` | `localhost` | Certificate hostname used by the Docker health check. |
| `RHINO_MCP_PLUGIN_TLS` | `0` | Set to `1` for remote plugin connections; also requires `RHINO_MCP_ALLOW_REMOTE=1`. |
| `RHINO_MCP_PLUGIN_TLS_CA` | *(system trust)* | PEM CA used to verify the plugin certificate and hostname. |
| `RHINO_MCP_GH_DIR` | *(bundled definitions)* | Urban definition directory as seen by Rhino; configure when MCP runs on another host/container. |
| `RHINO_MCP_REPORT_DIR` | `~/.urbanagent/reports` | Local report root; artifacts use separate scope namespaces and unique names. |

### Rhino Plugin (C# side)

| Variable | Default | Description |
|---|---|---|
| `RHINO_MCP_BIND_HOST` | `127.0.0.1` | IP address the Rhino plugin binds its TCP listener to. Set to `0.0.0.0` to accept connections from any network interface (required for remote AI clients). Must be set in Rhino's environment before `MCPStart` is run. |
| `RHINO_MCP_PLUGIN_SECRET` | *(unset)* | Pre-shared key required from the Python server on every connection. **Required for network (non-loopback) binding** — since v0.16.0 the plugin refuses to start listening on a non-loopback address without it. Set the same value on both machines. Unset = no authentication (loopback-only binding still works). |
| `RHINO_MCP_PLUGIN_TLS_CERT` | *(unset)* | PFX certificate with private key; required for non-loopback binding since 0.17.0. |
| `RHINO_MCP_PLUGIN_TLS_PASSWORD` | *(unset)* | Password for the PFX file. |

---

## Tool Profiles

Profiles let you control which tool modules are loaded at startup. Use a narrower profile to reduce context size when you don't need the full tool set.

| Profile | Tools | Includes |
|---------|-------|---------|
| `full` *(default)* | 358 | Everything |
| `core` | 194 | Geometry, layers, transforms, curves, surfaces, meshes, materials, export, annotations, document |
| `grasshopper` | 277 | `core` + all Grasshopper modules (GH1, GH2, Pufferfish, Weaverbird, LunchBox, Kangaroo, Ladybug…) |
| `rendering` | 225 | `core` + V-Ray, Enscape, PBR materials, asset libraries |
| `urban` | 226 | `core` + urban design, massing, studio pipeline, AI generation |
| `bim` | 212 | `core` + VisualARQ, Lands Design |

Regenerate the profile counts with:

```bash
uv run python - <<'PY'
from rhmcp import _resolve_profile
from rhmcp.tools_helpers.compact_registry import CompactRegistry
import yaml

with open("src/rhmcp/data/profiles.yml") as f:
    profiles = yaml.safe_load(f)

for name in ["full", "core", "grasshopper", "rendering", "urban", "bim"]:
    registry = CompactRegistry()
    registry.load_from_modules(_resolve_profile(name, profiles))
    print(name, len(registry._tools))
PY
```

**CLI flag:**
```bash
rhino-mcp --profile core
rhino-mcp --profile grasshopper
```

**Environment variable** (useful in Claude Desktop config):
```bash
RHMCP_PROFILE=core
```

**Claude Desktop example** — add `"--profile", "core"` to `args`:
```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp", "--profile", "core"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "127.0.0.1",
        "RHINO_MCP_PORT": "1999"
      }
    }
  }
}
```

The `core` profile covers standard Rhino modeling — geometry creation, boolean ops, curves, surfaces, meshes, layers, materials, transforms, export, and document tools. The other profiles extend `core` with their respective plugin tools.

---

## Compact Mode

Compact mode loads Python modules at startup and exposes their schemas on demand.
Discovery includes module categories and underlying safety annotations; it also
filters tools by the authenticated identity’s grants.

Compact mode registers 3 meta-tools instead of full schemas, reducing the per-request token cost to ~1.5k regardless of how many tools are available.

| Tool | Description |
|------|-------------|
| `list_rhino_tools` | Returns all available tools with one-line descriptions. Accepts optional `category` substring filter. |
| `describe_rhino_tool` | Returns the full description and input schema for a named tool. |
| `call_rhino_tool` | Calls any tool by name with a `arguments` dict. |

Compact mode is **on by default**. To disable and load all schemas upfront:

```bash
rhino-mcp --no-compact
RHMCP_COMPACT=0 rhino-mcp
```

**Works alongside `--profile`** — the registry behind the meta-tools is filtered to the active profile:
```bash
rhino-mcp --profile core   # compact + core (default compact applies)
rhino-mcp --no-compact --profile core  # full schemas, core tools only
```

| Mode | ~Tokens |
|------|---------|
| `full` | ~52k |
| `--profile core` | ~28k |
| `--compact` | ~1.5k |
| `--compact --profile core` | ~1.5k |

---

## Remote Host Support

Remote HTTP and Rhino plugin connections require TLS. The plugin also requires a
shared secret. Configure certificates, client trust, and identity grants using
[Secure operation](docs/secure-operation.md#tls). This applies to Docker as well
as separate machines; earlier plaintext network examples require these settings.

HTTP supports separate authenticated identities with explicit tool, project, and
Rhino-instance grants. All tools accept `project_id` and `rhino_id`; workflow
state is isolated by identity/project/instance, with mutations serialized per
instance within the server process. See [identity configuration](docs/secure-operation.md#http-identities-and-grants).

---

## Telemetry

Telemetry is **opt-in** and **disabled by default**. No data leaves your machine — events are written to a local JSONL file only. When disabled, no events are written. Both compact and direct mode record the underlying tool name when enabled. Arguments and exception messages are omitted.

### Enable / disable

```bash
# Enable
export RHINO_MCP_TELEMETRY=1        # also accepts: true, yes

# Disable (unset or set to anything else)
unset RHINO_MCP_TELEMETRY
```

The env var is read once at server startup. Changing it while the MCP server is running has no effect — restart the server to pick up the new value.

### Log file location

```bash
# Default
~/.rhino_mcp_telemetry.jsonl

# Override
export RHINO_MCP_TELEMETRY_LOG=/path/to/rhino_mcp_usage.jsonl
```

The parent directory is created automatically if it does not exist.

### Event format

Each line is a complete, self-contained JSON object:

```json
{"ts":"2026-09-06T18:30:00+00:00","tool":"capture_rhino_view","ms":142,"actor":"local","project":"default","ok":true,"error":null}
{"ts":"2026-09-06T18:30:08+00:00","tool":"urban_get_metrics","ms":87,"actor":"designer-a","project":"courtyard-study","ok":false,"error":"METRICS_UNAVAILABLE"}
```

| Field | Type | Description |
|---|---|---|
| `ts` | ISO-8601 UTC string | Timestamp when the event is recorded |
| `tool` | string | Underlying MCP tool name exactly as registered |
| `actor` | string | HTTP identity ID, or `local` for stdio |
| `project` | string | Requested `project_id`, or `default` when omitted |
| `ms` | integer | Wall-clock duration in milliseconds (includes Rhino round-trip time for plugin-backend calls) |
| `ok` | boolean | `false` for exceptions or dictionary results with `ok: false`; `true` otherwise |
| `error` | string \| null | Exception class or result error code when available; no exception message |

> `ms` measures time inside the runtime tool wrapper; it excludes client/network transit to the MCP server. For plugin-backend tools this includes the full TCP round-trip to Rhino plus any Rhino-side computation. It is a useful proxy for "how long did the user wait."

### Querying the log

```bash
# Tail live events as they come in
tail -f ~/.rhino_mcp_telemetry.jsonl | jq .

# All failed calls today
jq 'select(.ok == false)' ~/.rhino_mcp_telemetry.jsonl

# Average duration by tool (requires jq 1.6+)
jq -s 'group_by(.tool)[] | {tool: .[0].tool, avg_ms: (map(.ms) | add / length)}' \
   ~/.rhino_mcp_telemetry.jsonl

# Top 10 slowest calls
jq -s 'sort_by(-.ms) | .[:10] | .[] | {tool, ms, ok}' \
   ~/.rhino_mcp_telemetry.jsonl

# Count calls per tool, descending
jq -s 'group_by(.tool)[] | {tool: .[0].tool, count: length}' \
   ~/.rhino_mcp_telemetry.jsonl | jq -s 'sort_by(-.count)[]'

# All errors in the last 100 lines
tail -100 ~/.rhino_mcp_telemetry.jsonl | jq 'select(.ok == false) | {tool, ms, error}'
```

### Implementation notes

The interceptor is installed at the `ToolManager.call_tool` level inside FastMCP, so it wraps every tool regardless of which module it lives in — no per-tool changes needed. Any I/O failure in the log-write path (permission error, disk full, etc.) is caught and silently discarded so a broken log never surfaces to the user or the AI client.

---

## Third-Party Plugin Support

Rhino MCP can install, check, and introspect third-party Grasshopper and Rhino plugins. The `install_plugin` tool supports three methods depending on the plugin:

### Automatic Installation via Yak

The following plugins are in Rhino's official Yak package registry and can be installed silently with no UI interaction:

| Plugin | Yak package name | Notes |
|---|---|---|
| Pufferfish | `pufferfish` | Geometry morphing and tweening |
| Elefront | `elefront` | Object attribute management |
| Weaverbird | `weaverbird` | Mesh subdivision |
| Anemone | `anemone` | Iterative loops |
| Human | `human` | GH↔Rhino attribute bridge |
| LunchBox | `lunchbox` | Parametric paneling |

When the AI client calls `install_plugin(plugin_name="Pufferfish")`, the server locates the Yak CLI at the standard Rhino installation path, calls `yak install pufferfish`, and returns status. Rhino must be restarted after a Yak install for the plugin to activate.

> **Known Yak behaviour:** Yak prompts interactively if the package is already installed. The server detects this case and returns a clear message rather than hanging.

**Yak CLI locations searched:**

| Platform | Path |
|---|---|
| macOS (Rhino 8) | `/Applications/Rhino 8.app/Contents/Resources/bin/yak` |
| macOS (Rhino 7) | `/Applications/Rhino 7.app/Contents/Resources/bin/yak` |
| Windows (Rhino 8) | `C:\Program Files\Rhino 8\System\yak.exe` |
| Windows (Rhino 7) | `C:\Program Files\Rhino 7\System\yak.exe` |

If Yak is not found at those locations, the tool returns instructions to use `_PackageManager` manually.

### Manual Installation

Plugins not available in Yak require a manual install step. The tool returns actionable instructions with the exact steps and a download URL:

| Plugin | Install method | Download |
|---|---|---|
| Ladybug Tools | Rhino Package Manager UI | [food4rhino.com](https://www.food4rhino.com/en/app/ladybug-tools) |
| Honeybee | Rhino Package Manager UI | [food4rhino.com](https://www.food4rhino.com/en/app/ladybug-tools) |
| Kangaroo 2 | Built into Rhino 8; open Grasshopper | [food4rhino.com](https://www.food4rhino.com/en/app/kangaroo-physics) |
| VisualARQ | Vendor installer (license required) | [visualarq.com](https://www.visualarq.com/download/) |
| Lands Design | Vendor installer (license required) | [lands-design.com](https://www.lands-design.com/download/) |

Vendor-only paid plugins (V-Ray, Enscape) return a download URL with a message explaining that a license and vendor installer are required.

### File-based Installation

If you have already downloaded a plugin file, pass the `file_path` parameter to `install_plugin`:

| File type | Behaviour |
|---|---|
| `.gha` | Copied directly into the Grasshopper Libraries folder. Restart Grasshopper to activate. |
| `.rhp` | Loaded immediately via Rhino's `_LoadPlugin` command. No restart required. |
| `.rhi` | Opened with the Rhino Installer (OS-native handler). Follow the installer prompts, then restart Rhino. |

**Example:**
```
install_plugin(plugin_name="MyPlugin", file_path="/Downloads/MyPlugin.gha")
```

**Grasshopper Libraries folder locations:**

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/Grasshopper (b45a29b1-4343-4035-989e-044e8580d9cf)/Libraries/` |
| Windows | `%APPDATA%\Grasshopper\Libraries\` |

> Note: Yak-installed packages go to a separate location (`~/Library/Application Support/McNeel/Rhinoceros/packages/8.0/` on macOS) and are not visible in the Libraries folder. This is expected.

### Checking Plugin Status

Before running plugin-specific tools (V-Ray, Enscape, VisualARQ, Lands Design, and all GH plugin tools), each module checks that the required plugin is loaded. If it is not, the tool returns `{"success": false, "message": "..."}` with install instructions rather than raising an unhandled error.

You can also call `check_plugin_loaded(plugin_name="V-Ray")` directly to test whether a plugin is active before attempting to use it.

---

## All 358 Tools

---

### Plugin Management

Tools for discovering, installing, and running commands from any Rhino or Grasshopper plugin. These tools work with both first-party and third-party plugins and do not require the plugin-specific modules below.

| Tool | Description |
|---|---|
| `list_installed_plugins` | Return all installed Rhino plugins with their name, GUID, loaded state, and file path. Useful for discovering what is available before calling plugin-specific tools. |
| `get_plugin_commands` | List all Rhino commands registered by a specific plugin. Provide `plugin_name` (partial, case-insensitive) or `plugin_id` (GUID). Returns the full command list with command names. |
| `run_plugin_command` | Run any Rhino command string, including commands from third-party plugins. `options_string` is appended after the command name (e.g. `"_Enter"` to confirm prompts). |
| `check_plugin_loaded` | Check whether a named plugin is installed and loaded. Returns `{loaded: bool, message: str, plugin: {...}}`. Call this before using plugin-specific tools to get a clear diagnostic. |
| `install_plugin` | Install a Rhino or Grasshopper plugin. See [Third-Party Plugin Support](#third-party-plugin-support) for full details. `file_path` triggers a local file install; omitting it triggers Yak or returns manual instructions depending on the plugin. |

**`install_plugin` parameters:**

| Parameter | Type | Description |
|---|---|---|
| `plugin_name` | `str` | Plugin name (case-insensitive). Used to look up the Yak package name or return manual instructions. |
| `file_path` | `str \| None` | Path to a `.gha`, `.rhp`, or `.rhi` file. When provided, skips the Yak/manual lookup and installs from the file directly. |

**`install_plugin` return values:**

| Key | Description |
|---|---|
| `success` | `true` if the install completed without errors. |
| `method` | `"yak"`, `"gha_copy"`, `"load_plugin"`, `"rhi_installer"`, `"manual_required"`, or `"vendor_installer_required"`. |
| `message` | Human-readable result or instructions. |
| `output` | (Yak only) Raw stdout from the Yak CLI, including the installed version. |
| `destination` | (`.gha` only) Destination path in the Grasshopper Libraries folder. |

---

### Grasshopper — Canvas

Requires the plugin backend and Grasshopper to be open in Rhino.

| Tool | Description |
|---|---|
| `gh_search_components` | Search the Grasshopper component library by name, category, or description. Returns component GUIDs needed for `gh_add_component`. Always search first — do not guess component GUIDs. |
| `gh_list_components` | List all objects currently on the active Grasshopper canvas with their instance GUIDs and canvas positions. |
| `gh_get_canvas` | Get a full snapshot of the canvas: all components, wire connections, and groups. |
| `gh_get_component_info` | Get detailed info about one component: input/output params, lock state, and runtime state. |
| `gh_add_component` | Place a component on the canvas by its component GUID (use `gh_search_components` to find GUIDs). Returns the new instance GUID. |
| `gh_remove_component` | Remove a component from the canvas by instance GUID. |
| `gh_move_component` | Move a component to new canvas coordinates. |
| `gh_rename_component` | Change the display name (NickName) of a component. |
| `gh_set_component_comment` | Add or update the comment tooltip on a component. |
| `gh_connect_params` | Draw a wire between two components by specifying source instance GUID + output parameter name, and target instance GUID + input parameter name. |
| `gh_disconnect_params` | Remove a wire connection between two parameters. |
| `gh_add_group` | Create a named group around a set of components. Optional color as `[r, g, b]`. |

---

### Grasshopper — Parameters

| Tool | Description |
|---|---|
| `gh_set_slider` | Set the value of a Number Slider component. The value is clamped to the slider's configured min/max range. Returns the clamped value. |
| `gh_set_panel` | Set the text content of a Panel component. |
| `gh_set_number_param` | Set one or more persistent numeric values on a Number parameter component. |
| `gh_set_point_param` | Set one or more persistent point values on a Point parameter component. Accepts `[[x,y,z], ...]`; 2D points `[x,y]` are extended to `[x,y,0]`. |
| `gh_get_output` | Read computed output data from a component after a solution. Specify `output_name` to get a single output, or omit to get all outputs. |
| `gh_get_errors` | Get runtime error and warning messages. Optionally filter to a single component by instance GUID. |
| `gh_add_script_component` | Add a C# or Python script component to the canvas. Specify `language` (`python` or `csharp`), `code`, input/output parameter names, and canvas position. **Requires Rhino 8.** |
| `gh_set_script_code` | Replace the source code in an existing script component and trigger a re-solve. **Requires Rhino 8.** |

---

### Grasshopper — Solution & Baking

| Tool | Description |
|---|---|
| `gh_get_solution_state` | Check whether the current solution is idle, computing, or in post-process. |
| `gh_run_solution` | Trigger a new solution and wait for it to complete. Configurable timeout via `wait_ms` (default 10 000 ms). Returns `timed_out: true` if the solver is still running when the timeout expires. |
| `gh_bake` | Bake the geometry output of a single component into the Rhino document. Optionally specify a target layer. Returns the Rhino object GUIDs of the baked geometry. |
| `gh_bake_all` | Bake all bakeable geometry in the active definition into the Rhino document. Returns the Rhino object GUIDs. |
| `gh_enable_component` | Enable or disable (lock) a component. Disabled components are skipped during solution. |

---

### Grasshopper — Definition Management

| Tool | Description |
|---|---|
| `gh_get_definition_info` | Return metadata about the active definition: name, file path, component count, group count, solution state, and error count. |
| `gh_new_definition` | Create a new blank Grasshopper definition and make it active. Opens the Grasshopper editor if it is not already open. |
| `gh_open_definition` | Open a `.gh` or `.ghx` file from disk. |
| `gh_save_definition` | Save the active definition. Optionally specify a file path; if omitted, saves to the current path. |
| `gh_close_definition` | Close the active definition. |

---

### Grasshopper 2 (GH2)

Requires **Rhino 9** with Grasshopper 2 installed. Grasshopper 2 is not included in stable Rhino 8 — it ships with Rhino 9. All GH2 handlers use runtime reflection — no compile-time dependency on Grasshopper2.dll. Returns a clear error when GH2 is not available, so tools degrade gracefully on Rhino 8.

Every GH2 tool accepts an optional `rhino_id` parameter (from `get_rhino_instances`) to target a specific Rhino instance.

| Tool | Description |
|---|---|
| `gh2_start` | Launch the Grasshopper 2 editor. |
| `gh2_get_canvas_graph` | Get a full snapshot of the active GH2 canvas: components, wires, and volatile data samples. `sample_size` (default 3) controls how many data items are returned per output port. |
| `gh2_apply_graph` | Atomically place components and wire them in one call. `components`: list of `{key, type_name|component_guid, x, y}` or `{key, type="slider", min, max, value, decimals, x, y}`. `wires`: list of `{from_key|from_guid, from_output, to_key|to_guid, to_input}` with ports by nickname or index. Returns `{ok, placed: {key: instanceGuid}, wired: N, errors: [...]}`. |
| `gh2_place_component` | Place a GH2 component by `type_name` (e.g. `"Point"`, `"Circle"`) or `component_guid`. Returns `instance_guid`. |
| `gh2_place_slider` | Place a GH2 Number Slider with `min`, `max`, `value`, `decimals`, and canvas `x`/`y`. Returns `instance_guid`. |
| `gh2_connect` | Wire a single output to an input. `from_output` / `to_input` can be index (int) or param name (str). |
| `gh2_connect_many` | Wire multiple connections in one call; continues past individual failures. `wires`: list of `{from_guid, from_output, to_guid, to_input}` (ports by nickname or index). Returns `{ok, connected: N, errors: [...]}`. |
| `gh2_describe_component` | Get metadata for a component: category, description, input/output param names and types. Accepts `instance_guid` (placed instance) or `name` (component type lookup). |
| `gh2_search_components` | Search available GH2 components by name, nickname, or description. Optional `category` filter. |
| `gh2_solve_graph` | Expire and re-solve the active GH2 canvas. Returns list of errors. |
| `gh2_clear_canvas` | Clear all objects from the active GH2 canvas. Requires `confirm=True` to prevent accidental clears. |

**Recommended GH2 workflow:**
```
1. gh2_start()                              → open GH2
2. gh2_search_components("Circle")          → find component GUIDs
3. gh2_apply_graph(components=[...], wires=[...])  → place + wire atomically
4. gh2_solve_graph()                        → solve and check errors
5. gh2_get_canvas_graph()                   → inspect outputs
```

---

### Grasshopper — Intelligence (GH1 Analysis, Refactor & Migration)

Tools for analysing, reorganising, and migrating Grasshopper definitions.

**Works on Rhino 8 (GH1):**

| Tool | Description |
|---|---|
| `gh_get_canvas_analysis` | Analyse the active GH1 canvas: component count, wire count, estimated wire crossings, identified logical clusters (groups of connected components), and orphaned components. Returns structured data for the AI to decide how to refactor. |
| `gh_get_graph_data` | Export the full component graph as nodes + edges. Includes each component's instance GUID, type, canvas position, and all wire connections. Used as input for layout-optimisation reasoning. |
| `gh_refactor_canvas` | Refactor the active GH1 canvas: re-layout components to reduce wire crossings and add named groups for each detected logical cluster. Optional `dry_run=true` returns the proposed moves without applying them. Returns `{moved: N, groups_added: N}`. |
| `gh1_export_migration_data` | Export migration metadata from the active GH1 canvas: each component's instance GUID, type GUID, type name, and canvas position. Cross-references `gh1_to_gh2_map.yml` to indicate which components have a known GH2 equivalent and which are `unmapped`. |

**Requires Rhino 9 + GH2** (return a clear error on Rhino 8 — no crash):

| Tool | Description |
|---|---|
| `gh_migrate_to_gh2` | Migrate the active GH1 canvas to GH2. Reads migration data, opens GH2, places GH2 equivalents for all mapped components, and wires them. Returns `{placed: N, wired: N, unmapped: [...]}`. Components without a GH2 equivalent are listed in `unmapped` but do not block the migration. |
| `gh2_move_component` | Move a GH2 component to new canvas coordinates. Accepts `instance_guid` and `x`/`y` canvas position. |
| `gh2_add_group` | Create a named group in the GH2 canvas around a list of component instance GUIDs. Optional `color` as `[r, g, b]`. |

**Recommended GH Intelligence workflow (GH1 → cleaner GH1):**
```
1. gh_get_canvas_analysis()      → understand current state (crossings, clusters)
2. gh_refactor_canvas(dry_run=True)  → preview proposed moves and groups
3. gh_refactor_canvas()          → apply layout + grouping
```

**Recommended GH1 → GH2 migration workflow:**
```
1. gh1_export_migration_data()   → see what maps and what doesn't
2. gh_migrate_to_gh2()           → place GH2 equivalents + wire them
3. gh2_solve_graph()             → check for errors
4. gh2_get_canvas_graph()        → inspect outputs
```

---

### Grasshopper — Pufferfish (Geometry Morphing)

Requires [Pufferfish](https://www.food4rhino.com/en/app/pufferfish) to be installed. Install automatically: `install_plugin("Pufferfish")`.

All Pufferfish tools place the component on the canvas and wire inputs automatically. The `canvas_x` / `canvas_y` parameters control where the component is placed on the GH canvas (in canvas units).

| Tool | Parameters | Description |
|---|---|---|
| `gh_pufferfish_tween_curves` | `curve1_instance_guid`, `curve2_instance_guid`, `count=5`, `canvas_x`, `canvas_y` | Place a **Tween Curves** component and connect two curve sources. Generates `count` intermediate curves interpolated between Curve A and Curve B. |
| `gh_pufferfish_morph_surface` | `geometry_instance_guid`, `source_surface_instance_guid`, `target_surface_instance_guid`, `canvas_x`, `canvas_y` | Place a **Surface Morph** component and connect geometry, source surface, and target surface. Remaps geometry from the UV space of the source surface to the target surface. |
| `gh_pufferfish_blend_surfaces` | `surface1_instance_guid`, `surface2_instance_guid`, `count=5`, `canvas_x`, `canvas_y` | Place a **Tween Surfaces** component and connect two surface sources. Generates `count` intermediate surface states. |
| `gh_pufferfish_twist` | `geometry_instance_guid`, `axis_instance_guid`, `angle_degrees=45.0`, `canvas_x`, `canvas_y` | Place a **Twist Object** component, connect geometry and axis line, and set the twist angle in degrees. |
| `gh_pufferfish_bend` | `geometry_instance_guid`, `axis_instance_guid`, `angle_degrees=45.0`, `canvas_x`, `canvas_y` | Place a **Bend Object** component, connect geometry and axis line, and set the bend angle in degrees. |

---

### Grasshopper — Weaverbird (Mesh Subdivision)

Requires [Weaverbird](https://www.food4rhino.com/en/app/weaverbird) to be installed. Install automatically: `install_plugin("Weaverbird")`.

All Weaverbird tools wire the `Mesh` input automatically from `mesh_instance_guid`.

| Tool | Parameters | Description |
|---|---|---|
| `gh_wb_catmull_clark` | `mesh_instance_guid`, `iterations=1`, `canvas_x`, `canvas_y` | Place a **Catmull-Clark Subdivision** component. Produces smooth, quad-dominant subdivisions. Each iteration quadruples the face count. |
| `gh_wb_loop` | `mesh_instance_guid`, `iterations=1`, `canvas_x`, `canvas_y` | Place a **Loop Subdivision** component. Optimised for triangle meshes; produces C2-continuous surfaces. |
| `gh_wb_butterfly` | `mesh_instance_guid`, `iterations=1`, `canvas_x`, `canvas_y` | Place a **Butterfly Subdivision** component. Interpolating scheme — original vertices are preserved exactly. |
| `gh_wb_frame` | `mesh_instance_guid`, `offset=0.1`, `canvas_x`, `canvas_y` | Place a **Mesh Frame** component. Shrinks each face inward by `offset`, leaving a frame of faces at each edge. Useful for generating mesh apertures. |
| `gh_wb_thicken` | `mesh_instance_guid`, `thickness=0.1`, `canvas_x`, `canvas_y` | Place a **Mesh Thickening** component. Offsets the mesh by `thickness` in the face normal direction, producing a closed solid shell. |
| `gh_wb_extrude_face` | `mesh_instance_guid`, `distance=0.5`, `canvas_x`, `canvas_y` | Place a **Mesh Face Extrusion** component. Extrudes each face outward by `distance` along its normal, creating a faceted relief surface. |

---

### Grasshopper — LunchBox (Paneling)

Requires [LunchBox](https://www.food4rhino.com/en/app/lunchbox) to be installed. Install automatically: `install_plugin("LunchBox")`.

All LunchBox panel tools wire a surface input from `surface_instance_guid` and set UV count parameters.

| Tool | Parameters | Description |
|---|---|---|
| `gh_lunchbox_quad_panels` | `surface_instance_guid`, `u_count=10`, `v_count=10`, `canvas_x`, `canvas_y` | Place a **Quad Panels** component. Divides the surface into a rectangular grid of quad panels. |
| `gh_lunchbox_tri_panels` | `surface_instance_guid`, `u_count=10`, `v_count=10`, `canvas_x`, `canvas_y` | Place a **Triangle Panels A** component. Generates triangulated panels from a surface grid. |
| `gh_lunchbox_diamond_panels` | `surface_instance_guid`, `u_count=10`, `v_count=10`, `canvas_x`, `canvas_y` | Place a **Diamond Panels** component. Generates rotated diamond-shaped panels across the surface. |
| `gh_lunchbox_hex_panels` | `surface_instance_guid`, `u_count=10`, `v_count=10`, `canvas_x`, `canvas_y` | Place a **Hexagonal Panels** component. Generates a hexagonal tiling across the surface. |
| `gh_lunchbox_space_frame` | `surface_instance_guid`, `depth=1.0`, `canvas_x`, `canvas_y` | Place a **Space Frame** component and set the frame depth. Generates a structural space frame from the surface grid — top chord, bottom chord, and diagonal members. |

---

### Grasshopper — Anemone (Looping)

Requires [Anemone](https://www.food4rhino.com/en/app/anemone) to be installed. Install automatically: `install_plugin("Anemone")`.

Anemone enables iterative feedback loops in Grasshopper — the output of one solution pass feeds back as input for the next.

| Tool | Parameters | Description |
|---|---|---|
| `gh_anemone_setup_loop` | `max_loops=100`, `canvas_x`, `canvas_y` | Place **Loop Start** and **Loop End** components side-by-side (400 canvas units apart). Sets `Max Loops` on the Loop Start component. Returns both instance GUIDs — connect your iterative logic between them. |
| `gh_anemone_set_max_loops` | `loop_start_instance_guid`, `max_loops=100` | Update the `Max Loops` count on an existing Loop Start component without replacing it. |

**Workflow pattern:**
1. Call `gh_anemone_setup_loop` to place the bookend components.
2. Place your logic components between the returned `loop_start_instance_guid` and `loop_end_instance_guid`.
3. Wire outputs from Loop Start to your logic, and wire your logic outputs into Loop End.
4. Call `gh_run_solution` to execute the loop up to `max_loops` iterations.

---

### Grasshopper — Human & Elefront (Attributes)

Requires [Human](https://www.food4rhino.com/en/app/human) and/or [Elefront](https://www.food4rhino.com/en/app/elefront). Install automatically: `install_plugin("Human")` / `install_plugin("Elefront")`.

These plugins expose Rhino object attributes (layer, name, user text) inside Grasshopper, enabling attribute-driven workflows and controlled baking.

**Elefront tools:**

| Tool | Parameters | Description |
|---|---|---|
| `gh_elefront_bake_attributes` | `component_instance_guid`, `layer="Default"`, `name=""`, `user_text={key: value}`, `canvas_x`, `canvas_y` | Place an **Elefront Bake Objects** component, wire geometry from `component_instance_guid`, and configure layer, name, and user text key-value pairs. Unlike the standard GH bake, Elefront baking preserves all attribute metadata on the Rhino object. |
| `gh_elefront_reference_by_filter` | `layer=None`, `name_filter=None`, `user_text_key=None`, `canvas_x`, `canvas_y` | Place a **Reference by Filter** component. Filters Rhino document objects by layer, name pattern, or user text key. Returns geometry matching all specified criteria. |
| `gh_elefront_set_user_text` | `component_instance_guid`, `key`, `value`, `canvas_x`, `canvas_y` | Place a **Set User Text** component, wire geometry, and set a single key-value pair. Writes user text to Rhino objects after baking. |

**Human tools:**

| Tool | Parameters | Description |
|---|---|---|
| `gh_human_get_attributes` | `rhino_object_id`, `canvas_x`, `canvas_y` | Place a **Get Object Attributes** component and set the object ID. Exposes the object's layer, name, color, linetype, render material, and all user text keys as separate outputs. |
| `gh_human_set_user_text` | `component_instance_guid`, `key`, `value_component_instance_guid`, `canvas_x`, `canvas_y` | Place a **Set User Text** component, wire objects from `component_instance_guid`, wire the value from `value_component_instance_guid`, and set the key name. Writes user text to live Rhino objects without requiring a bake. |

---

### Grasshopper — Kangaroo Physics

Kangaroo 2 is **built into Rhino 8** — no separate install required. In Rhino 7, install from [food4rhino.com](https://www.food4rhino.com/en/app/kangaroo-physics). Grasshopper must be open with a document loaded.

| Tool | Parameters | Description |
|---|---|---|
| `gh_kangaroo_setup_solver` | `canvas_x`, `canvas_y`, `iterations=100`, `threshold=1e-9` | Place a **Kangaroo2 Solver** component on the canvas. Returns `instance_guid` of the placed solver. |
| `gh_kangaroo_add_goal` | `goal_type`, `canvas_x`, `canvas_y` | Place a Kangaroo goal component. `goal_type` must be one of: `Length`, `Angle`, `Anchor`, `OnMesh`, `Spring`, `Pressure`, `Load`, `Hinge`, `Laplacian`. Returns the placed component's `instance_guid`. |
| `gh_kangaroo_connect_goal` | `solver_instance_guid`, `goal_instance_guid` | Wire a goal component's output (`G`) into the solver's `Goals` input. Call once per goal component. |
| `gh_kangaroo_configure_solver` | `solver_instance_guid`, `iterations=100`, `threshold=1e-9` | Set `Iterations` and `Threshold` on an existing solver without replacing it. Lower `threshold` (e.g. `1e-15`) gives a more converged result; higher `iterations` allows longer simulations. |
| `gh_kangaroo_run_physics` | `solver_instance_guid` | Trigger a Grasshopper solution to advance the physics simulation. Equivalent to manually clicking "Solve" or changing a slider. |

**Workflow pattern:**
1. `gh_kangaroo_setup_solver` → get `solver_guid`
2. `gh_kangaroo_add_goal(goal_type="Anchor", ...)` → get `anchor_guid`
3. `gh_kangaroo_add_goal(goal_type="Length", ...)` → get `length_guid`
4. Connect geometry to goal inputs via `gh_connect_params`
5. `gh_kangaroo_connect_goal(solver_guid, anchor_guid)`
6. `gh_kangaroo_connect_goal(solver_guid, length_guid)`
7. `gh_kangaroo_run_physics(solver_guid)`

---

### Grasshopper — Ladybug Tools & Honeybee

Requires [Ladybug Tools](https://www.food4rhino.com/en/app/ladybug-tools) to be installed via the Rhino Package Manager. Install instructions: `install_plugin("Ladybug")`.

Ladybug handles climate visualisation (weather data, sun, wind, radiation). Honeybee handles building energy modelling. Both are installed together as part of the Ladybug Tools suite.

**Ladybug tools:**

| Tool | Parameters | Description |
|---|---|---|
| `gh_ladybug_load_weather` | `epw_file_path`, `canvas_x`, `canvas_y` | Place an **Import EPW** component and set the EPW file path. The EPW output provides location, dry-bulb temperature, humidity, solar radiation, and wind data for all downstream Ladybug components. |
| `gh_ladybug_sun_path` | `location_instance_guid`, `north_angle=0.0`, `canvas_x`, `canvas_y` | Place a **Sun Path** component and connect a location output. Generates a 3D sun path diagram showing solar position throughout the year. |
| `gh_ladybug_radiation_analysis` | `geometry_instance_guid`, `location_instance_guid`, `canvas_x`, `canvas_y` | Place a **Radiation Analysis** component and connect analysis geometry and location. Computes cumulative solar radiation on surfaces (kWh/m²). |
| `gh_ladybug_wind_rose` | `location_instance_guid`, `canvas_x`, `canvas_y` | Place a **Wind Rose** component connected to a location. Visualises wind speed and direction frequency distribution. |
| `gh_ladybug_utci_comfort` | `location_instance_guid`, `geometry_instance_guid`, `canvas_x`, `canvas_y` | Place a **UTCI Comfort** component for outdoor thermal comfort analysis. UTCI (Universal Thermal Climate Index) maps comfort zones across the geometry mesh. |

**Honeybee tools:**

| Tool | Parameters | Description |
|---|---|---|
| `gh_honeybee_create_room` | `geometry_component_id`, `room_name="HBRoom"`, `canvas_x`, `canvas_y` | Place an **HB Room from Solid** component and connect a closed Brep geometry. Creates a Honeybee Room object representing a thermal zone. |
| `gh_honeybee_add_window` | `room_instance_guid`, `ratio=0.4`, `canvas_x`, `canvas_y` | Place **HB Add Subface** and connect a room. `ratio` is the window-to-wall ratio (0.0–1.0). Adds glazing to all exterior faces at the specified ratio. |
| `gh_honeybee_run_energy` | `model_instance_guid`, `canvas_x`, `canvas_y` | Place **HB Model to IDF** and connect a Honeybee Model. Exports the model to EnergyPlus IDF format for energy simulation. Run `gh_run_solution` after to trigger the simulation. |

---

### Geometry Creation

| Tool | Description |
|---|---|
| `create_rhino_geometry` | Create a single geometric object. Supported types: `box`, `sphere`, `cylinder`, `cone`, `torus`, `line`, `polyline`, `arc`, `circle`, `ellipse`, `curve` (free-form NURBS), `surface` (from points), `plane`, `text`, `point`, `mesh`, `extrusion`, `brep` (from existing), and more. **Box params:** corner form — `corner=[x,y,z]` + `width`/`depth`/`height` (or `x_size`/`y_size`/`z_size`); center form — `center=[x,y,z]` + same dimension params, or `size=[sx,sy,sz]`. **`snap_to_grid`:** pass a grid spacing (e.g. `0.5` for 6-inch, `1.0` for 1-foot) to round all point coordinates before creation. |
| `create_rhino_scene` | Create multiple objects in one call. Accepts a list of the same object descriptors as `create_rhino_geometry`. Also accepts `snap_to_grid` to align all objects in the batch. |
| `validate_rhino_geometry` | Check objects for common tracing errors: endpoint gaps, non-orthogonal walls, duplicate segments, zero-length curves. Returns a structured issue report with severity levels. `auto_fix=True` closes gaps and removes duplicates automatically. |
| `get_rhino_objects` | List objects with optional filters by type, layer, name, or color. **Pagination:** `offset` + `limit` (default 100) — response includes `total_matching` and `has_more` so you can page through large scenes. **Hidden objects:** `include_hidden=true` includes objects that are hidden (default false). **Lightweight mode:** `include_geometry=false` skips bounding-box computation for fast metadata-only queries. **Spatial filter:** `bbox_filter=[[min_x,min_y,min_z],[max_x,max_y,max_z]]` restricts to objects overlapping a region. Supports `logic="or"` for multi-filter unions. |
| `get_rhino_object_info` | Get detailed info about one object: type, layer, name, bounding box, material, groups, and user text dict. Pass `object_id` (GUID) **or** `name` (exact name match, returns first hit) — no need to know the GUID when you have a name. |

---

### Object Editing & Selection

| Tool | Description |
|---|---|
| `select_rhino_objects` | Select objects by GUID, name, layer, type, color, `color_tolerance` (per-channel fuzzy match), or `user_text` (`{"key": "value"}` dict). Supports `logic="or"`. `deselect=true` removes matching objects from the selection instead of replacing it. `limit` caps the number of objects acted on. |
| `get_selected_rhino_objects` | Return the GUIDs and basic properties of all currently selected objects. Add `include_attributes=true` to include each object's user text key-value pairs in one round-trip. |
| `transform_rhino_objects` | Move, rotate, or scale objects. Specify object GUIDs or operate on the current selection. Supports `copy=true` to duplicate instead of move. |
| `edit_rhino_object_attributes` | Change name, layer, display color, or visibility on one or more objects. `visible=true` shows hidden objects; `visible=false` hides them. Pass `apply_to_all=true` to target every object in the document. |
| `delete_rhino_objects` | Delete objects by GUID, the current selection, or pass `delete_all=true` to clear the entire document in one call. |
| `align_geometry_to_point` | Move all specified objects (or all document objects) so that a source point lands exactly on a target point. Use after PDF tracing to anchor geometry to model-space origin. |
| `undo_rhino` | Undo the last N operations (`count`, default 1). Via the plugin backend: stops when the undo stack is exhausted and reports `undone_steps` vs `requested_steps`. Via rhinocode: runs `count` individual `_Undo` commands. |
| `redo_rhino` | Redo the last N undone operations (`count`, default 1). Via the plugin backend: stops when the redo stack is exhausted. Via rhinocode: runs `count` individual `_Redo` commands. |

---

### Layers

| Tool | Description |
|---|---|
| `manage_rhino_layer` | List all layers, create a new layer, update layer properties (color, visibility, lock state), delete a layer, or set the current layer. |
| `create_layer` | Create a named layer with optional color. Returns the new layer index. |
| `delete_layer` | Delete a layer by name or index. |
| `get_or_set_current_layer` | Get the current active layer name, or set it by providing a name. |

---

### Materials

| Tool | Description |
|---|---|
| `get_materials` | Return all non-deleted materials in the document with diffuse, specular, emission, shininess, and transparency values. |
| `create_material` | Create a new material with name, diffuse/specular/emission colors, shininess, and transparency. |
| `set_object_material` | Assign a material to an object by material name or index. |
| `delete_material` | Delete a material by name or index. |

---

### PBR Materials & Rendering

| Tool | Description |
|---|---|
| `create_pbr_material` | Create a physically-based material with base color, metallic, roughness, opacity, optional `ior` (applied via `OpacityIOR`), emission, and texture maps (albedo, roughness, metallic, normal, displacement, AO, opacity). Textures attach at default amount; Rhino exposes no bump/displacement scale. Reports `applied` / `not_applied`. |
| `assign_pbr_material_to_objects` | Assign a named PBR material to one or more objects by GUID. |
| `get_pbr_material_info` | Return the PBR properties and texture paths of a named material. |
| `list_pbr_materials` | List all PBR materials in the document. |
| `set_environment_map` | Load an HDR or EXR file as the render environment (background, lighting, reflections). |
| `set_render_settings` | Configure background color, transparent background, ground plane on/off and ground plane altitude (altitude applies independently). Renderer choice, samples, shadows and AO have no cross-engine Rhino API and are not offered. Reports `applied` / `not_applied`. |
| `render_to_image` | Trigger a Rhino render and save/return the result as a file path and optional base-64 PNG. |

---

### V-Ray Rendering

Requires [V-Ray for Rhino](https://www.chaos.com/vray/rhino) to be installed and licensed. Each tool checks that V-Ray is loaded and returns `{"success": false, "message": "..."}` if it is not. Render size, quality preset and rendering use V-Ray's documented Python module (`rh8VRay` / `rhVRay`); when it is not importable the result lists those settings under `not_applied`. Lights and the environment are interactive commands/dialogs.

| Tool | Parameters | Description |
|---|---|---|
| `vray_start_ipr` | — | Run `_vrayRender _Interactive` to start V-Ray interactive rendering. |
| `vray_stop_ipr` | — | Run `_vrayRender _Stop`. |
| `vray_render` | `output_path=None`, `width=1920`, `height=1080`, `quality_preset="medium"` | Set size and quality preset through the V-Ray Python module (`rh8VRay`/`rhVRay`) and run `vray.Render` synchronously. `quality_preset`: `low` \| `medium` \| `high` \| `ultra` (V-Ray Low/Medium/High/High+). Saving via `_-SaveRenderWindowAs` is attempted; check `saved`. Reports `applied` / `not_applied`. |
| `vray_create_material` | `name`, `diffuse_color=[r,g,b]`, `opacity=1.0` | Create a standard Rhino material (diffuse 0–255, opacity as transparency) that V-Ray converts on render. V-Ray documents no API for creating VRayMtl assets, so roughness/metalness/IOR are not offered. |
| `vray_apply_material` | `object_ids=[...]`, `material_name` | Assign a named V-Ray material to a list of Rhino objects by GUID. |
| `vray_add_light` | `light_type="Rectangle"` | Launch the interactive `_vrayLight _Create <type>` command; placement is by mouse and intensity/colour are set in the Asset Editor. `light_type`: `Rectangle` \| `Sphere` \| `Directional` \| `Spot` \| `IES` \| `Omni` \| `Dome` \| `Sun`. |
| `vray_set_environment` | — | Open the V-Ray Asset Editor (`_vrayShowAssetEditor`) to set the environment HDRI interactively. Nothing is applied programmatically. |
| `vray_set_render_settings` | `width=None`, `height=None`, `quality_preset=None` | Set V-Ray output size and quality preset through the V-Ray Python module. AA subdivisions, GI presets and time limits have no documented scripting access and are not offered. Reports `applied` / `not_applied`. |
| `vray_export_vrscene` | `output_path` | Run `_vrayExportVRScene` to export a `.vrscene` file. The command documents no compression option. |

---

### Enscape Real-Time Rendering

Requires [Enscape](https://enscape3d.com) to be installed and licensed. Each tool checks that Enscape is loaded and returns `{"success": false, "message": "..."}` if it is not. Enscape has no scripting API beyond its Rhino commands, so these tools only launch those commands; image size, panorama resolution and atmosphere are set in Enscape's own dialogs.

| Tool | Parameters | Description |
|---|---|---|
| `enscape_start` | — | Launch the Enscape real-time rendering window from the current Rhino viewport. |
| `enscape_screenshot` | `output_path` | Run `Enscape_Screenshot`; may open a save dialog. Image size is an Enscape visual setting and cannot be scripted. |
| `enscape_export_panorama` | `output_path` | Run `Enscape_ExportPanorama`; may open an export dialog. Resolution is an Enscape setting and cannot be scripted. |
| `enscape_export_standalone` | `output_path` | Export the scene as a self-contained Enscape standalone executable (`.exe`) for sharing without requiring an Enscape license on the viewer's machine. |
| `enscape_set_time_of_day` | `hour=12`, `minute=0` | Set the sun position by time of day. `hour`: 0–23, `minute`: 0–59. |
| `enscape_set_atmosphere` | — | Open Enscape's Visual Settings dialog (`Enscape_VisualSettings`); atmosphere is adjusted there. Nothing is applied programmatically. |
| `enscape_create_view` | `name` | Save the current Enscape camera position as a named view that can be recalled later. |

---

### Views & Viewport

| Tool | Parameters | Description |
|---|---|---|
| `set_rhino_view` | `view="Perspective"`, `camera=[x,y,z]`, `target=[x,y,z]`, `lens=None` | Activate a named view or set camera position, target, and lens length. Common view names: `Perspective`, `Top`, `Front`, `Right`, `Back`, `Left`, `Bottom`. |
| `capture_rhino_view` | `path=None`, `width=1200`, `height=900`, `viewport=None`, `show_grid=None`, `show_axes=None`, `show_cplane_axes=None`, `zoom_to_fit=False` | **Capture a viewport and return it as a visual image the AI can see.** `viewport` selects a named viewport (e.g. `"Top"`, `"Perspective"`) — omit to capture the active viewport. `path` is optional; when provided the PNG is also saved to disk. `show_grid` temporarily toggles the construction grid. `show_axes` and `show_cplane_axes` are aliases — both control construction-axes visibility for the capture. Returns `[{metadata}, Image]` so the AI client renders the image inline. |

---

### Document & File I/O

| Tool | Description |
|---|---|
| `get_rhino_document_summary` | Return document metadata: object count by type and layer, materials, units, tolerance, and named views. |
| `save_rhino_document` | Save the active document to its current path. Pass `path` to save-as a new file. |
| `export_rhino_document` | Export to a specified file format. Supported: `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.stp`, `.dxf`, `.dwg`, `.pdf`. `select_all=true` (default) exports the whole document; set `false` to export only selected objects. |
| `import_file` | Import any file Rhino supports (3DS, FBX, OBJ, STL, STEP, IGES, DXF, DWG, 3DM) with automatic material normalization and display setup. DWG/DXF/SVG/PDF → Wireframe mode, black background, grid hidden, black layers flipped to white. FBX/OBJ/3DS/STL/3MF/STEP/IGES/3DM → Shaded mode. Zoom to extents applied automatically. Override with `post_import_display`. |
| `normalize_imported_objects` | Fix display colors on objects imported from 3DS, FBX, OBJ and similar formats. Preserves original material colors, shine, transparency, specular, emission, and texture maps (bitmap, bump, environment, transparency channels). |
| `set_object_display_color` | Set object color so it shows correctly in both Shaded and Rendered viewport modes. Creates a matching render material (MCP_Color_RRGGBB) — ObjectColor alone only affects wireframe edges. Handles import-baked objects automatically. |

---

### Export Tools

| Tool | Description |
|---|---|
| `export_step` | Export selected objects or entire model to STEP with a configurable application protocol (`schema`: AP203/AP214/AP242). Uses the document tolerance (Rhino has no STEP tolerance option). Reports `applied` / `not_applied`. |
| `export_iges` | Export to IGES with a configurable `tolerance` (`FileIgsWriteOptions.Tolerance`). Reports `applied` / `not_applied`. |
| `export_dwg` | Export to DWG/DXF with AutoCAD version targeting (`autocad_version`: 2000–2018). Reports `applied` / `not_applied`. |
| `export_obj` | Export to OBJ/MTL with material definition and texture coordinate export controls. Reports `applied` / `not_applied`. |
| `export_fbx` | Export to FBX with `file_type` (`binary7` \| `binary6` \| `ascii7` \| `ascii6`). Textures are always external references. Reports `applied` / `not_applied`. |
| `export_glb` | Export to GLB (textures embedded) or glTF (external resources) with Draco compression and material export controls. Reports `applied` / `not_applied`. |
| `export_3dm` | Export to native Rhino 3DM with version targeting, selective object export by layer/type, and embedded metadata notes. |
| `export_stl` | Export to STL with binary/ASCII format control and mesh tolerance settings. |
| `export_3mf` | Export to 3MF using the document's current render-mesh settings (Rhino exposes no 3MF mesh-quality option). |
| `convert_image` | Convert image files between PNG, JPG, BMP, TIFF, GIF with JPEG quality control; one of `width`/`height` resizes preserving aspect ratio. |
| `export_viewport_image` | Capture the active viewport to an image file with display mode, resolution, and scale options. |

---

### Document Reading

Read external design files — floor plans, specifications, spreadsheets, and reference images — directly from the MCP session. The AI receives page images it can visually interpret, extracted text, and structured data, eliminating the need for separate file-reading workarounds.

**Complete PDF-to-Rhino tracing workflow:**
```
1. get_pdf_info(path)                                       → page count + sheet dimensions
2. read_pdf(path, pages="1", dpi=200, scale_hint='1/4"=1\'') → page image + nominal px-to-feet ratio
3. calibrate_pdf_scale([x1,y1], [x2,y2], real_distance=20)  → corrected ratio (fixes print-to-fit error)
4. read_pdf_vectors(path, pages="1", dpi=200, real_units_per_px=...)  → exact line coords (CAD-exported PDFs)
5. extract_pdf_dimensions(path, pages="1")                   → dimension annotations for cross-check
6. create_rhino_scene(items=[...], snap_to_grid=0.5)         → geometry snapped to 6-inch grid
7. validate_rhino_geometry(auto_fix=True)                    → close gaps, remove duplicates
8. align_geometry_to_point([px,py,0], [0,0,0])               → anchor to model origin
```

> **Have the original CAD file?** Use `import_file` instead — Rhino opens DWG/DXF/STEP/IGES natively with exact geometry. The PDF tools are for when you only have a printed/exported PDF.

`scale_hint` formats: `"1/4\" = 1'"`, `"1/8\" = 1'-0\""`, `"1\" = 20'"` (imperial → feet); `"1:100"`, `"1:50"` (metric → meters). Use `calibrate_pdf_scale` to correct for print-to-fit scaling when the sheet was not printed at its intended size.

**PDF reading tools:**

| Tool | Description |
|---|---|
| `get_pdf_info` | Return page count, metadata, and page sizes. Use `pages` to paginate; at most 50 pages per call, with explicit `truncated`. |
| `read_pdf` | Render pages as base64-encoded PNG images. `scale_hint` enables pixel→real-world mapping. Parameters: `pages`, `dpi` (default 150; use 200-300 for fine detail), `max_pages` (default 10), `scale_hint`. |
| `calibrate_pdf_scale` | Compute the true `px_per_real_unit` ratio from two pixel coordinates and a known real-world distance — corrects for print-to-fit scaling. |
| `read_pdf_vectors` | Extract lines, rectangles, and cubic curves in PDF points relative to the rotated crop origin. Use `real_units_per_point` or `real_units_per_px` with matching `dpi`. Reports partial/visibility limits; `NO_VECTORS` means no drawing paths. |
| `extract_pdf_dimensions` | Extract dimension annotation strings (`20'-6"`, `3000mm`, etc.) and their bounding box positions from the PDF text layer. Heuristic, explicit-unit matches only; bare part numbers are excluded. Use the same DPI as rendering. |

**Other document tools:**

| Tool | Formats | Description |
|---|---|---|
| `read_image` | `.jpg` `.png` `.tiff` `.bmp` `.webp` `.gif` `.heic` `.heif` | Read an image and return it as base64-encoded PNG. Auto-resizes to `max_dimension` (default 2048 px). |
| `read_spreadsheet` | `.csv` `.xlsx` `.xls` | Read CSV or Excel as structured rows. Returns all sheet names for workbook navigation. |
| `read_svg` | `.svg` `.svgz` | Parse SVG XML with metadata and optional PNG render via cairosvg. |
| `read_docx` | `.docx` | Extract paragraphs (with style names) and tables from Word documents. |

**Parameters shared across document tools:**

| Parameter | Tool | Default | Notes |
|---|---|---|---|
| `pages` | `read_pdf`, `read_pdf_vectors`, `extract_pdf_dimensions` | all (up to `max_pages`) | `"3"`, `"1-5"`, `"1,3,5-8"` — 1-based |
| `dpi` | `read_pdf`, `read_svg`, `extract_pdf_dimensions` | 150 | 150 = overview; 200-300 = fine drawing detail |
| `max_pages` | PDF readers | 10 (info: 50) | 1–50 pages per call; truncation is reported |
| `scale_hint` | `read_pdf` | *(none)* | Imperial: `"1/4\" = 1'"`. Metric: `"1:100"` |
| `real_units_per_px` | `read_pdf_vectors`, `extract_pdf_dimensions` | *(none)* | From `calibrate_pdf_scale` or `read_pdf`; supply the same `dpi` to vector/dimension tools. Vector output remains in points; conversion accounts for DPI. |
| `max_dimension` | `read_image` | 2048 | Max pixel dimension after resize |
| `sheet` | `read_spreadsheet` | first sheet | Sheet name or 1-based index |
| `max_rows` | `read_spreadsheet` | 500 | Row cap; re-call with offset for large sheets |
| `include_tables` | `read_docx` | `true` | Set `false` for text only |
| `render_png` | `read_svg` | `true` | Requires `brew install cairo` on macOS |

**macOS note:** On macOS, `read_svg` PNG rendering requires libcairo (installed via `brew install cairo`). The server sets `DYLD_LIBRARY_PATH` automatically — no manual configuration needed.

---

### Scripting

| Tool | Description |
|---|---|
| `execute_rhino_python` | Run arbitrary Python code inside Rhino with full RhinoScriptSyntax and RhinoCommon access. Assign a JSON-serialisable value to `result` to return data. **Document recovery:** failed execution rolls back the Rhino undo record, including recorded additions, modifications and deletions. External side effects and unsupported third-party state cannot be rolled back. Pass `verified_functions=["rs.AddBox", ...]` to document which API calls were looked up — omitting it adds an `api_warning` to the response as a reminder to verify RhinoScript names before use. |
| `execute_rhino_csharp` | Run arbitrary C# code inside Rhino via Roslyn scripting. Returns stdout output or document changes. Requires RhinoCode C# support (Rhino 8). |
| `get_rhino_commands` | List all available Rhino command names, optionally filtered by substring (`filter="circle"`). `loaded_only=true` (default) limits to loaded plugins. Call this before `run_rhino_command` to discover exact spellings. |
| `run_rhino_command` | Execute a Rhino command macro string (e.g. `_Box 0,0,0 1,1,1`). `echo=true` echoes the command to Rhino's history. Returns `output` with captured command-window text so the AI can read results. Requires the Rhino plugin to be running (auto-starts with Rhino). |
| `list_tool_categories` | Returns all tool categories with counts. Use `include_tool_names=true` to list every tool name per category. |
| `search_rhino_docs` | Full-text search of bundled Rhino scripting notes. |
| `get_rhinoscript_docs` | Look up RhinoScriptSyntax module-level documentation. Pass a module name (`"curve"`, `"surface"`, `"object"`, etc.) to list its functions. |
| `search_rhinoscript_functions` | Search RhinoScriptSyntax function reference by name or keyword. **Always call this before writing Python scripts** to avoid hallucinated function names. |
| `get_rhinoscript_function` | Get the full docstring for a specific RhinoScriptSyntax function including parameter types, order, and return values. |
| `list_rhinoscript_modules` | List all RhinoScriptSyntax modules with their function counts. Use to discover available modules before calling `get_module_functions`. |
| `get_module_functions` | List all functions in a named RhinoScriptSyntax module with their signatures. Faster than `search_rhinoscript_functions` when you know which module you need. |

**Best practice for `execute_rhino_python`:**

```
1. search_rhinoscript_functions("AddBox")   → find the right function + signature
2. execute_rhino_python(
     code="import rhinoscriptsyntax as rs\n...\nresult = {'id': str(obj)}",
     verified_functions=["rs.AddBox", "rs.ObjectLayer"]
   )
```

Providing `verified_functions` suppresses the `api_warning` in the response and signals that API calls were verified, not guessed.

**Execution safety gates** — operators can disable arbitrary-code execution via environment variables:

| Variable | Tool(s) controlled |
|---|---|
| `RHINO_MCP_ENABLE_RHINOSCRIPT=0` | Python dispatch, built-in script-backed tools, and GH Python script creation |
| `RHINO_MCP_ENABLE_CSHARP=0` | C# dispatch and GH C# script creation |
| `RHINO_MCP_ENABLE_RUN_COMMAND=0` | `run_rhino_command`, `run_command` |

Set these gates in both the MCP and Rhino environments. Replacing an existing GH script requires both script gates. These controls are not a sandbox; see [execution controls](docs/secure-operation.md#execution-controls). All gates default to enabled (`1`). When disabled, the tool returns `{"ok": false, "error_code": "TOOL_DISABLED"}` rather than raising an exception.

**Named MCP Resources** (read-only, browseable in MCP clients that support resources):

| Resource URI | Description |
|---|---|
| `rhinoscript://modules` | List all RhinoScriptSyntax modules with their function counts |
| `rhinoscript://module/{name}` | Full function listing for a named module (e.g. `rhinoscript://module/curve`) |
| `rhinoscript://function/{name}` | Full docstring for a named function (e.g. `rhinoscript://function/AddBox`) |

These mirror `list_rhinoscript_modules`, `get_module_functions`, and `get_rhinoscript_function` as browseable resources rather than tool calls.

---

### Boolean Operations

| Tool | Description |
|---|---|
| `boolean_union` | Unite two or more Brep/solid objects. |
| `boolean_difference` | Subtract one set of solids from another. |
| `boolean_intersection` | Compute the intersection volume of two or more solids. For 3+ objects, chains pairwise intersections automatically. |

---

### Curve Operations

| Tool | Description |
|---|---|
| `loft` | Loft through a set of profile curves. Supports normal, loose, tight, straight, and developable loft types. |
| `extrude_curve` | Extrude a curve along a direction vector to create a surface or solid. |
| `sweep1` | Sweep a profile curve along a rail curve. |
| `offset_curve` | Offset a curve by a distance on a plane. |
| `pipe` | Create a pipe surface along a rail curve with given radius. |
| `project_curve` | Project a curve onto a surface along a direction. |
| `intersect_curves` | Find intersection points between two curves. |
| `split_curve` | Split a curve at parameter values or intersection points. |

---

### AI Generation

| Tool | Description |
|---|---|
| `generate_3d_from_text` | Submit a text prompt to generate a 3D mesh. `service`: `"rodin"` (Hyper3D, requires `HYPER3D_API_KEY`) or `"hunyuan3d"` (public Gradio, no key needed). `output_format`: `glb`, `obj`, `fbx`, `stl`, `usdz`. `tier`: `"Regular"` or `"Sketch"` (Rodin only). Returns a `job_id` for polling. |
| `generate_3d_from_images` | Submit 1–5 reference images for image-to-3D generation. Same `service`/`output_format` options as `generate_3d_from_text`. |
| `poll_generation_job` | Poll a generation job by `job_id` and `service`. Returns `progress` (0.0–1.0), `status`, and `download_url` when complete. |
| `import_generated_model` | Download a completed mesh and import it into Rhino. Pass either `(job_id, service)` or a direct `download_url`. Supports `scale` and `position` to place the model on import. |
| `get_generation_services_status` | Check which AI generation services are reachable and whether API keys are configured. |

---

### Studio Pipeline Tools

Requires env vars — see [Studio Pipeline Env Vars](#studio-pipeline-env-vars). All cloud services are optional; the pipeline degrades gracefully to local output without credentials.

**Design Language** (`ANTHROPIC_API_KEY` required):

| Tool | Description |
|---|---|
| `urban_generate_design_language` | Call Claude API to generate a complete design language. **Required params:** `brief` (free-text site description), `typology` (e.g. `"residential"`, `"mixed-use"`, `"office"`), `far` (floor area ratio, e.g. `3.5`), `climate_zone` (e.g. `"temperate"`, `"arid"`, `"tropical"`). **Optional:** `style_hints` (comma-separated direction words, e.g. `"brick, biophilic"`). Returns: `style_name`, `facade_vocabulary`, `material_palette` (with hex codes), `colour_story`, `landscape_character`, `diffusion_prompt`, `negative_prompt`, `executive_summary`. Stores result in session state. |
| `urban_update_design_language` | Patch a single field of the current design language (e.g. `style_name`, `facade_vocabulary`, `material_palette`). Re-derives the diffusion prompt when style or materials change. |
| `urban_get_design_language` | Return the current session design language dict, or `{"set": false}` if none generated yet. |

**AI Renders** (`FAL_KEY` required):

| Tool | Description |
|---|---|
| `urban_render_views` | Capture one or more named Rhino viewports and AI-render them using fal.ai FLUX.1 ControlNet img2img. **Optional params:** `views` (list of viewport names, default `["Perspective","Top","Front","Right"]`), `strength` (ControlNet influence 0–1, default `0.65`; lower = more photorealistic, higher = more stylised), `style_override` (ad-hoc prompt string to override the session design language), `seed` (integer for reproducibility). Uses the session design language diffusion prompt by default. Retries with reduced strength on first failure; falls back to raw Rhino captures on double failure. Returns list of `RenderResult` dicts: `original_b64`, `rendered_b64`, `prompt_used`, `seed`. |
| `urban_render_style_preview` | Text-to-image style mood board via fal.ai FLUX.1 (no massing or Rhino viewport needed). Use to explore design directions before generating the full massing. |
| `urban_get_renders` | Return all AI renders produced this session, keyed by view name (`Perspective`, `Top`, `Front`, `Right`, etc.). |

**Report Generator** (`DOCRAPTOR_API_KEY` + AWS credentials optional):

| Tool | Description |
|---|---|
| `urban_export_report` | Collect all session state (metrics, renders, solar, design language), render a branded Jinja2 HTML template, convert to PDF via DocRaptor, upload to S3, and return a 7-day presigned URL. Falls back to `~/.urbanagent/reports/` when cloud credentials are absent. |
| `urban_preview_report` | Render the report as HTML only — no PDF conversion, no S3 upload. Returns the HTML string for fast iteration. |
| `urban_list_reports` | List all reports exported this session with scheme name, PDF URL, timestamp, and file size. |

**Pipeline Orchestrator**:

| Tool | Description |
|---|---|
| `urban_run_studio_pipeline` | Single-call orchestrator. Runs all 4 steps in sequence: design language → AI renders → solar analysis → PDF export. Design language failure aborts; render/solar/export failures are logged but the pipeline continues. Supports `skip_steps=["renders"]` to reuse existing renders. Returns `PipelineResult` with `report_url`, `renders`, `metrics`, `design_language`, `step_log`, `elapsed_s`, and `errors`. |
| `urban_pipeline_status` | Return the status of the currently running or last completed pipeline: `{running, current_step, steps_done, steps_total}`. |
| `urban_list_pipeline_runs` | List all pipeline runs this session with their report URLs, step counts, and errors. Allows comparing across scheme iterations. |

---

### Asset Libraries (Poly Haven & Sketchfab)

| Tool | Description |
|---|---|
| `get_polyhaven_categories` | List Poly Haven asset categories (textures, HDRIs, models). |
| `search_polyhaven_assets` | Search Poly Haven by keyword and category. |
| `download_polyhaven_asset` | Download a Poly Haven asset (texture maps or HDR file) to a local path. |
| `apply_polyhaven_texture` | Download and apply a Poly Haven texture as a PBR material on selected objects. |
| `apply_polyhaven_hdri` | Download and set a Poly Haven HDRI as the Rhino render environment. |
| `search_sketchfab_models` | Search Sketchfab for downloadable 3D models. |
| `get_sketchfab_model_info` | Get metadata, thumbnail, and download info for a Sketchfab model. |
| `download_sketchfab_model` | Download a Sketchfab model and import it into Rhino. |

---

### VisualARQ (Architectural BIM)

Requires [VisualARQ](https://www.visualarq.com) to be installed and licensed. Each tool checks that VisualARQ is loaded. Install instructions: `install_plugin("VisualARQ")`.

VisualARQ adds parametric BIM objects (walls, slabs, columns, stairs, etc.) directly inside Rhino. All VisualARQ objects are standard Rhino objects with embedded BIM data — no separate file format required. VisualARQ has no public scripting API: the creation tools below launch the interactive `va*` commands, which then expect mouse input, so geometry, dimensions and styles cannot be passed programmatically.

| Tool | Parameters | Description |
|---|---|---|
| `varq_create_wall` | — | Launch the interactive `_vaWall` command. VisualARQ has no scripting API; points, height and style are chosen with the mouse. |
| `varq_add_opening` | `opening_type="window"` | Launch the interactive `_vaWindow` or `_vaDoor` command. `opening_type`: `window` \| `door`. Wall, position, size and style are chosen with the mouse. |
| `varq_create_slab` | — | Launch the interactive `_vaSlab` command; boundary, thickness and style are chosen with the mouse. |
| `varq_create_column` | — | Launch the interactive `_vaColumn` command; position, height and style are chosen with the mouse. |
| `varq_create_stair` | — | Launch the interactive `_vaStair` command; geometry and style are chosen with the mouse. |
| `varq_create_railing` | — | Launch the interactive `_vaRailing` command; path, height and style are chosen with the mouse. |
| `varq_set_level` | — | Open the interactive `_vaLevels` dialog; levels are edited there. |
| `varq_export_ifc` | `output_path` | Export the model to IFC via `_vaExportIFC`. The IFC schema version comes from VisualARQ's IFC Export Options dialog; the command documents no version option. |
| `varq_get_object_properties` | `object_id` | Get VisualARQ type, style, level assignment, and IFC properties for any object by GUID. Returns `{"type": "...", "style": "...", "level": "..."}`. |
| `varq_list_styles` | `object_type="wall"` | List available VisualARQ styles for a given object type. `object_type`: `wall` \| `door` \| `window` \| `slab` \| `column` \| `stair` \| `railing`. |

---

### Lands Design (Landscape)

Requires [Lands Design](https://www.lands-design.com) to be installed and licensed. Each tool checks that Lands Design is loaded. Install instructions: `install_plugin("Lands Design")`.

Lands Design adds landscape-specific objects (plants, terrain, paths, water) directly inside Rhino, with a built-in plant species database and seasonal display. Lands Design has no public scripting API: the placement tools below launch the interactive `la*` commands, which then expect mouse input, so plants, positions and geometry cannot be passed programmatically.

| Tool | Parameters | Description |
|---|---|---|
| `lands_place_plant` | — | Launch the interactive `_laPlant` command. Lands Design has no scripting API; species, position and size are chosen with the mouse. |
| `lands_place_tree` | — | Launch the interactive `_laPlant` command (trees are plants); species and placement are chosen with the mouse. |
| `lands_create_terrain` | — | Launch the interactive `_laTerrain` command; boundary and source geometry are picked with the mouse. |
| `lands_create_path` | — | Launch the interactive `_laPath` command; centerline, width and surface are chosen with the mouse. |
| `lands_create_water` | — | Launch the interactive `_laWater` command; boundary and level are chosen with the mouse. |
| `lands_get_plant_database` | — | Open the interactive `_laPlantDatabase` window. No plant list is returned and no filtering can be scripted. |
| `lands_set_season` | `season="summer"` | Set the display season for all Lands Design plants and trees in the scene. `season`: `spring` \| `summer` \| `autumn` \| `winter`. Affects 3D representation and texture. |
| `lands_export_plant_list` | `output_path` | Export a plant schedule via `_laExportPlantList`; the format follows the file extension (`.csv`, `.xlsx`). |

---

### Annotations

| Tool | Description |
|---|---|
| `add_text` | Add a text annotation to the document at a 3D point with font, size, bold/italic options, name, and layer. |
| `add_text_dot` | Add a text dot (balloon label) at a 3D point with optional font height. |
| `add_leader` | Add a leader (line with arrowhead and optional text) through a list of 3D points. |

---

### Blocks (Instance Definitions)

| Tool | Description |
|---|---|
| `create_block` | Create a block definition from selected objects with a base point. Optionally delete the input geometry. |
| `insert_block` | Insert an instance of a named block at a point with scale and rotation. |
| `explode_block` | Explode a block instance back to individual objects. |
| `delete_block` | Delete a block definition by name. |
| `list_blocks` | List all block definitions in the document. |

---

### Groups

| Tool | Description |
|---|---|
| `create_group` | Create an empty named group, or pass `object_ids` to group objects immediately. |
| `delete_group` | Delete a group by name. |
| `add_to_group` | Add objects to an existing group. |
| `remove_from_group` | Remove objects from a group. |
| `list_groups` | List all groups in the document with their member counts. |
| `select_by_group` | Select all objects belonging to a named group. |

---

### Analysis & Measurement

| Tool | Description |
|---|---|
| `measure_distance` | Measure the Euclidean distance between two 3D points. |
| `measure_curve_length` | Return the arc length of a curve. |
| `measure_area` | Return the area of a closed curve or surface. |
| `measure_volume` | Return the volume of a closed solid or polysurface. |
| `get_bounding_box` | Return the axis-aligned bounding box of one or more objects. `world_coordinates=true` returns world-space bounds. |
| `is_object_solid` | Return whether an object is a closed polysurface or closed mesh. |

---

### User Data (Object & Document Attributes)

| Tool | Description |
|---|---|
| `set_user_text` | Set a key-value string pair on an object's user data. |
| `get_user_text` | Get the value of a user data key on an object. |
| `delete_user_text` | Delete a user data key from an object. |
| `set_document_user_text` | Set a document-level key-value string (persisted in the .3dm file). |
| `get_document_user_text` | Get a document-level user data value by key. |

---

### Surface Operations

| Tool | Description |
|---|---|
| `revolve_curve` | Revolve a profile curve around an axis to create a surface of revolution. |
| `sweep2` | Sweep a profile curve along two rail curves. |
| `create_planar_surface` | Create a planar surface from a closed flat curve. |
| `create_edge_surface` | Create a surface from 2–4 edge curves. |
| `create_network_surface` | Create a surface from a network of crossing curves. |
| `create_patch` | Fit a patch surface to a set of curves or points. |
| `offset_surface` | Offset a surface by a distance. |
| `split_brep` | Split a Brep with a cutting surface. |
| `fillet_surfaces` | Fillet two surfaces with a given radius. |
| `cap_planar_holes` | Cap all planar holes in a polysurface to make it solid. |
| `extrude_curve_along_curve` | Extrude a profile curve along a path curve. |
| `extrude_curve_to_point` | Extrude a curve to a point to create a cone-like surface. |
| `duplicate_edge_curves` | Extract the edge curves of a Brep as standalone curve objects. |
| `duplicate_surface_border` | Extract the outer border curve of a surface. |
| `join_surfaces` | Join adjacent surfaces/Breps into a single polysurface. |
| `explode_polysurface` | Explode a polysurface into individual surfaces. |
| `unroll_surface` | Unroll a developable surface or polysurface to a flat pattern. |

---

### Mesh Operations

| Tool | Description |
|---|---|
| `create_mesh` | Create a mesh from explicit vertex coordinates and face index lists. |
| `create_planar_mesh` | Create a planar mesh from a closed flat curve. |
| `mesh_from_surface` | Convert surfaces or polysurfaces to mesh objects. |
| `mesh_boolean_union` | Boolean union two meshes. |
| `mesh_boolean_difference` | Boolean difference of two meshes. |
| `mesh_boolean_intersection` | Boolean intersection of two meshes. |
| `join_meshes` | Join multiple mesh objects into a single mesh. |
| `mesh_to_nurbs` | Convert a mesh to a NURBS polysurface. |
| `mesh_offset` | Offset a mesh by a distance (creates a shell). |

---

### Advanced Transforms

| Tool | Description |
|---|---|
| `mirror_objects` | Mirror objects about a plane defined by origin and normal. `copy=true` keeps originals. |
| `copy_objects` | Copy objects by a translation vector. |
| `array_linear` | Create a linear array of objects along a direction vector. |
| `array_polar` | Create a polar (circular) array of objects around a center point. |
| `orient_objects` | Orient objects from a reference plane to a target plane (2-point or 3-point orient). |

---

### Extended Curve Operations

| Tool | Description |
|---|---|
| `create_rectangle` | Create a rectangle in a plane. |
| `create_spiral` | Create a helix or flat spiral. |
| `create_nurbs_curve` | Create a NURBS curve from control points. |
| `create_blend_curve` | Create a smooth blend curve between two curves at given parameters. |
| `fillet_curves` | Fillet two curves with a radius. |
| `divide_curve` | Divide a curve into N equal segments and return the points. |
| `divide_curve_length` | Divide a curve at intervals of a given arc length. |
| `close_curve` | Close an open curve. |
| `reverse_curve` | Reverse the direction of a curve. |
| `rebuild_curve` | Rebuild a curve with a target degree and point count. |
| `curve_closest_point` | Find the closest point on a curve to a test point. |
| `evaluate_curve` | Evaluate the position, tangent, and curvature of a curve at a parameter. |
| `curve_start_end_points` | Return the start and end points of a curve. |
| `join_curves` | Join a set of curves into a single polycurve where endpoints match. |
| `explode_curves` | Explode a polycurve into its component segments. |

---

### Extended Selection

| Tool | Description |
|---|---|
| `select_all_objects` | Select all objects in the document. |
| `deselect_all_objects` | Deselect all objects. |
| `invert_selection` | Invert the current selection. |
| `select_by_type` | Select all objects of a given geometry type (e.g. `Curve`, `Brep`, `Mesh`, `Point`). |
| `select_by_layer` | Select all objects on a named layer. |
| `select_by_name` | Select all objects with a given name. |
| `delete_selected_objects` | Delete all currently selected objects. |
| `get_last_created_objects` | Return the GUIDs of the most recently created objects. |

---

### Extended Material Tools

| Tool | Description |
|---|---|
| `set_material_color` | Set the diffuse color of an object's material using RGB. Creates a new material if the object uses the default. |
| `set_material_transparency` | Set the transparency (0.0–1.0) of an object's material. |
| `set_material_shine` | Set the shininess (0.0–255.0) of an object's material. |
| `add_material_to_layer` | Create a material and assign it to a layer by name. |

---

### Extended View Tools

| Tool | Description |
|---|---|
| `zoom_extents` | Zoom the active viewport to show all objects. `all_views=true` zooms all viewports simultaneously. |
| `zoom_selected` | Zoom the active viewport to fit the current selection. |
| `zoom_to_object` | Zoom the active viewport to frame a specific object by GUID. (McNeel RhinoMCP compatible) |
| `zoom_to_layer` | Zoom the active viewport to frame all objects on a named layer. (McNeel RhinoMCP compatible) |
| `get_view_info` | Return camera position, target, lens length, and display mode for a viewport. |
| `set_display_mode` | Set the display mode of a viewport (`Wireframe`, `Shaded`, `Rendered`, `Ghosted`, `XRay`, etc.). |
| `add_named_view` | Save the current viewport state as a named view. |
| `restore_named_view` | Restore a previously saved named view. |

---

### Extended Document Tools

| Tool | Description |
|---|---|
| `enable_redraw` | Enable or disable viewport redraw. Disable before batch operations, re-enable when done. |
| `set_unit_system` | Set the document unit system (`Millimeters`, `Centimeters`, `Meters`, `Inches`, `Feet`, etc.). |

---

### Reference-Compatible Aliases

These tools use the public RhinoMCP wire protocol names so agents trained on other MCP servers work without prompting:

`create_object`, `create_objects`, `get_objects`, `get_object_info`, `get_selected_objects_info`, `modify_object`, `modify_objects`, `delete_object`, `select_objects`, `create_layer`, `delete_layer`, `get_or_set_current_layer`, `capture_viewport`, `undo`, `redo`, `execute_rhinoscript_python_code`, `execute_rhinocommon_csharp_code`, `get_document_summary`, `send_rhinomcp_plugin_command`, `get_commands`, `run_command`

---

## Skills

The [`skills/`](skills/README.md) folder holds ready-made prompt packages in the Agent Skills format for Claude Code, Codex CLI, and ChatGPT Skill Creator. Each one was written against the tool source, so it carries the real parameter names, return keys, and the `applied` / `not_applied` reporting each tool returns.

| Skill | Covers |
|---|---|
| `rhino-mcp-basics` | Response shapes, units, risky defaults, undo, scripting rules |
| `rhino-text-to-3d` | Brief to model, with the full `create_rhino_scene` type table |
| `rhino-image-to-3d` | Trace plans and PDFs to scale, or generate meshes from photos |
| `rhino-document-reading` | PDFs, drawings, spreadsheets, SVG, Word, images |
| `rhino-grasshopper-parametric` | GH1 and GH2 build loops, script components, plugin helpers |
| `rhino-landscape-site-plan` | Terrain, paths, water, planting blocks, schedules |
| `rhino-urban-massing-studio` | Typologies, FAR, solar, AI renders, reports |
| `rhino-rendering-and-export` | Materials, HDRI, views, image capture, file export |

Install by copying the folders into `~/.claude/skills/` or `~/.codex/skills/`, or paste a `SKILL.md` into ChatGPT Skill Creator. `uv run python scripts/check_skill_tools.py` verifies every tool name a skill mentions exists in the code.

---

## Studio Pipeline Env Vars

```bash
export ANTHROPIC_API_KEY=sk-ant-...          # design language generation
export FAL_KEY=...                            # AI renders (fal.ai account)
export DOCRAPTOR_API_KEY=...                  # PDF export (optional)
export URBAN_AGENT_S3_BUCKET=my-bucket       # cloud storage (optional)
export AWS_ACCESS_KEY_ID=...                  # S3 credentials (optional)
export AWS_SECRET_ACCESS_KEY=...              # S3 credentials (optional)
```

Without `DOCRAPTOR_API_KEY` the report is saved as HTML at `~/.urbanagent/reports/`. Without AWS credentials the PDF is saved locally at `~/.urbanagent/reports/`. The pipeline always completes and always produces output.

---

## Building the Plugin from Source

```bash
# Prerequisites: .NET 8 SDK
dotnet --version   # should be 8.x

# Build and copy to Rhino (macOS auto-copies via PostBuild)
./scripts/build-plugin.sh

# Package as Yak for distribution
./scripts/package-plugin.sh
```

The `build-plugin.sh` script runs `dotnet build` inside `rhino_plugin/RhinoMCPPlugin/`. On macOS, the PostBuild step automatically copies the `.rhp` to `/Applications/Rhino 8.app/Contents/PlugIns/`. Restart Rhino after each build to load the new version.
The `package-plugin.sh` script stages release assets in `rhino_plugin/release/` and includes both the direct-install `rhino-mcp.rhp` and the `rhino-mcp-*.yak` package.
GitHub release automation is available in `.github/workflows/release-plugin.yml`; it publishes both artifacts from a self-hosted macOS runner with Rhino installed.

---

## Running Tests

```bash
# Unit tests (no Rhino required — runs in ~0.4s)
uv run python -m pytest tests/test_tools_unit.py tests/test_plugin_files.py -v

# Server metadata test (starts the MCP server process, no Rhino required)
uv run python -m pytest tests/test_server_metadata.py -v

# Security gates and remote host guard tests
uv run python -m pytest tests/test_security_gates.py -v

# Keep-alive TCP connection tests
uv run python -m pytest tests/test_plugin_client.py -v

# Urban + Studio Pipeline tests (no Rhino required — all external APIs mocked)
uv run python -m pytest tests/test_urban_unit.py tests/test_urban_design_language.py \
    tests/test_urban_renders.py tests/test_urban_report.py tests/test_urban_pipeline.py -v

# Grasshopper integration tests (requires Rhino running with MCPStart active)
uv run python -m pytest tests/test_gh_integration.py -v -m integration

# All non-integration tests
uv run python -m pytest tests/ \
    --ignore=tests/test_integration.py \
    --ignore=tests/test_gh_integration.py \
    --ignore=tests/test_studio_pipeline_integration.py \
    --ignore=tests/test_gh_intelligence_integration.py \
    -q

# Confirm the current non-integration test count
uv run python -m pytest tests/ \
    --ignore=tests/test_integration.py \
    --ignore=tests/test_gh_integration.py \
    --ignore=tests/test_studio_pipeline_integration.py \
    --ignore=tests/test_gh_intelligence_integration.py \
    --collect-only -q
```

The non-integration collection currently includes 512 tests plus five subtests. Integration tests auto-skip cleanly if the plugin socket is not reachable.

---

## References

- [Rhino Developer Docs](https://developer.rhino3d.com/)
- [RhinoCommon API](https://developer.rhino3d.com/api/rhinocommon/)
- [RhinoScriptSyntax API](https://developer.rhino3d.com/api/RhinoScriptSyntax/)
- [Grasshopper SDK](https://developer.rhino3d.com/api/grasshopper/html/723c01da-9986-4db2-8f53-6f3a7494df75.htm)
- [RhinoCode CLI](https://developer.rhino3d.com/guides/scripting/advanced-cli/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Yak Package Manager](https://developer.rhino3d.com/guides/yak/)
- [Pufferfish](https://www.food4rhino.com/en/app/pufferfish)
- [Weaverbird](https://www.food4rhino.com/en/app/weaverbird)
- [LunchBox](https://www.food4rhino.com/en/app/lunchbox)
- [Anemone](https://www.food4rhino.com/en/app/anemone)
- [Human](https://www.food4rhino.com/en/app/human)
- [Elefront](https://www.food4rhino.com/en/app/elefront)
- [Kangaroo Physics](https://www.food4rhino.com/en/app/kangaroo-physics)
- [Ladybug Tools](https://www.ladybug.tools/)
- [V-Ray for Rhino](https://www.chaos.com/vray/rhino)
- [Enscape](https://enscape3d.com)
- [VisualARQ](https://www.visualarq.com)
- [Lands Design](https://www.lands-design.com)

# Rhino MCP

Control Rhino 3D from Claude, Cursor, Codex, and any other MCP-capable AI tool. Create geometry, manipulate objects, run Grasshopper definitions, manage layers and materials, install plugins, bake results, generate AI 3D models, and more — all through natural language.

---

## Table of Contents

- [Quick Start](#quick-start)
  - [Path A — Manual setup with Claude Desktop](#path-a--manual-setup-with-claude-desktop)
  - [Path B — Docker setup with Claude Desktop](#path-b--docker-setup-with-claude-desktop)
- [What You Can Do](#what-you-can-do)
- [Urban Massing Workflow](#urban-massing-workflow)
- [Studio Pipeline](#studio-pipeline)
- [Architecture Overview](#architecture-overview)
- [Requirements](#requirements)
- [Installation](#installation)
  - [1. Install the Rhino Plugin](#1-install-the-rhino-plugin)
  - [2. Install the Python MCP Server](#2-install-the-python-mcp-server)
  - [3. Configure API Keys (Studio Pipeline)](#3-configure-api-keys-studio-pipeline)
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
  - [Docker / HTTP Transport](#docker--http-transport)
- [Backend Selection](#backend-selection)
- [Environment Variables](#environment-variables)
- [Remote Host Support](#remote-host-support)
- [Telemetry](#telemetry)
- [Third-Party Plugin Support](#third-party-plugin-support)
  - [Automatic Installation via Yak](#automatic-installation-via-yak)
  - [Manual Installation](#manual-installation)
  - [File-based Installation](#file-based-installation)
  - [Checking Plugin Status](#checking-plugin-status)
- [All 216 Tools](#all-216-tools)
  - [Plugin Management](#plugin-management)
  - [Grasshopper — Canvas](#grasshopper--canvas)
  - [Grasshopper — Parameters](#grasshopper--parameters)
  - [Grasshopper — Solution & Baking](#grasshopper--solution--baking)
  - [Grasshopper — Definition Management](#grasshopper--definition-management)
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
  - [Scripting](#scripting)
  - [Boolean Operations](#boolean-operations)
  - [Curve Operations](#curve-operations)
  - [AI Generation](#ai-generation)
  - [Studio Pipeline Tools](#studio-pipeline-tools)
  - [Asset Libraries (Poly Haven & Sketchfab)](#asset-libraries-poly-haven--sketchfab)
  - [VisualARQ (Architectural BIM)](#visualarq-architectural-bim)
  - [Lands Design (Landscape)](#lands-design-landscape)
  - [Reference-Compatible Aliases](#reference-compatible-aliases)
- [Studio Pipeline Env Vars](#studio-pipeline-env-vars)
- [Building the Plugin from Source](#building-the-plugin-from-source)
- [Running Tests](#running-tests)
- [References](#references)

---

## Quick Start

Two paths to get up and running. Both require the Rhino plugin — only the server setup differs.

---

### Path A — Manual setup with Claude Desktop

**Prerequisites:** Rhino 7 or 8, Python 3.10+, [uv](https://docs.astral.sh/uv/) (`pip install uv`), git.

#### Step 1 — Install the Rhino plugin

The plugin runs a socket server inside Rhino that the MCP server talks to.

```bash
# macOS
cp rhino_plugin/package/rhino-mcp.rhp \
   "/Applications/Rhino 8.app/Contents/PlugIns/"
```

```powershell
# Windows
Copy-Item rhino_plugin\package\rhino-mcp.rhp `
  "$env:ProgramFiles\Rhino 8\Plug-ins\"
```

Then in Rhino: **Tools → Options → Plug-ins → Install** and select the `.rhp` file.

#### Step 2 — Clone the repo and install the Python server

```bash
git clone https://github.com/your-org/rhino-mcp.git
cd rhino-mcp
uv sync          # installs all Python dependencies from uv.lock
```

Verify it works:

```bash
uv run python -m rhmcp --help
```

You should see the argument list printed. If you see it, the server is ready.

#### Step 3 — Tell Claude Desktop how to start the server

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

#### Step 4 — Start Rhino and activate the plugin

1. Open Rhino 3D.
2. In the Rhino command line, type `MCPStart` and press Enter.
3. You should see: `RhinoMCP: Listening on 127.0.0.1:1999`

> **Tip:** Add `MCPStart` to Rhino's startup commands so it activates automatically:  
> *Rhino Options → General → Command Lists → startup commands*

#### Step 5 — Restart Claude Desktop and start using it

Fully quit Claude Desktop (don't just close the window) and reopen it. Claude Desktop reads the config on launch, spawns the MCP server in the background, and the 216 Rhino tools become available automatically.

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

Docker bundles the Python server and all dependencies into a self-contained image. No Python, no uv, no cloning required on the machine running the container.

**Prerequisites:** Rhino 7 or 8, Docker Desktop.

#### Step 1 — Install the Rhino plugin

Same as Path A Step 1 above. The plugin must run inside Rhino on your machine — it cannot be containerized.

#### Step 2 — Build and run the Docker image

```bash
# Clone just to get the Dockerfile (or copy it manually)
git clone https://github.com/your-org/rhino-mcp.git
cd rhino-mcp

# Build
docker build -t rhino-mcp .

# Run — paste your real API keys
docker run -d \
  -p 8000:8000 \
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
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e FAL_KEY="..." \
  --name rhino-mcp \
  rhino-mcp
```

Verify the server is up:

```bash
curl http://localhost:8000/
```

#### Step 3 — Tell Claude Desktop to connect via URL

In HTTP mode the server is already running — Claude Desktop connects to it rather than spawning it. Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rhino": {
      "url": "http://localhost:8000/"
    }
  }
}
```

No `command`, no `args`, no `env` — the API keys were set when you ran the container.

#### Step 4 — Start Rhino and activate the plugin

Same as Path A Step 4. Type `MCPStart` in Rhino and confirm it shows `Listening on 127.0.0.1:1999`.

#### Step 5 — Restart Claude Desktop and start using it

Fully quit and reopen Claude Desktop. It connects to the running container and the 216 tools appear.

**Connection flow:**
```
Claude Desktop → HTTP → localhost:8000 (Docker container)
                               ↓
                    host.docker.internal:1999 (Rhino plugin)
                               ↓
                          Rhino 3D geometry
```

---

## What You Can Do

| Category | Examples |
|---|---|
| **Plugin Management** | Check if a plugin is installed, automatically install via Yak, install from `.gha`/`.rhp`/`.rhi` files, list all loaded plugins, introspect any plugin's commands |
| **Grasshopper** | Place components, draw wires, set sliders/panels, run solutions, bake geometry to Rhino doc, add script components |
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
| **Objects** | Select, move, rotate, scale, rename, change layer/color, delete, undo/redo |
| **Layers** | List, create, delete, set current, change color/visibility/lock |
| **Materials** | Create, assign, and delete standard and PBR materials; set environment maps; configure render settings |
| **V-Ray** | Start/stop IPR, render to file, create and apply V-Ray materials, add lights (Rectangle/Sphere/IES/Dome/Sun), set HDRI environment, configure GI presets, export `.vrscene` |
| **Enscape** | Launch Enscape window, capture screenshots, export 360° panoramas, export standalone executables, set time of day and atmosphere, save named views |
| **Views** | Capture the active viewport — **Claude receives the image and can see the scene**; set named views, camera position, target, and lens length; save PNG to disk |
| **Files** | Save and export to `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg` |
| **Scripting** | Run arbitrary Rhino Python (RhinoScriptSyntax / RhinoCommon) or C# (Roslyn) directly |
| **AI Generation** | Generate 3D models from text or images via Hunyuan3D, import results into Rhino |
| **Asset Libraries** | Search and import Poly Haven textures/HDRIs, download Sketchfab models |
| **VisualARQ (BIM)** | Create walls, doors, windows, slabs, columns, stairs, railings, levels; query BIM properties; export IFC |
| **Lands Design** | Place plants and trees from species library, generate terrain from contours, create paths and water features, export plant schedules |
| **Remote host** | Run Rhino on a separate workstation or VM — set `RHINO_MCP_BIND_HOST=0.0.0.0` on the Rhino machine and point the MCP client at its IP |
| **Telemetry** | Optional per-call usage log (JSONL on disk, opt-in, never leaves the machine) for debugging slow tools and measuring usage patterns |

---

## Urban Massing Workflow

Rhino MCP includes an agent-led urban massing workflow for early site studies. Claude can collect a short brief, choose a typology, open the matching Grasshopper definition under `grasshopper/urban/`, set named sliders, solve the definition, bake the generated geometry into Rhino, and read back planning metrics.

Supported massing typologies are `tower`, `podium_tower`, `courtyard`, `perimeter_block`, and `street_grid`. The workflow is driven by `urban_generate_massing`, which accepts the site origin, site dimensions, and typology-specific parameter overrides such as floor count, setbacks, footprint size, program mix, road width, or grid rotation. Results are baked to layers like `Urban::Massing::tower`.

Use `urban_get_metrics` after generation to retrieve the active definition's reported `gfa_m2`, `far`, `unit_count_est`, and `open_space_pct`. Use `urban_update_param` for iterative slider changes, `urban_capture_and_evaluate` to pair metrics with a viewport image, `urban_run_analysis` for the Ladybug solar-analysis definition, and `urban_clear_massing` to remove generated layers.

The PRD-facing API is also available with product-level names: `parse_urban_prompt`, `generate_site_layout`, `generate_massing`, `calculate_urban_metrics`, `optimize_plan`, `render_urban_preview`, `export_model`, `save_project_version`, and `create_urban_scheme`. The orchestrator accepts GeoJSON-style `site_boundary` input and derives site dimensions from its bbox/coordinates when the prompt does not include explicit dimensions.

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
  RhinoMCPPlugin (.rhp)          ← runs inside Rhino 7/8
       │
       ▼
  Rhino 3D + Grasshopper
```

The **Python MCP server** exposes all tools to the AI client via the Model Context Protocol over stdio. It connects to the **Rhino plugin** over a local TCP socket. All Rhino-side operations (including all Grasshopper canvas mutations) execute on Rhino's main UI thread via `RhinoApp.InvokeOnUiThread`, keeping the document consistent and undo-safe.

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

### 1. Install the Rhino Plugin

The plugin is a `.rhp` file that runs a TCP socket server inside Rhino. There are three ways to install it.

#### Option A — Copy the pre-built `.rhp` directly (fastest)

```bash
# macOS
cp rhino_plugin/package/rhino-mcp.rhp \
   "/Applications/Rhino 8.app/Contents/PlugIns/"
```

```powershell
# Windows — adjust Rhino version path as needed
Copy-Item rhino_plugin\package\rhino-mcp.rhp `
  "C:\Program Files\Rhino 8\Plug-ins\"
```

Then restart Rhino. The plugin loads automatically on startup.

#### Option B — Install via Yak (Rhino's package manager)

1. Open Rhino.
2. Run the command `_PackageManager` in the Rhino command line.
3. Click **Install from file…** and select `rhino_plugin/package/rhino-mcp-0.2.0-rh8_17-any.yak`.
4. Restart Rhino when prompted.

#### Option C — Build from source

```bash
# Requires .NET 8 SDK
dotnet build -c Release rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj
```

The build output is placed at `rhino_plugin/RhinoMCPPlugin/bin/Release/net8.0/rhino-mcp.rhp` and is automatically copied to `/Applications/Rhino 8.app/Contents/PlugIns/` on macOS by the PostBuild step.

---

### 2. Install the Python MCP Server

```bash
# Clone the repo
git clone https://github.com/your-org/rhino-mcp.git
cd rhino-mcp

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

Docker bundles the Python server and all dependencies into a self-contained image. You still need the Rhino plugin (step 1) — it runs inside Rhino on your machine and cannot be containerized.

**Build the image:**

```bash
docker build -t rhino-mcp .
```

**Run it:**

```bash
docker run -d \
  -p 8000:8000 \
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
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  rhino-mcp
```

Once running, point your AI client at `http://localhost:8000/` — see [Docker / HTTP Transport](#docker--http-transport) below.

**Both paths work independently.** Existing manual stdio setups are unaffected by the Docker option.

---

## Starting the Service

### Step 1 — Start Rhino and activate the plugin

1. **Open Rhino 3D** (version 7 or 8).
2. In the Rhino command line, type:

   ```
   MCPStart
   ```

   You should see a message like:
   ```
   RhinoMCP: Listening on 127.0.0.1:1999
   ```

3. *(Optional — for Grasshopper tools)* Open Grasshopper:

   ```
   Grasshopper
   ```

   Grasshopper must be open at least once before GH tools will work. After the first open, `gh_new_definition` will open it automatically on demand.

> **Tip:** To start the socket server automatically every time Rhino opens, add `MCPStart` to your Rhino startup commands:  
> *Rhino Options → General → Command Lists → Add to startup commands*

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
> - **Studio Pipeline API keys** (`ANTHROPIC_API_KEY`, `FAL_KEY`, etc.) — these are used by the **MCP server process itself** to call external services when you ask it to generate design language, produce AI renders, or export PDFs. Your app login is not shared with the server process — it needs its own credentials.
>
> **If you only use Rhino tools** (geometry, Grasshopper, layers, materials, rendering, BIM) you need **no API keys at all** in the `env` block — just the three connection variables:
> ```json
> "env": { "RHINO_MCP_BACKEND": "plugin", "RHINO_MCP_HOST": "127.0.0.1", "RHINO_MCP_PORT": "1999" }
> ```
> Add API keys only if you want Studio Pipeline features. See [Studio Pipeline Env Vars](#studio-pipeline-env-vars) for the full list.

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

With Docker running, use the URL form instead:

```json
{
  "mcpServers": {
    "rhino": {
      "url": "http://localhost:8000/"
    }
  }
}
```

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

With Docker: add a server with type `sse` and URL `http://localhost:8000/`.

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

With Docker running, use `"type": "http"` and `"url": "http://localhost:8000/"` instead of `command`/`args`.

---

### Codex CLI

```bash
RHINO_MCP_BACKEND=plugin \
RHINO_MCP_HOST=127.0.0.1 \
RHINO_MCP_PORT=1999 \
ANTHROPIC_API_KEY="sk-ant-..." \
FAL_KEY="..." \
codex --mcp-server "uv run --directory /path/to/rhino-mcp python -m rhmcp"
```

---

### Docker / HTTP Transport

When the server is running in Docker (or started manually with `--transport http`), AI clients connect to a URL instead of spawning a process. API keys are set on the container at `docker run` time — no `env` block needed in the client config.

**Claude Desktop** — edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rhino": {
      "url": "http://localhost:8000/"
    }
  }
}
```

**Claude Code (CLI):**

```bash
claude --mcp-server "rhino:http://localhost:8000/"
```

**Cursor** — Settings → MCP → Add Server, type `http`, URL `http://localhost:8000/`.

**Windsurf** — add a server with type `sse` and URL `http://localhost:8000/`.

**GitHub Copilot (VS Code)** — in `.vscode/mcp.json` use `"type": "http"` and `"url": "http://localhost:8000/"`.

**Codex CLI:**

```bash
codex --mcp-server "http://localhost:8000/"
```

> The manual stdio setup and Docker/HTTP setup can coexist. Point different clients at whichever they prefer — the Rhino plugin on port 1999 handles both.

---

## Backend Selection

The MCP server supports three backend modes:

| Mode | Description | Use case |
|---|---|---|
| `plugin` | TCP socket to RhinoMCPPlugin | **Recommended.** Full feature set including Grasshopper. Works with Rhino 7 and 8. |
| `rhinocode` | Rhino 8.11+ official CLI | No plugin required. Does not support Grasshopper. Slower for complex operations. |
| `auto` | Try plugin first, fall back to rhinocode | Good default when plugin availability is uncertain. |

Set the backend via environment variable:

```bash
export RHINO_MCP_BACKEND=plugin    # or rhinocode, auto
```

Use `get_rhino_backend_status` from any AI client to check which backends are currently reachable.

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
| `RHINOCODE` | *(auto-detected)* | Path to rhinocode binary if not on `PATH` |
| `RHINO_MCP_TELEMETRY` | *(unset)* | Set to `1`, `true`, or `yes` to enable usage telemetry |
| `RHINO_MCP_TELEMETRY_LOG` | `~/.rhino_mcp_telemetry.jsonl` | Path for the telemetry log file (JSONL format) |

### Rhino Plugin (C# side)

| Variable | Default | Description |
|---|---|---|
| `RHINO_MCP_BIND_HOST` | `127.0.0.1` | IP address the Rhino plugin binds its TCP listener to. Set to `0.0.0.0` to accept connections from any network interface (required for remote AI clients). Must be set in Rhino's environment before `MCPStart` is run. |

---

## Remote Host Support

The Python MCP server and the Rhino plugin communicate over TCP. By default both sides use `127.0.0.1` (loopback), so Rhino and the AI client must be on the same machine. Setting `RHINO_MCP_BIND_HOST` lets the plugin accept connections from any address, enabling Claude (or any MCP client) to drive Rhino on a dedicated render workstation, a cloud VM, or across a local network.

> **Prerequisite:** Remote host support requires the C# plugin to be rebuilt from source. Run `./scripts/build-plugin.sh` and restart Rhino before following the steps below. The pre-built `.rhp` in the repo binds to loopback only.

---

### Bind address values

| `RHINO_MCP_BIND_HOST` value | Effect |
|---|---|
| *(not set)* or `127.0.0.1` | Loopback only — local connections, most secure (default) |
| `0.0.0.0` | All IPv4 interfaces — accepts connections from any machine on the network |
| `192.168.x.x` (specific IP) | Only the named interface — useful on multi-homed machines |
| `::` | All IPv6 interfaces |

---

### Step 1 — Set the bind address on the Rhino machine

The env var must be present in the environment that launches the Rhino process. Setting it in a terminal after Rhino is already open has no effect.

**macOS — temporary (current terminal session only):**
```bash
export RHINO_MCP_BIND_HOST=0.0.0.0
open -a "Rhino 8"
```

**macOS — persistent (survives reboots, affects all Rhino launches):**
```bash
# Write a launchd environment variable
launchctl setenv RHINO_MCP_BIND_HOST 0.0.0.0
# Takes effect for new processes — restart Rhino if it's already running.
# To remove later:
launchctl unsetenv RHINO_MCP_BIND_HOST
```

**Windows — temporary (current PowerShell session):**
```powershell
$env:RHINO_MCP_BIND_HOST = "0.0.0.0"
& "C:\Program Files\Rhino 8\System\Rhino.exe"
```

**Windows — persistent (user-level, survives reboots):**
```powershell
[System.Environment]::SetEnvironmentVariable(
    "RHINO_MCP_BIND_HOST", "0.0.0.0", "User")
# Restart Rhino after setting.
# To remove:
[System.Environment]::SetEnvironmentVariable(
    "RHINO_MCP_BIND_HOST", $null, "User")
```

Then in Rhino: run `MCPStart`. The confirmation message shows the actual bind address:
```
Rhino MCP server started on 0.0.0.0:1999
```

Run `MCPStatus` at any time to confirm:
```
Rhino MCP server running on 0.0.0.0:1999
```

---

### Step 2 — Open the firewall port on the Rhino machine

```bash
# macOS Application Firewall — allow Rhino to accept incoming connections
sudo /usr/libexec/ApplicationFirewall/socketfilterfw \
     --add "/Applications/Rhino 8.app/Contents/MacOS/Rhino"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw \
     --unblockapp "/Applications/Rhino 8.app/Contents/MacOS/Rhino"
```

```powershell
# Windows Defender Firewall — open port 1999 inbound
netsh advfirewall firewall add rule `
    name="RhinoMCP" protocol=TCP dir=in `
    localport=1999 action=allow
```

---

### Step 3 — Configure the MCP client

Set `RHINO_MCP_HOST` to the IP address of the Rhino machine. The Python MCP server (which runs on the client machine) connects to that IP on port 1999.

```json
{
  "mcpServers": {
    "rhino": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/rhino-mcp", "python", "-m", "rhmcp"],
      "env": {
        "RHINO_MCP_BACKEND": "plugin",
        "RHINO_MCP_HOST": "192.168.1.50",
        "RHINO_MCP_PORT": "1999"
      }
    }
  }
}
```

---

### Step 4 — Verify connectivity

From the client machine, before involving the AI client at all:

```bash
# macOS / Linux — check that port 1999 is open and responding
nc -zv 192.168.1.50 1999
# Expected: Connection to 192.168.1.50 port 1999 [tcp/*] succeeded!

# Windows
Test-NetConnection -ComputerName 192.168.1.50 -Port 1999
# Expected: TcpTestSucceeded : True
```

If the connection is refused, recheck the bind address in `MCPStatus` and confirm the firewall rule is active.

---

> **Security note:** Port 1999 accepts unauthenticated JSON commands that can execute arbitrary Python inside Rhino. Only expose it on trusted private networks. Never open it to the public internet. If you need remote access over the internet, tunnel through SSH (`ssh -L 1999:localhost:1999 user@rhino-host`) rather than exposing the port directly.

---

## Telemetry

Telemetry is **opt-in** and **disabled by default**. No data leaves your machine — events are written to a local JSONL file only. When disabled (the default), the interceptor is never installed and adds zero overhead to tool calls.

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
{"ts":"2026-05-08T18:30:00.123456+00:00","tool":"capture_rhino_view","ms":142,"ok":true,"error":null}
{"ts":"2026-05-08T18:30:05.001234+00:00","tool":"gh_run_solution","ms":3201,"ok":true,"error":null}
{"ts":"2026-05-08T18:30:08.999999+00:00","tool":"vray_render","ms":87,"ok":false,"error":"RuntimeError: V-Ray for Rhino is not installed or not loaded."}
```

| Field | Type | Description |
|---|---|---|
| `ts` | ISO-8601 UTC string | Timestamp of invocation start |
| `tool` | string | MCP tool name exactly as registered |
| `ms` | integer | Wall-clock duration in milliseconds (includes Rhino round-trip time for plugin-backend calls) |
| `ok` | boolean | `true` if the tool returned normally; `false` if it raised an exception |
| `error` | string \| null | `"ExceptionClass: message"` when `ok` is `false`; `null` otherwise |

> `ms` measures total time from when the MCP client called the tool to when the Python server returned the result. For plugin-backend tools this includes the full TCP round-trip to Rhino plus any Rhino-side computation. It is a useful proxy for "how long did the user wait."

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

## All 216 Tools

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
| `gh_wb_extrude_face` | `mesh_instance_guid`, `distance=0.5`, `canvas_x`, `canvas_y` | Place an **Extrude Face** component. Extrudes each face outward by `distance`. |

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
| `create_rhino_geometry` | Create a single geometric object. Supported types: `box`, `sphere`, `cylinder`, `cone`, `torus`, `line`, `polyline`, `arc`, `circle`, `ellipse`, `curve` (free-form NURBS), `surface` (from points), `plane`, `text`, `point`, `mesh`, `extrusion`, `brep` (from existing), and more. |
| `create_rhino_scene` | Create multiple objects in one call. Accepts a list of the same object descriptors as `create_rhino_geometry`. |
| `get_rhino_objects` | List objects in the document with optional filters by type, layer, name, or bounding box. |
| `get_rhino_object_info` | Get detailed info about a specific object by GUID: type, layer, name, bounding box, material, and geometry properties. |

---

### Object Editing & Selection

| Tool | Description |
|---|---|
| `select_rhino_objects` | Select objects by GUID, name, layer, type, or color. Supports multi-select. |
| `get_selected_rhino_objects` | Return the GUIDs and basic properties of all currently selected objects. |
| `transform_rhino_objects` | Move, rotate, or scale objects. Specify object GUIDs or operate on the current selection. |
| `edit_rhino_object_attributes` | Change name, layer, display color, linetype, or print color on one or more objects. |
| `delete_rhino_objects` | Delete objects by GUID or delete the current selection. |
| `undo_rhino` | Undo the last N operations (default 1). |
| `redo_rhino` | Redo the last N undone operations. |

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
| `create_pbr_material` | Create a physically-based material with base color, metallic, roughness, opacity, and texture maps (albedo, roughness, metallic, normal, displacement, AO). |
| `assign_pbr_material_to_objects` | Assign a named PBR material to one or more objects by GUID. |
| `get_pbr_material_info` | Return the PBR properties and texture paths of a named material. |
| `list_pbr_materials` | List all PBR materials in the document. |
| `set_environment_map` | Load an HDR or EXR file as the render environment (background, lighting, reflections). |
| `set_render_settings` | Configure render resolution, background color, transparent background, ambient occlusion, ground plane, and shadows. |
| `render_to_image` | Trigger a Rhino render and save/return the result as a file path and optional base-64 PNG. |

---

### V-Ray Rendering

Requires [V-Ray for Rhino](https://www.chaos.com/vray/rhino) to be installed and licensed. Each tool checks that V-Ray is loaded and returns `{"success": false, "message": "..."}` if it is not.

| Tool | Parameters | Description |
|---|---|---|
| `vray_start_ipr` | — | Start V-Ray **Interactive Production Rendering** in the active viewport. IPR updates the render bucket live as you modify the scene. |
| `vray_stop_ipr` | — | Stop the running IPR session. |
| `vray_render` | `output_path`, `width=1920`, `height=1080`, `quality_preset="medium"` | Trigger a full V-Ray render and save the result to `output_path`. `quality_preset`: `low` \| `medium` \| `high` \| `ultra`. |
| `vray_create_material` | `name`, `diffuse_color=[r,g,b]`, `roughness=0.5`, `metalness=0.0`, `ior=1.5`, `opacity=1.0` | Create a V-Ray material via RhinoCommon. `diffuse_color` values are 0–255. |
| `vray_apply_material` | `object_ids=[...]`, `material_name` | Assign a named V-Ray material to a list of Rhino objects by GUID. |
| `vray_add_light` | `light_type="Rectangle"`, `position=[x,y,z]`, `target=[x,y,z]`, `intensity=1.0`, `color=[r,g,b]` | Add a V-Ray light. `light_type`: `Rectangle` \| `Sphere` \| `IES` \| `Dome` \| `Sun`. |
| `vray_set_environment` | `hdri_path`, `intensity=1.0`, `rotation_degrees=0.0` | Set the V-Ray dome/environment light to an HDRI file. Opens the V-Ray Options dialog — `hdri_path`, `intensity`, and `rotation_degrees` are returned for reference. |
| `vray_set_render_settings` | `width=1920`, `height=1080`, `aa_subdivs=4`, `gi_preset="interior"`, `time_limit_seconds=0` | Configure render resolution, AA subdivisions, and GI preset. `gi_preset`: `interior` \| `exterior` \| `studio`. `time_limit_seconds=0` disables the time limit. |
| `vray_export_vrscene` | `output_path`, `compressed=False` | Export the current scene as a `.vrscene` file for V-Ray Standalone or distributed rendering. |

---

### Enscape Real-Time Rendering

Requires [Enscape](https://enscape3d.com) to be installed and licensed. Each tool checks that Enscape is loaded and returns `{"success": false, "message": "..."}` if it is not.

| Tool | Parameters | Description |
|---|---|---|
| `enscape_start` | — | Launch the Enscape real-time rendering window from the current Rhino viewport. |
| `enscape_screenshot` | `output_path`, `width=1920`, `height=1080` | Capture a high-resolution screenshot from the current Enscape view and save it to `output_path`. |
| `enscape_export_panorama` | `output_path`, `resolution="4K"` | Export a 360° equirectangular panorama. `resolution`: `2K` \| `4K` \| `8K`. |
| `enscape_export_standalone` | `output_path` | Export the scene as a self-contained Enscape standalone executable (`.exe`) for sharing without requiring an Enscape license on the viewer's machine. |
| `enscape_set_time_of_day` | `hour=12`, `minute=0` | Set the sun position by time of day. `hour`: 0–23, `minute`: 0–59. |
| `enscape_set_atmosphere` | `cloud_density=0.3`, `wind_speed=0.0`, `precipitation_type="none"` | Configure atmosphere. `cloud_density`: 0.0–1.0. `precipitation_type`: `none` \| `rain` \| `snow`. Opens Visual Settings — values are passed for reference. |
| `enscape_create_view` | `name` | Save the current Enscape camera position as a named view that can be recalled later. |

---

### Views & Viewport

| Tool | Parameters | Description |
|---|---|---|
| `set_rhino_view` | `view="Perspective"`, `camera=[x,y,z]`, `target=[x,y,z]`, `lens=None` | Activate a named view or set camera position, target, and lens length. Common view names: `Perspective`, `Top`, `Front`, `Right`. |
| `capture_rhino_view` | `path=None`, `width=1200`, `height=900` | **Capture the active viewport and return it as a visual image the AI can see.** `path` is optional — omit it for in-memory capture only. When `path` is provided the PNG is also saved to disk. Returns `[{metadata}, Image]` so the AI client renders the image inline. |

---

### Document & File I/O

| Tool | Description |
|---|---|
| `get_rhino_document_summary` | Return document metadata: object count by type and layer, materials, units, tolerance, and named views. |
| `save_rhino_document` | Save the active document to its current path. |
| `export_rhino_document` | Export to a specified file format. Supported: `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.stp`, `.dxf`, `.dwg`, `.pdf`. |

---

### Scripting

| Tool | Description |
|---|---|
| `execute_rhino_python` | Run arbitrary Python code inside Rhino with full RhinoScriptSyntax and RhinoCommon access. Returns the `result` variable if set. |
| `execute_rhino_csharp` | Run arbitrary C# code inside Rhino via Roslyn scripting. Returns the last expression value or a `result` variable. |
| `run_rhino_command` | Execute a Rhino command macro string (e.g. `_Box 0,0,0 1,1,1`). |
| `search_rhino_docs` | Full-text search of bundled Rhino scripting notes. |
| `get_rhinoscript_docs` | Look up RhinoScriptSyntax module-level documentation. |
| `search_rhinoscript_functions` | Search RhinoScriptSyntax function reference by name or keyword. |
| `get_rhinoscript_function` | Get the full docstring for a specific RhinoScriptSyntax function. |

---

### Boolean Operations

| Tool | Description |
|---|---|
| `boolean_union` | Unite two or more Brep/solid objects. |
| `boolean_difference` | Subtract one set of solids from another. |
| `boolean_intersection` | Compute the intersection volume of two solids. |

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
| `generate_3d_from_text` | Submit a text prompt to Hunyuan3D to generate a 3D mesh. Returns a job ID for polling. |
| `generate_3d_from_images` | Submit one or more reference images to Hunyuan3D for image-to-3D generation. |
| `poll_generation_job` | Check the status of a generation job and retrieve the result URL when complete. |
| `import_generated_model` | Download a generated mesh and import it into the active Rhino document. |
| `get_generation_services_status` | Check which AI generation services (Hunyuan3D, etc.) are reachable. |

---

### Studio Pipeline Tools

Requires env vars — see [Studio Pipeline Env Vars](#studio-pipeline-env-vars). All cloud services are optional; the pipeline degrades gracefully to local output without credentials.

**Design Language** (`ANTHROPIC_API_KEY` required):

| Tool | Description |
|---|---|
| `urban_generate_design_language` | Call Claude API to generate a complete design language: style name, facade vocabulary, material palette with hex codes, colour story, landscape character, diffusion prompt, and executive summary. Stores result in session state. |
| `urban_update_design_language` | Patch a single field of the current design language (e.g. `style_name`, `facade_vocabulary`, `material_palette`). Re-derives the diffusion prompt when style or materials change. |
| `urban_get_design_language` | Return the current session design language dict, or `{"set": false}` if none generated yet. |

**AI Renders** (`FAL_KEY` required):

| Tool | Description |
|---|---|
| `urban_render_views` | Capture one or more named Rhino viewports and AI-render them using fal.ai FLUX.1 ControlNet img2img. Uses the session design language as the diffusion prompt. Retries with reduced strength on first failure; falls back to raw Rhino captures on double failure. Returns list of `RenderResult` dicts with `original_b64`, `rendered_b64`, `prompt_used`, `seed`. |
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

VisualARQ adds parametric BIM objects (walls, slabs, columns, stairs, etc.) directly inside Rhino. All VisualARQ objects are standard Rhino objects with embedded BIM data — no separate file format required.

| Tool | Parameters | Description |
|---|---|---|
| `varq_create_wall` | `start_pt=[x,y,z]`, `end_pt=[x,y,z]`, `height=3.0`, `style_name="Basic Wall"`, `layer=None` | Create a VisualARQ wall between two 3D points. `height` is in document units. The wall uses the named style from the VisualARQ style library. |
| `varq_add_opening` | `wall_id`, `opening_type="window"`, `position_along_wall=0.5`, `width=1.0`, `height=2.0`, `style_name=None` | Add a window or door to an existing wall. `opening_type`: `window` \| `door`. `position_along_wall` is a 0.0–1.0 fraction of the wall's length from the start point. |
| `varq_create_slab` | `boundary_curve_ids=[...]`, `thickness=0.3`, `style_name="Basic Slab"`, `layer=None` | Create a VisualARQ floor or ceiling slab from one or more closed boundary curves. |
| `varq_create_column` | `position=[x,y,z]`, `height=3.0`, `style_name="Basic Column"`, `layer=None` | Create a structural column at a 3D point with the specified height. |
| `varq_create_stair` | `start_pt=[x,y,z]`, `direction=[x,y,z]`, `width=1.2`, `rise=0.175`, `run=0.28`, `story_count=1`, `style_name="Basic Stair"` | Create a stair. `rise` is the vertical step height (m), `run` is the horizontal tread depth (m), `direction` is a unit vector for stair direction. |
| `varq_create_railing` | `path_curve_id`, `height=1.0`, `style_name="Basic Railing"` | Create a railing along a curve path. The curve can be straight, curved, or follow a stair profile. |
| `varq_set_level` | `name`, `elevation=0.0` | Create or update a VisualARQ building level (floor/storey). Levels control visibility, object assignment, and IFC storey export. |
| `varq_export_ifc` | `output_path`, `ifc_version="IFC4"` | Export the entire model to IFC format. `ifc_version`: `IFC2x3` \| `IFC4`. VisualARQ objects export with full IFC type mappings (IfcWall, IfcSlab, IfcColumn, etc.). |
| `varq_get_object_properties` | `object_id` | Get VisualARQ type, style, level assignment, and IFC properties for any object by GUID. Returns `{"type": "...", "style": "...", "level": "..."}`. |
| `varq_list_styles` | `object_type="wall"` | List available VisualARQ styles for a given object type. `object_type`: `wall` \| `door` \| `window` \| `slab` \| `column` \| `stair` \| `railing`. |

---

### Lands Design (Landscape)

Requires [Lands Design](https://www.lands-design.com) to be installed and licensed. Each tool checks that Lands Design is loaded. Install instructions: `install_plugin("Lands Design")`.

Lands Design adds landscape-specific objects (plants, terrain, paths, water) directly inside Rhino, with a built-in plant species database and seasonal display.

| Tool | Parameters | Description |
|---|---|---|
| `lands_place_plant` | `plant_name`, `position=[x,y,z]`, `rotation_degrees=0.0`, `scale=1.0` | Place a plant from the Lands Design library at a position. `plant_name` must match a name from the Lands Design plant database. |
| `lands_place_tree` | `species_name`, `position=[x,y,z]`, `trunk_height=2.0`, `canopy_radius=3.0` | Place a tree from the Lands Design species library. `trunk_height` and `canopy_radius` are in document units. |
| `lands_create_terrain` | `boundary_curve_id`, `source_type="contours"`, `source_id=None` | Generate a terrain surface from existing geometry. `source_type`: `contours` (interpolates from contour curves) \| `points` (from a point cloud). `source_id` is the GUID of the source geometry. |
| `lands_create_path` | `centerline_curve_id`, `width=2.0`, `surface_type="Asphalt"` | Create a path or road surface along a curve. `surface_type` controls the material display (e.g. `Asphalt`, `Gravel`, `Grass`, `Paving`). |
| `lands_create_water` | `boundary_curve_id`, `water_level_z=0.0` | Create a Lands Design water surface within a closed boundary curve. `water_level_z` sets the elevation of the water plane. |
| `lands_get_plant_database` | `search_query=""`, `category=""` | Browse the Lands Design plant species database. Filter by search term and/or category (e.g. `"Trees"`, `"Shrubs"`, `"Groundcovers"`). Use this to find exact plant names before calling `lands_place_plant`. |
| `lands_set_season` | `season="summer"` | Set the display season for all Lands Design plants and trees in the scene. `season`: `spring` \| `summer` \| `autumn` \| `winter`. Affects 3D representation and texture. |
| `lands_export_plant_list` | `output_path`, `format="csv"` | Export a plant schedule (quantity takeoff) from the current model. `format`: `csv` \| `xlsx`. The schedule includes species name, count, size parameters, and location data. |

---

### Reference-Compatible Aliases

These tools use the public RhinoMCP wire protocol names so agents trained on other MCP servers work without prompting:

`create_object`, `create_objects`, `get_objects`, `get_object_info`, `get_selected_objects_info`, `modify_object`, `modify_objects`, `delete_object`, `select_objects`, `create_layer`, `delete_layer`, `get_or_set_current_layer`, `capture_viewport`, `undo`, `redo`, `execute_rhinoscript_python_code`, `execute_rhinocommon_csharp_code`, `get_document_summary`, `send_rhinomcp_plugin_command`

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

---

## Running Tests

```bash
# Unit tests (no Rhino required — runs in ~0.4s)
uv run python -m pytest tests/test_tools_unit.py tests/test_plugin_files.py -v

# Server metadata test (starts the MCP server process, no Rhino required)
uv run python -m pytest tests/test_server_metadata.py -v

# Urban + Studio Pipeline tests (no Rhino required — all external APIs mocked)
uv run python -m pytest tests/test_urban_unit.py tests/test_urban_design_language.py \
    tests/test_urban_renders.py tests/test_urban_report.py tests/test_urban_pipeline.py -v

# Grasshopper integration tests (requires Rhino running with MCPStart active)
uv run python -m pytest tests/test_gh_integration.py -v -m integration

# All non-integration tests (169 tests, ~1.7s)
uv run python -m pytest tests/ --ignore=tests/test_gh_integration.py -v
```

The integration tests auto-skip cleanly if the plugin socket is not reachable.

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

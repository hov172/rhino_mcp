# Rhino MCP

Control Rhino 3D from Claude, Cursor, Codex, and any other MCP-capable AI tool. Create geometry, manipulate objects, run Grasshopper definitions, manage layers and materials, bake results, generate AI 3D models, and more — all through natural language.

---

## Table of Contents

- [What You Can Do](#what-you-can-do)
- [Architecture Overview](#architecture-overview)
- [Requirements](#requirements)
- [Installation](#installation)
  - [1. Install the Rhino Plugin](#1-install-the-rhino-plugin)
  - [2. Install the Python MCP Server](#2-install-the-python-mcp-server)
- [Starting the Service](#starting-the-service)
  - [Step 1 — Start Rhino and activate the plugin](#step-1--start-rhino-and-activate-the-plugin)
  - [Step 2 — Start the MCP server](#step-2--start-the-mcp-server)
- [Connecting AI Clients](#connecting-ai-clients)
  - [Claude Desktop](#claude-desktop)
  - [Claude Code (CLI)](#claude-code-cli)
  - [Cursor](#cursor)
  - [Codex CLI](#codex-cli)
- [Backend Selection](#backend-selection)
- [Environment Variables](#environment-variables)
- [All 114 Tools](#all-114-tools)
  - [Grasshopper — Canvas](#grasshopper--canvas)
  - [Grasshopper — Parameters](#grasshopper--parameters)
  - [Grasshopper — Solution & Baking](#grasshopper--solution--baking)
  - [Grasshopper — Definition Management](#grasshopper--definition-management)
  - [Geometry Creation](#geometry-creation)
  - [Object Editing & Selection](#object-editing--selection)
  - [Layers](#layers)
  - [Materials](#materials)
  - [PBR Materials & Rendering](#pbr-materials--rendering)
  - [Views & Viewport](#views--viewport)
  - [Document & File I/O](#document--file-io)
  - [Scripting](#scripting)
  - [Boolean Operations](#boolean-operations)
  - [Curve Operations](#curve-operations)
  - [AI Generation](#ai-generation)
  - [Asset Libraries (Poly Haven & Sketchfab)](#asset-libraries-poly-haven--sketchfab)
  - [Reference-Compatible Aliases](#reference-compatible-aliases)
- [Building the Plugin from Source](#building-the-plugin-from-source)
- [Running Tests](#running-tests)

---

## What You Can Do

| Category | Examples |
|---|---|
| **Grasshopper** | Place components, draw wires, set sliders/panels, run solutions, bake geometry to Rhino doc, add script components |
| **Geometry** | Create boxes, spheres, cylinders, cones, tori, curves, surfaces, meshes, text, arcs, ellipses, planes, and more |
| **Modeling** | Boolean union/difference/intersection, loft, extrude, sweep, offset, pipe, project/intersect/split curves |
| **Objects** | Select, move, rotate, scale, rename, change layer/color, delete, undo/redo |
| **Layers** | List, create, delete, set current, change color/visibility/lock |
| **Materials** | Create, assign, and delete standard and PBR materials; set environment maps; configure render settings |
| **Views** | Set named views, capture viewport images, set camera position |
| **Files** | Save and export to `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg` |
| **Scripting** | Run arbitrary Rhino Python (RhinoScriptSyntax / RhinoCommon) or C# (Roslyn) directly |
| **AI Generation** | Generate 3D models from text or images via Hunyuan3D, import results into Rhino |
| **Asset Libraries** | Search and import Poly Haven textures/HDRIs, download Sketchfab models |

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
| Rhino 3D | **Rhino 7** (Rhino 8 recommended; script components require Rhino 8) |
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
cp rhino_plugin/package/RhinoMCPPlugin.rhp \
   "/Applications/Rhino 8.app/Contents/PlugIns/"
```

```powershell
# Windows — adjust Rhino version path as needed
Copy-Item rhino_plugin\package\RhinoMCPPlugin.rhp `
  "C:\Program Files\Rhino 8\Plug-ins\"
```

Then restart Rhino. The plugin loads automatically on startup.

#### Option B — Install via Yak (Rhino's package manager)

1. Open Rhino.
2. Run the command `_PackageManager` in the Rhino command line.
3. Click **Install from file…** and select either:
   - `rhino_plugin/package/rhino-mcp-0.1.0-rh8_30-any.yak` (Rhino 8)
   - `rhino_plugin/package/rhino-mcp-0.1.0-any-any.yak` (any version)
4. Restart Rhino when prompted.

#### Option C — Build from source

```bash
# Requires .NET 8 SDK
./scripts/build-plugin.sh
```

The build output is placed at `rhino_plugin/RhinoMCPPlugin/bin/Debug/net8.0/RhinoMCPPlugin.rhp` and is automatically copied to `/Applications/Rhino 8.app/Contents/PlugIns/` on macOS by the PostBuild step.

---

### 2. Install the Python MCP Server

```bash
# Clone the repo
git clone https://github.com/your-org/rhino-mcp.git
cd rhino-mcp

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

Verify the install:

```bash
uv run python -m rhmcp --help
```

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
        "RHINO_MCP_PORT": "1999"
      }
    }
  }
}
```

Replace `/path/to/rhino-mcp` with the absolute path to the cloned repo. Restart Claude Desktop after editing.

---

### Claude Code (CLI)

Add to your project's `.mcp.json` or `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "rhino": {
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

Or start Claude Code with the server inline:

```bash
claude --mcp-server "rhino:uv run --directory /path/to/rhino-mcp python -m rhmcp"
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
      "RHINO_MCP_PORT": "1999"
    }
  }
}
```

---

### Codex CLI

```bash
RHINO_MCP_BACKEND=plugin \
RHINO_MCP_HOST=127.0.0.1 \
RHINO_MCP_PORT=1999 \
codex --mcp-server "uv run --directory /path/to/rhino-mcp python -m rhmcp"
```

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

| Variable | Default | Description |
|---|---|---|
| `RHINO_MCP_BACKEND` | `auto` | Backend mode: `plugin`, `rhinocode`, or `auto` |
| `RHINO_MCP_HOST` | `127.0.0.1` | Plugin socket host |
| `RHINO_MCP_PORT` | `1999` | Plugin socket port |
| `RHINO_MCP_SOCKET_TIMEOUT` | `15.0` | Socket timeout in seconds |
| `RHINOCODE` | *(auto-detected)* | Path to rhinocode binary if not on `PATH` |

---

## All 114 Tools

### Grasshopper — Canvas

Requires the plugin backend and Grasshopper to be open in Rhino.

| Tool | Description |
|---|---|
| `gh_search_components` | Search the Grasshopper component library by name, category, or description. Returns component GUIDs needed for `gh_add_component`. |
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

### Views & Viewport

| Tool | Description |
|---|---|
| `set_rhino_view` | Activate a named view or set camera position, target, and lens length. |
| `capture_rhino_view` | Capture the active viewport to a PNG file. Returns the file path and optional base-64 string. |

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

### Reference-Compatible Aliases

These tools use the public RhinoMCP wire protocol names so agents trained on other MCP servers work without prompting:

`create_object`, `create_objects`, `get_objects`, `get_object_info`, `get_selected_objects_info`, `modify_object`, `modify_objects`, `delete_object`, `select_objects`, `create_layer`, `delete_layer`, `get_or_set_current_layer`, `capture_viewport`, `undo`, `redo`, `execute_rhinoscript_python_code`, `execute_rhinocommon_csharp_code`, `get_document_summary`, `send_rhinomcp_plugin_command`

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

# Grasshopper integration tests (requires Rhino running with MCPStart active)
uv run python -m pytest tests/test_gh_integration.py -v -m integration

# All non-integration tests
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

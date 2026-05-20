# Changelog

All notable changes to rhino-mcp are documented here.
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **Execution safety gates** — three env vars let operators disable arbitrary-code
  execution tools at the server level:
  - `RHINO_MCP_ENABLE_RHINOSCRIPT=0` — disables `execute_rhino_python` and
    `execute_rhinoscript_python_code`. Default: `1` (enabled).
  - `RHINO_MCP_ENABLE_CSHARP=0` — disables `execute_rhino_csharp` and
    `execute_rhinocommon_csharp_code`. Default: `1` (enabled).
  - `RHINO_MCP_ENABLE_RUN_COMMAND=0` — disables `run_rhino_command` and
    `run_command`. Default: `1` (enabled).
  Disabled tools return `{"ok": false, "error_code": "TOOL_DISABLED"}` rather
  than raising, so clients receive a clear message instead of a server error.
- **Remote host guard** — the MCP server now refuses to connect to a non-loopback
  Rhino plugin host unless `RHINO_MCP_ALLOW_REMOTE=1` is set. Prevents
  accidental connections to production Rhino instances or LAN hosts. Docker
  deployments have this set automatically via the Dockerfile.
- **Keep-alive TCP connection**: the Python client now reuses a single persistent
  TCP connection to the Rhino plugin instead of opening a new connection per
  tool call. Eliminates per-call TCP handshake overhead; transparent reconnect
  on stale connections (e.g. after Rhino restart). Disable with
  `RHINO_MCP_KEEPALIVE=0` if needed.
- **C# plugin keep-alive**: `RhinoMcpServer` now handles multiple requests on
  the same connection and accepts new connections concurrently (fire-and-forget
  per client task), so a long-lived Python connection never blocks new connects.
- Retry delay reduced from 500 ms to 50 ms — faster recovery from transient
  connection failures on localhost.

---

## [0.14.0] — 2026-05-20

### Added
- Compact mode is now **on by default**: 3 meta-tools (`list_rhino_tools`,
  `describe_rhino_tool`, `call_rhino_tool`) instead of all full schemas. Cuts
  per-request token cost from ~52k to ~1.5k with no capability loss.
  Use `--no-compact` or `RHMCP_COMPACT=0` to load all schemas upfront.

---

## [0.13.0] — 2026-05-19

### Added

- **Tool profiles** — new `--profile` CLI flag (and `RHMCP_PROFILE` env var) selects which tool modules are loaded at startup. Cuts context window usage significantly for users who don't need specialty plugins.

  Available profiles:

  | Profile | Tools | ~Tokens |
  |---------|-------|---------|
  | `full` *(default)* | 360 | ~52k |
  | `core` | 194 | ~28k |
  | `grasshopper` | 277 | ~40k |
  | `rendering` | 225 | ~35k |
  | `urban` | 226 | ~34k |
  | `bim` | 212 | ~31k |

  `core` covers geometry creation, layers, transforms, booleans, curves, surfaces, meshes, materials, export, annotations, and document management — everything needed for standard Rhino modeling. Specialty profiles extend core with their respective plugin tools.

  Usage: `rhino-mcp --profile core` or `RHMCP_PROFILE=grasshopper rhino-mcp`

### Improved

- **Trimmed tool descriptions** — stripped verbose `Parameters`/`Args`/`Notes` sections from all 360 tool docstrings. These sections duplicated information already present in the JSON schema and inflated token usage unnecessarily. The `full` profile now costs ~52k tokens vs. ~62k before (16% reduction even without a profile).

---

## [0.12.2] — 2026-05-19

### Added

- **`snap_to_grid` for geometry creation** — new optional parameter on `create_rhino_geometry` and `create_rhino_scene`. When set (e.g. `0.5` for a 6-inch grid, `1.0` for a 1-foot grid), all point coordinates are rounded to the nearest multiple before geometry is created. Eliminates the "almost aligned" problem when tracing floor plans from PDFs.

- **`calibrate_pdf_scale`** — new tool that computes the true pixel-to-real-world scale from two identified points in a rendered PDF page and their known real-world distance. Corrects for print-to-fit scaling that makes the printed scale annotation inaccurate. Returns `px_per_real_unit` / `real_units_per_px` in the same format as `read_pdf(scale_hint=...)`.

- **`read_pdf_vectors`** — new tool that extracts vector paths (lines, rectangles) directly from the PDF drawing layer using pymupdf's `page.get_drawings()`. For PDFs exported from CAD/BIM tools (Revit, AutoCAD, Rhino), returns exact line segment coordinates with zero pixel estimation. Gracefully returns a `no_vectors` error for scanned/raster-only PDFs. When `real_units_per_px` is supplied, coordinates are also returned in real-world units.

- **`extract_pdf_dimensions`** — new tool that extracts dimension annotation strings and their bounding box positions from the PDF text layer. Parses imperial (`20'-6"`, `3'-0"`), metric (`3000mm`, `4.5m`), and bare numeric formats. Each match includes `bbox_px`, `center_px`, and optionally `center_real` for spatial cross-checking of traced geometry.

- **`validate_rhino_geometry`** — new tool that checks a set of objects (or all curves in the document) for common tracing errors: gaps between endpoints, non-orthogonal wall angles, duplicate segments, and zero-length curves. Returns a structured issue report with severity levels. `auto_fix=True` closes gaps by snapping endpoints to midpoint and deletes duplicate segments.

- **`align_geometry_to_point`** — new tool that moves all specified objects (or all document objects) so that a given source point lands exactly on a target point. One call to anchor traced geometry to model-space origin after PDF tracing.

---

## [0.12.1] — 2026-05-18

### Added

- **`read_pdf` scale hint** — new `scale_hint` parameter accepts a drawing scale annotation string (`"1/4\" = 1'"`, `"1/8\" = 1'-0\""`, `"1:100"`, `"1:50"`, etc.) and computes the pixel-to-real-world mapping for each rendered page. The response now includes `px_per_real_unit`, `real_units_per_px`, `real_width`, `real_height`, and `real_unit` (`"feet"` for imperial, `"meters"` for metric ratio formats), enabling accurate coordinate mapping from PDF pixel space to model space.

### Fixed

- **JSON-to-Python boolean/null injection bug (server-only)** — `json.dumps()` was used to embed Python values directly into source code strings sent to Rhino's IronPython runtime. JSON tokens `true`, `false`, and `null` are not valid Python identifiers, causing `NameError` on any tool call that passed a boolean or `None` parameter through the rhinocode fallback path. Fixed across 16 tool modules and 4 export modules (`export_visual`, `export_cad`, `export_print`, `export_images`) — 40+ injection sites total. All replaced with `repr()` / `{!r}`, which produces valid Python literals (`True`, `False`, `None`). Plugin-socket users were unaffected; the bug consistently broke the rhinocode fallback path.
- **`set_unit_system` crash on any call** — `Rhino.UnitSystem.None_` was evaluated eagerly inside a dict literal, throwing `AttributeError: 'type' object has no attribute 'None_'` even when setting valid units like `Millimeters`. Fixed with `getattr` fallback and changed guard from `if us is None` to `if name not in _MAP`.
- **`create_rhino_geometry` box ignores `corner` and dimension params** — the box handler only read `center` + `size`; passing `corner` + `x_size`/`y_size`/`z_size` (or their aliases `width`/`depth`/`height`) silently fell back to a unit cube at the origin. Added full support for the corner + dimensions calling convention and `width`/`depth`/`height` as accepted aliases for `x_size`/`y_size`/`z_size`.
- **Plugin autostart** — set `PlugInLoadTime.AtStartup` on the plugin class. Without this, Rhino defaulted to `WhenNeeded`, meaning the TCP socket server only started after the user manually ran `MCPStart` for the first time. Now the server is ready immediately when Rhino opens, before any user interaction.

---

## [0.12.0] — 2026-05-17

### Added

**Grasshopper Intelligence — 7 new tools**

Works on **Rhino 8 (GH1)**:
- `gh_get_canvas_analysis` — canvas metrics (component count, wire count, clusters), wire-crossing estimate, complexity score, and actionable refactor suggestions
- `gh_get_graph_data` — full adjacency snapshot (nodes + edges) used by layout and migration tools
- `gh_refactor_canvas` — GH1 de-spaghettify: re-layout to reduce crossings, auto-group clusters, `dry_run=True` preview mode
- `gh1_export_migration_data` — serialise GH1 canvas to migration-ready JSON; flags which components have a known GH2 equivalent

Requires **Rhino 9 + GH2** (return a clear error on Rhino 8):
- `gh_migrate_to_gh2` — place GH2 equivalents for all mapped GH1 components and wire them; lists unmapped components
- `gh2_move_component` — move a GH2 component to new canvas coordinates by GUID
- `gh2_add_group` — create a named group around specified components on the GH2 canvas

**New C# plugin handlers**
- `gh_get_canvas_analysis`, `gh_get_graph_data`, `gh1_export_migration_data` — read-only GH1 analysis (GHIntelligenceHandlers.cs)
- `gh2_move_component`, `gh2_add_group` — GH2 write operations (GH2IntelligenceHandlers.cs)

**New data file**
- `src/rhmcp/data/gh1_to_gh2_map.yml` — 20 GH1→GH2 type mappings used by the migration tool

**Tests**
- `tests/test_gh_intelligence.py` — 26 unit tests (all non-integration)
- `tests/test_gh_intelligence_integration.py` — 9 integration tests (require live Rhino)

Brings total tool count to **353** (up from 347).

---

## [0.11.0] — 2026-05-17

### Added

**Grasshopper 2 (GH2) support — 11 new tools**

- `gh2_start` — launch the Grasshopper 2 editor
- `gh2_get_canvas_graph` — full snapshot of the active GH2 canvas (components, wires, volatile data samples)
- `gh2_apply_graph` — atomically place components and wire them in one call; returns placed GUIDs and wired count
- `gh2_place_component` — place a GH2 component by type name or component GUID
- `gh2_place_slider` — place a GH2 Number Slider with min/max/value/decimals
- `gh2_connect` — wire a single output to an input
- `gh2_connect_many` — wire multiple connections at once; continues past individual failures
- `gh2_describe_component` — get metadata (category, description, input/output param names and types) for any component
- `gh2_search_components` — search available GH2 components by name, nickname, or description
- `gh2_solve_graph` — expire and re-solve the active GH2 canvas
- `gh2_clear_canvas` — clear all objects from the active GH2 canvas (requires `confirm=True`)

All GH2 handlers use runtime reflection — no compile-time dependency on Grasshopper2.dll. Two-tier graceful degradation: returns a clear error when GH2 is not loaded. **Requires Rhino 9** — Grasshopper 2 is not available in stable Rhino 8.

**Multi-Rhino instance management**

- `get_rhino_instances` — discover all running Rhino processes via slot registry JSON files in the system temp dir
- `launch_rhino` — launch a new Rhino process and wait for it to announce its slot (uses `RHINO_MCP_RHINO_PATH` env var or auto-detected install)
- C# `SlotAnnouncer` — on TCP listener start, writes `{pid}.json` to `Path.GetTempPath()/rhino-mcp-slots/` with pid, host, port, version, rhino_version, started_at
- Python `slot_registry.py` — `discover()`, `get()`, `wait_for_slot()` mirror the C# slot dir via `tempfile.gettempdir()`
- `backend.py` — routes `plugin_result()` via slot registry when `rhino_id` is provided or `RHINO_MCP_USE_SLOT_REGISTRY=1` is set

**`host_app` field on ping / health_check**

- `ping` response now includes `host_app` — returns the process name when Rhino is hosted (e.g. Rhino.Inside Revit/AutoCAD); returns `"Rhino"` otherwise
- `health_check()` in `plugin_client.py` surfaces `host_app` from the ping result

**New environment variables**
- `RHINO_MCP_USE_SLOT_REGISTRY` — set to `1` to always route via slot registry (default: off)
- `RHINO_MCP_RHINO_PATH` — override path to the Rhino executable used by `launch_rhino`

**Tests**
- 334 tests passing (was 262 before this release)
- New `test_gh2.py` (27 tests), `test_rhinoinside.py` (7 tests), `test_slot_registry.py` (21 tests), `test_rhino_launcher.py` (14 tests), `test_install_scripts.py` (14 tests)

### Security hardening (comprehensive — 8-round audit)

**HTTP transport (Python MCP server):**
- Bearer token auth middleware — random 64-hex token generated at startup, printed to stderr; required on all requests except `/health` and OPTIONS preflight
- CORS restricted to `localhost` / `127.0.0.1` only (was wildcard)
- Rate limiting — 120 req/min sliding window per token (configurable via `RHINO_MCP_RATE_LIMIT_RPM`); exempt: `/health`, OPTIONS
- `/health` endpoint returns `{"status": "ok"}` — used by Docker and Cloud Run health checks

**Input validation & injection prevention:**
- Macro injection: `sanitise_rhino_path()` applied at all Rhino macro / `rs.Command()` / `RhinoApp.RunScript()` call sites where user-supplied paths are embedded
- C# verbatim string escaping: corrected `replace('"', '""')` throughout (was `replace('"', '\\"')` — wrong for `@"..."` strings)
- Python code injection: `layer_prefix` and other user strings embedded into IronPython scripts now use `repr()` instead of raw f-string interpolation
- `material_name` validated against `^[\w\s.\-]{1,128}$` regex; `object_id` validated as UUID before C# interpolation
- `install_plugin`: restricted to `.rhi`, `.rhp`, `.yak` file types with path resolution

**Path traversal & file safety:**
- Zip Slip prevention: `safe_extractall()` blocks symlinks and path escapes (Poly Haven / Sketchfab downloads)
- `read_*` document tools: `_validate_read_path()` restricts file reads to `~` or `RHINO_MCP_READ_ROOTS`
- Urban `export_path` and `save_project_version` directory restricted to home or temp via `_safe_export_path()`
- AI generation download filename: regex allowlist `[A-Za-z0-9_.\-]` applied before `os.path.join()`
- Sketchfab `model_uid` validated as 32 hex chars before URL and path use
- API-supplied filenames: `os.path.basename()` applied

**SSRF prevention:**
- `validate_download_url()`: blocks private IPs, loopback, IPv4-mapped IPv6, non-HTTPS URLs; DNS fail-closed
- Applied to all download paths: AI generation, Poly Haven, Sketchfab, fal.ai; redirect loops revalidate every hop
- cairosvg (`read_svg`): custom `url_fetcher` blocks all external resource loading including `file://` and `http://`

**Other fixes:**
- Jinja2 `autoescape=True` in urban PDF report template
- API keys removed from `_JOB_STORE` (were accidentally persisted in job metadata)
- `_JOB_STORE` bounded to 1000 entries (OrderedDict LRU) + `threading.Lock()` for concurrent access
- Input clamping: `clamp()` applied to DPI, image dimensions, quality, max rows, paragraphs
- Code execution tools: 200 KB length cap
- Prompt / text inputs: 8000 char cap; style parameters: 2000 char cap
- API error bodies truncated to 200 chars before returning to clients
- Telemetry error strings truncated to 120 chars
- `rhinocode` binary path validated with `os.path.isfile` + `os.X_OK` before use

**Plugin TCP security:**
- Pre-shared key (PSK) authentication via `RHINO_MCP_PLUGIN_SECRET` environment variable
- Plugin validates PSK using SHA-256 + `CryptographicOperations.FixedTimeEquals` (constant-time) before dispatching any command
- Python client automatically includes the secret in every request when the env var is set
- Rhino console warning printed when binding to a non-loopback address without a secret configured
- Backward compatible: if `RHINO_MCP_PLUGIN_SECRET` is not set, all connections accepted (existing localhost setups unaffected)

**New environment variables:**
- `RHINO_MCP_PLUGIN_SECRET` — shared secret between Rhino plugin and Python server (required for network use)
- `RHINO_MCP_READ_ROOTS` — colon-separated paths the `read_*` tools may access (default: `~`)
- `RHINO_MCP_RATE_LIMIT_RPM` — HTTP rate limit (default: 120 requests/minute)

**Tests:**
- New `test_security.py` with 31 tests covering all security helpers

---

## [0.9.0] — 2026-05-11

### Added

- `import_file` gains `post_import_display` parameter — automatically configures viewport display
  mode, background, grid, and zoom on every import based on file extension:
  - `dwg` / `dxf` / `svg` / `pdf` / `eps` → Wireframe mode, solid black background, grid and axes
    hidden, black/near-black layers and per-object colours flipped to white so AutoCAD layer
    colours are immediately visible with no manual steps.
  - `fbx` / `obj` / `3ds` / `stl` / `3mf` / `ply` / `wrl` → Shaded mode, zoom to extents.
  - `iges` / `step` / `3dm` / `skp` → Shaded mode, zoom to extents.
  - Pass `"none"` to skip. Default is `"auto"` (detect from extension).

### Fixed

- **`System.Byte` hex format bug** — material names generated as `MCP_Color_722X722X752X` due to
  `{:02X}.format(System.Byte)` producing decimal output in IronPython. Fixed in `_IMPORT_SCRIPT`
  and `_NORMALIZE_SCRIPT` to use `"%02X" % int(channel)`.
- **Plugin version strings out of sync** — `AssemblyInformationalVersion` was hardcoded to `0.2.0`
  (causing a yak build warning on every release) and the `ping` response reported `0.6.0`. Both
  now track the release version.
- **Docker base image compatibility** — `libgdk-pixbuf2.0-0` renamed to
  `libgdk-pixbuf-xlib-2.0-0` in Debian Trixie (`python:3.13-slim`); Dockerfile updated.

---

## [0.8.0] — 2026-05-10

### Added

**Import pipeline — full material, texture, and color fidelity (3 new tools)**

- `import_file` — import any Rhino-supported format (3DS, FBX, OBJ, STL, STEP, IGES, DXF, DWG, 3DM)
  and automatically normalize import-baked materials so colors and textures display correctly
  in Shaded and Rendered modes immediately after import.  Accepts `show_textures_in_viewport`
  to switch to Rendered mode automatically when texture files are found.
- `normalize_imported_objects` — bulk-normalize objects already in the scene whose materials were
  baked at import time.  Optionally filter to specific layers.
- `set_object_display_color` — set an object's color so it shows correctly in **both** Shaded and
  Rendered viewport modes by creating a matching `MCP_Color_RRGGBB` render material.
  Handles import-baked objects automatically (delete+readd to bust display cache).

**Export tool modules (11 new tools across 5 modules)**

- `export_step`, `export_iges`, `export_dwg` — CAD interchange formats with engineering-specific
  options (AP protocol, tolerance, 2D/3D geometry control)
- `export_obj`, `export_fbx`, `export_glb` — visual/game-engine formats with material, texture
  coordinate, Draco compression, and embedding controls
- `export_3dm` — native Rhino export with version targeting, selective object export by layer/type,
  and embedded notes
- `export_stl`, `export_3mf` — 3D printing formats with unit, tolerance, and binary/ASCII controls
- `convert_image`, `export_viewport_image` — image conversion and viewport capture with display
  mode, resolution, quality, and format controls

**Total: 334 tools** (up from 320 in v0.7.0)

### Fixed

- **Import material fidelity** — all four texture slots preserved during normalization: bitmap
  (diffuse), bump/normal, environment/reflection, transparency/opacity.  Texture paths resolved
  with fallback search: raw path → source file directory → `textures/`, `maps/`, `tex/`, `images/`
  subdirectories.  Material properties preserved: DiffuseColor, Shine, Transparency, SpecularColor,
  EmissionColor.
- **Color visibility in Shaded mode** — `create_rhino_geometry`, `edit_rhino_object_attributes`,
  and `modify_object` previously set `rs.ObjectColor()` which only affects wireframe edges.
  All three now create and assign a `MCP_Color_RRGGBB` render material so face fill shows the
  correct color in Shaded and Rendered modes.
- **GLB export texture coordinates** — `export_glb` was binding `ExportTextureCoordinates` to
  the `export_materials` flag (copy-paste error), silently disabling UV export whenever materials
  were disabled.  Fixed to use the correct `export_textures` flag.
- **AI-generated model import** — `import_generated_model` (Hyper3D Rodin, Hunyuan3D-2) now runs
  material normalization after the C# `doc.Import()` call so imported mesh colors work immediately.
  Result dict includes `materials_normalized` count.
- **Shared MCP_ material mutation** — `_get_or_create_material()` in the materials tool previously
  returned the index of a shared `MCP_Color_RRGGBB` material; callers then mutated its DiffuseColor
  in place, corrupting the color for all objects sharing it.  Now creates a fresh per-object
  material when the existing assignment points to a shared MCP_ material.
- **Summary false positives** — `get_rhino_document_summary` no longer counts already-normalized
  `MCP_Color_` / `MCP_Tex_` objects in `baked_import_material_count`.
- **Normalize idempotency** — `normalize_imported_objects` and the inline normalize in
  `import_file` skip objects whose material already starts with `MCP_`, preventing double
  processing.
- **`set_object_display_color` wasted delete+readds** — already-normalized `MCP_` objects now go
  through the faster `ModifyAttributes` path instead of delete+readd.

---

## [0.7.0] — 2026-05-09

### Fixed
- **C1** — `execute_python` now promotes inner `ok: false` script results to the outer response so callers see failures correctly
- **H1** — Added GUID/guid_list validation to all tools in `advanced_geometry.py` and `mesh_ops.py`
- **H2** — `_run()` helpers in `boolean_operations`, `curve_operations`, and `advanced_geometry` now strip the `err` key from locals() before sending payload to Rhino
- **H4** — Boolean intersection loop variables renamed to `current_results`/`next_obj` for clarity
- **H5** — `measure_area` now correctly handles mesh objects via `rs.MeshArea()`
- **M1** — Removed `.strip()` from `validate.guid()` — whitespace-padded GUIDs now correctly fail validation
- **M2** — `manage_rhino_layer` validates `action` against the allowed set (`list`, `create`, `update`, `delete`, `current`) and returns `INVALID_VALUE` early
- **M3** — `get_rhino_objects` validates `limit > 0` and `offset >= 0`
- **M4** — `_wrap_with_revert` calls `expandtabs(4)` before indenting so tab-indented user code is handled correctly
- **M5** — `create_patch` validates `u_spans` and `v_spans` are positive integers
- **M6** — Removed unreachable dead-code block in `run_plugin_or_python`
- **M7** — Removed redundant `import time` inside `health_check` (already imported at module level)
- **M8** — `extrude_curve` result dict now includes `"capped": bool`
- **M9** — Plugin `OSError` during auto-mode fallback is captured as `plugin_error` in the rhinocode response
- **L1** — Distance op uses `rs.Distance()` instead of manual `math.sqrt`
- **L4** — `set_object_material` validates the object GUID; `set_rhino_view` validates `camera`/`target` coordinates
- **L5** — Bounding box failure response now includes `"error_code": "COMPUTATION_FAILED"`

### Changed
- Tool count corrected to **320** (was documented as 321)

---

## [0.6.0] — 2026-05-09

### Added
- **Script syntax tests** — `test_script_syntax.py` AST-validates every `_SCRIPT` block across all tool modules at CI time
- **Integration test scaffold** — `test_integration.py` with 13 live tests (auto-skip when no Rhino reachable); covers health check, Python execution, sphere/box/line CRUD, layer CRUD, move, user text, group, distance, bounding box
- **GitHub Actions CI** — `.github/workflows/ci.yml` runs unit + smoke + script-syntax tests on Python 3.10/3.11/3.12 on every push/PR; separate ruff lint job
- **One-command installers** — `scripts/install.sh` (macOS/Linux) and `scripts/install.ps1` (Windows PowerShell)

### Fixed
- Ruff lint violations across 8 tool modules (unused imports, bare except clauses, f-strings without placeholders, trailing semicolons)

---

## [0.5.0] — 2026-05-09

### Added
- **Auto-start socket server** — plugin starts TCP server on Rhino load; `MCPStart` remains as manual fallback
- **`MCPHelp` command** — opens GitHub documentation in the default browser from Rhino
- **`MCPStop` command** — stop the socket server without restarting Rhino
- **`list_tool_categories`** — discovery tool listing all 49 categories with per-category counts
- **`validate.py`** — shared input validators (guid, color, coordinate, layer_name, positive, non_negative, guid_list) wired into all major tool modules
- **Connection retry** — exponential backoff on socket OSError (default 2 retries, configurable via `RHINO_MCP_SOCKET_RETRIES`)
- **`health_check()`** — sends a `ping` command and returns latency + Rhino version; `ping` handler added to C# dispatcher
- **Structured error responses** — all tools return `ok: bool`, `error`, and `error_code` on failure via `normalize()`
- **Windows rhinocode support** — `find_rhinocode()` now checks Windows registry and default install path; `_TEMP_DIR` defaults to `tempfile.gettempdir()` cross-platform
- **`RHINOCODE_DISPATCH_FAILED` error code** — surfaced when rhinocode backend fails to execute script instead of silently returning `status: unknown`
- **Smoke tests** — `test_smoke.py` verifies all modules import, register, have unique tool names, and total ≥ 300 tools
- **130 unit tests** — expanded from 85; covers validators, retry, health check, and tool-level validation integration
- **GitHub Actions PyPI publish workflow** (removed pending first manual publish setup)
- **`pyproject.toml`** — full PyPI metadata, classifiers, project URLs

### Changed
- `_TEMP_DIR` default changed from `/private/tmp` (macOS-only) to `tempfile.gettempdir()` (cross-platform)
- Release assets now include Python wheel and source distribution alongside yak and rhp

### Fixed
- `scripts/package-plugin.sh`: fixed `net7.0` → `net8.0` and binary name `RhinoMCPPlugin.rhp` → `rhino-mcp.rhp`
- `manifest.yml`: fixed placeholder URL to actual GitHub repo
- `README.md`: corrected `StartScriptServer` references to `MCPStart`

---

## [0.4.0] — 2026-05-09

### Added
- **321 total tools** — closed all gaps vs jingcheng-chen/rhinomcp, mcneel/RhinoMCP, quocvibui/rhino3d-mcp
- `get_commands` / `run_command` — compatibility aliases for jingcheng-chen/rhinomcp
- `zoom_to_object` / `zoom_to_layer` — viewport tools from mcneel/RhinoMCP
- **Annotations**: `add_text`, `add_text_dot`, `add_leader`
- **Blocks**: `create_block`, `insert_block`, `explode_block`, `delete_block`, `list_blocks`
- **Groups**: `create_group`, `delete_group`, `add_to_group`, `remove_from_group`, `list_groups`, `select_by_group`
- **Analysis**: `measure_distance`, `measure_curve_length`, `measure_area`, `measure_volume`, `get_bounding_box`, `is_object_solid`
- **User Data**: `set_user_text`, `get_user_text`, `delete_user_text`, `set_document_user_text`, `get_document_user_text`
- **Surface Operations**: 17 new tools (revolve, sweep2, planar surface, edge surface, network surface, patch, offset, split, fillet, cap, extrude along curve, extrude to point, duplicate edges/border, join, explode, unroll)
- **Mesh Operations**: 9 new tools (create mesh, planar mesh, mesh from surface, boolean ops, join, to NURBS, offset)
- **Advanced Transforms**: mirror, copy, array linear, array polar, orient
- **Extended Curves**: 15 new tools
- **Extended Selection**: 8 new tools
- **Extended View**: zoom extents, zoom selected, zoom to object, zoom to layer, view info, display mode, named views

---

## [0.3.0] — 2026-05-08

### Added
- Urban design pipeline: `urban_run_studio_pipeline`, design language generation, AI renders, PDF report export
- V-Ray rendering tools (9 tools)
- Enscape real-time rendering tools (7 tools)
- VisualARQ BIM tools (9 tools)
- Lands Design landscape tools (8 tools)
- Grasshopper plugin tools: Kangaroo, Ladybug/Honeybee, Pufferfish, Weaverbird, LunchBox, Human/Elefront, Anemone
- Asset libraries: Poly Haven (HDRI, textures), Sketchfab model download
- AI 3D generation: text-to-3D, image-to-3D via fal.ai

---

## [0.2.0] — 2026-05-06

### Added
- Initial public release
- Plugin socket backend (port 1999) with rhinocode fallback
- Core geometry tools, Grasshopper canvas/params/solution tools
- PBR materials, layers, objects, views, session tools
- Python and C# script execution tools

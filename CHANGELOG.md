# Changelog

All notable changes to rhino-mcp are documented here.
Versioning follows [Semantic Versioning](https://semver.org/).

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

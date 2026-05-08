# Third-Party Plugin Support for rhino_mcp

**Date:** 2026-05-08  
**Status:** Approved

## Overview

Extend rhino_mcp with full typed MCP tool coverage for the most popular Rhino and Grasshopper third-party plugins, plus a generic plugin introspection/execution layer that works with any installed plugin.

Total additions: ~1 new C# handler, 11 new Python tool modules, ~60 new MCP tools.

---

## Architecture

### Integration mechanisms by plugin type

| Plugin type | Mechanism |
|---|---|
| Grasshopper plugins | Python tool modules orchestrate existing `gh_add_component` / `gh_connect_wire` / `gh_set_slider` with hardcoded component GUIDs per plugin. No new C# needed. |
| Rhino-level plugins (V-Ray, VisualARQ, Lands Design, Enscape) | Python tools call `run_command` with plugin command strings, or `execute_rhino_python` with the plugin's Python API. |
| Generic introspection | New C# handler `get_plugin_commands` + new Python `plugins.py` module. |

### What's new vs. existing

**Existing (unchanged):**
- `list_plugins` / `load_plugin` — C# handlers, kept as-is
- `run_command` — used internally by plugin wrappers
- `gh_add_component`, `gh_connect_wire`, `gh_set_slider`, `gh_set_panel` — GH canvas tools, called internally by GH plugin modules

**New C#:**
- `get_plugin_commands` — enumerate commands registered by a specific plugin

**New Python modules:**
- `plugins.py` — generic introspection
- `gh_kangaroo.py` — Kangaroo Physics
- `gh_ladybug.py` — Ladybug Tools / Honeybee
- `gh_pufferfish.py` — Pufferfish
- `gh_weaverbird.py` — Weaverbird
- `gh_lunchbox.py` — LunchBox
- `gh_human_elefront.py` — Human + Elefront
- `gh_anemone.py` — Anemone
- `vray.py` — V-Ray for Rhino
- `enscape.py` — Enscape
- `visualarq.py` — VisualARQ
- `lands_design.py` — Lands Design

---

## Section 1 — Generic Plugin Introspection

### C# handler: `get_plugin_commands`

Added to `RhinoHandlers.cs` and dispatched in `CommandDispatcher.cs` as a read-only command.

```
Input:  { "plugin_name": string | null, "plugin_id": string (GUID) | null }
Output: { commands: [{name, id}], plugin_name, plugin_id, count }
```

Implementation: iterate `Rhino.Commands.Command.List`, call `LookupCommand(name)`, filter by `.PlugInId == pluginGuid`. Accepts either GUID or partial name match.

### Python module: `plugins.py`

Four tools:

| Tool | Description |
|---|---|
| `list_installed_plugins()` | Enhanced plugin list: name, GUID, loaded status, version, path, command count |
| `get_plugin_commands(plugin_name)` | Commands registered by a specific plugin |
| `run_plugin_command(command, options_string)` | Run any Rhino command string (wraps existing `run_command`) |
| `check_plugin_loaded(plugin_name)` | Returns `{loaded: bool, message: str}` |

---

## Section 2 — Grasshopper Plugin Tools

All GH plugin tools are **workflow orchestration helpers**. They internally call existing lower-level GH canvas MCP commands. Each tool:
1. Checks the plugin is loaded by probing `gh_search_components` with a plugin-specific keyword
2. Resolves component GUIDs dynamically via `gh_search_components(query=component_name)` — never hardcoded, since GUIDs are stable per plugin version but must be confirmed against the live Rhino instance
3. Orchestrates `gh_add_component` + `gh_connect_wire` + parameter setting
4. Returns a summary of what was placed and connected

### `gh_kangaroo.py` — Kangaroo Physics

> Kangaroo 2 is bundled with Rhino 8, so always available in that version.

| Tool | Parameters | Description |
|---|---|---|
| `gh_kangaroo_setup_solver` | `canvas_x, canvas_y, iterations, threshold` | Place K2 Solver component |
| `gh_kangaroo_add_goal` | `goal_type, canvas_x, canvas_y` | Add a goal component (Length, Angle, Anchor, OnMesh, Spring, Pressure, etc.) |
| `gh_kangaroo_connect_goal` | `solver_id, goal_component_id` | Wire a goal into the solver's Goals input |
| `gh_kangaroo_configure_solver` | `solver_id, iterations, threshold, reset` | Set solver numeric parameters via sliders |
| `gh_kangaroo_run_physics` | `solver_id` | Toggle the solver on (set Boolean toggle connected to solver) |

### `gh_ladybug.py` — Ladybug Tools / Honeybee

| Tool | Parameters | Description |
|---|---|---|
| `gh_ladybug_load_weather` | `epw_file_path, canvas_x, canvas_y` | Place Import EPW component with file path |
| `gh_ladybug_sun_path` | `location_id, north_angle, hoy_or_period, canvas_x, canvas_y` | Place Sun Path component and connect location |
| `gh_ladybug_radiation_analysis` | `geometry_id, location_id, analysis_period, canvas_x, canvas_y` | Place Radiation Analysis workflow |
| `gh_ladybug_wind_rose` | `location_id, analysis_period, canvas_x, canvas_y` | Place Wind Rose component |
| `gh_ladybug_utci_comfort` | `location_id, geometry_id, canvas_x, canvas_y` | UTCI outdoor comfort analysis |
| `gh_honeybee_create_room` | `geometry_component_id, room_name, canvas_x, canvas_y` | Place HB Room from Solid component |
| `gh_honeybee_add_window` | `room_id, ratio, canvas_x, canvas_y` | Add HB windows by ratio |
| `gh_honeybee_run_energy` | `model_id, sim_params_id, canvas_x, canvas_y` | Place energy simulation workflow |

### `gh_pufferfish.py` — Pufferfish

| Tool | Parameters | Description |
|---|---|---|
| `gh_pufferfish_tween_curves` | `curve1_id, curve2_id, count, canvas_x, canvas_y` | Place Tween Curves component |
| `gh_pufferfish_morph_surface` | `geometry_id, source_surface_id, target_surface_id, canvas_x, canvas_y` | Surface morph |
| `gh_pufferfish_blend_surfaces` | `srf1_id, srf2_id, count, canvas_x, canvas_y` | Blend/tween surfaces |
| `gh_pufferfish_twist` | `geometry_id, axis_line_id, angle_degrees, canvas_x, canvas_y` | Twist geometry |
| `gh_pufferfish_bend` | `geometry_id, axis_line_id, angle_degrees, canvas_x, canvas_y` | Bend geometry |

### `gh_weaverbird.py` — Weaverbird

| Tool | Parameters | Description |
|---|---|---|
| `gh_wb_catmull_clark` | `mesh_component_id, iterations, canvas_x, canvas_y` | Catmull-Clark subdivision |
| `gh_wb_loop` | `mesh_component_id, iterations, canvas_x, canvas_y` | Loop subdivision |
| `gh_wb_butterfly` | `mesh_component_id, iterations, canvas_x, canvas_y` | Butterfly subdivision |
| `gh_wb_frame` | `mesh_component_id, offset, canvas_x, canvas_y` | Mesh frame |
| `gh_wb_thicken` | `mesh_component_id, thickness, canvas_x, canvas_y` | Mesh thickening |
| `gh_wb_extrude_face` | `mesh_component_id, distance, canvas_x, canvas_y` | Extrude selected faces |

### `gh_lunchbox.py` — LunchBox

| Tool | Parameters | Description |
|---|---|---|
| `gh_lunchbox_quad_panels` | `surface_id, u_count, v_count, canvas_x, canvas_y` | Quad paneling |
| `gh_lunchbox_tri_panels` | `surface_id, u_count, v_count, canvas_x, canvas_y` | Triangle paneling |
| `gh_lunchbox_diamond_panels` | `surface_id, u_count, v_count, canvas_x, canvas_y` | Diamond paneling |
| `gh_lunchbox_hex_panels` | `surface_id, u_count, v_count, canvas_x, canvas_y` | Hexagonal paneling |
| `gh_lunchbox_space_frame` | `surface_id, depth, canvas_x, canvas_y` | Space frame structure |

### `gh_human_elefront.py` — Human + Elefront

| Tool | Parameters | Description |
|---|---|---|
| `gh_elefront_bake_attributes` | `component_id, layer, name, user_text` | Bake with full attribute control |
| `gh_elefront_reference_by_filter` | `layer, name_filter, user_text_key, canvas_x, canvas_y` | Reference Rhino objects by filter |
| `gh_elefront_set_user_text` | `component_id, key, value` | Set user text key-value on objects |
| `gh_human_get_attributes` | `rhino_object_id, canvas_x, canvas_y` | Get Rhino object attributes into GH |
| `gh_human_set_user_text` | `component_id, key, value_component_id` | Wire user text back to Rhino |

### `gh_anemone.py` — Anemone

| Tool | Parameters | Description |
|---|---|---|
| `gh_anemone_setup_loop` | `canvas_x, canvas_y, max_loops` | Place Loop Start + Loop End pair and configure |
| `gh_anemone_set_max_loops` | `loop_start_id, max_loops` | Set loop count on existing loop |

---

## Section 3 — Rhino Plugin Tools

All tools use `run_command` (via `plugin_client.send_command("run_command", {...})`) or `execute_rhino_python`. Each tool returns a `{success, message, ...}` dict and checks plugin availability first.

### `vray.py` — V-Ray for Rhino

| Tool | Parameters | Description |
|---|---|---|
| `vray_start_ipr` | — | Start interactive production rendering |
| `vray_stop_ipr` | — | Stop IPR |
| `vray_render` | `output_path, width, height, quality_preset` | Full render and save |
| `vray_create_material` | `name, diffuse_color, roughness, metalness, ior, opacity` | Create V-Ray material |
| `vray_apply_material` | `object_ids, material_name` | Assign V-Ray material to objects |
| `vray_add_light` | `light_type, position, target, intensity, color, enabled` | Add V-Ray light (Rectangle, IES, Dome, Sun) |
| `vray_set_environment` | `hdri_path, intensity, rotation_degrees` | Set HDRI dome light |
| `vray_set_render_settings` | `width, height, aa_subdivs, gi_preset, time_limit_seconds` | Configure V-Ray render settings |
| `vray_export_vrscene` | `output_path, compressed` | Export .vrscene for V-Ray Standalone |

### `enscape.py` — Enscape

| Tool | Parameters | Description |
|---|---|---|
| `enscape_start` | — | Launch Enscape viewport |
| `enscape_screenshot` | `output_path, width, height` | Capture current view |
| `enscape_export_panorama` | `output_path, resolution` | Export 360° panorama |
| `enscape_export_standalone` | `output_path` | Export standalone .exe |
| `enscape_set_time_of_day` | `hour, minute` | Set sun time |
| `enscape_set_atmosphere` | `cloud_density, wind_speed, precipitation_type` | Weather settings |
| `enscape_create_view` | `name` | Save current Enscape view |

### `visualarq.py` — VisualARQ

| Tool | Parameters | Description |
|---|---|---|
| `varq_create_wall` | `start_pt, end_pt, height, style_name, layer` | Create wall |
| `varq_add_opening` | `wall_id, opening_type, position_along_wall, width, height, style_name` | Add window or door to wall |
| `varq_create_slab` | `boundary_curves, thickness, style_name, layer` | Create floor/slab |
| `varq_create_column` | `position, height, style_name, layer` | Structural column |
| `varq_create_stair` | `start_pt, direction, width, rise, run, story_count, style_name` | Stair |
| `varq_create_railing` | `path_curve, height, style_name` | Railing along curve |
| `varq_set_level` | `name, elevation` | Create or update building level |
| `varq_export_ifc` | `output_path, ifc_version` | Export to IFC 2x3 or IFC 4 |
| `varq_get_object_properties` | `object_id` | Get VisualARQ type, style, and IFC properties |
| `varq_list_styles` | `object_type` | List available styles for walls/doors/windows/slabs/columns/stairs |

### `lands_design.py` — Lands Design

| Tool | Parameters | Description |
|---|---|---|
| `lands_place_plant` | `plant_name, position, rotation_degrees, scale` | Place plant from library |
| `lands_place_tree` | `species_name, position, trunk_height, canopy_radius` | Place tree |
| `lands_create_terrain` | `boundary_curve, source_type, source_id` | Terrain from contours or point cloud |
| `lands_create_path` | `centerline_curve, width, surface_type` | Path or road |
| `lands_create_water` | `boundary_curve, water_level_z` | Water feature |
| `lands_get_plant_database` | `search_query, category` | List available plants/species |
| `lands_set_season` | `season` | spring / summer / autumn / winter |
| `lands_export_plant_list` | `output_path, format` | Export plant schedule (CSV, XLSX) |

---

## Section 4 — Error Handling

All plugin tools follow this pattern:

```python
def _require_plugin(plugin_name: str) -> str | None:
    """Returns None if loaded, error string if not."""
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    loaded = any(p["name"].lower() == plugin_name.lower() and p["loaded"] for p in plugins)
    if not loaded:
        return f"{plugin_name} is not installed or not loaded in Rhino. Install it from the Rhino Package Manager or the plugin vendor."
    return None
```

GH plugin tools additionally probe `gh_search_components` with a plugin-specific keyword to verify the plugin's components are registered.

---

## Section 5 — Testing

- `test_tools_unit.py`: extended with unit tests for each new module; plugin client is mocked; "plugin not loaded" paths are asserted
- `test_plugin_files.py`: asserts all 11 new Python modules exist and are importable
- Integration tests (`@pytest.mark.integration`): only run when the relevant plugin is installed; one smoke test per plugin that calls its simplest read-only tool
- No new C# tests required (C# unit tests are not part of the existing test suite)

---

## Tool Count Summary

| Module | New tools |
|---|---|
| `plugins.py` | 4 |
| `gh_kangaroo.py` | 5 |
| `gh_ladybug.py` | 8 |
| `gh_pufferfish.py` | 5 |
| `gh_weaverbird.py` | 6 |
| `gh_lunchbox.py` | 5 |
| `gh_human_elefront.py` | 5 |
| `gh_anemone.py` | 2 |
| `vray.py` | 9 |
| `enscape.py` | 7 |
| `visualarq.py` | 10 |
| `lands_design.py` | 8 |
| **Total** | **70** |

Plus 1 new C# handler (`get_plugin_commands`) and corresponding `CommandDispatcher.cs` entry.

---
name: rhino-mcp-basics
description: Shared rules for every Rhino MCP tool call. Read this first when controlling Rhino 3D through MCP; the other rhino-* skills assume it.
---

# Rhino MCP basics

## Connect
- `health_check` first. If it fails, Rhino is not running or the plugin is not started (`MCPStart` in Rhino).
- More than one Rhino open? `get_rhino_instances`, then pass `rhino_id` to every tool. `launch_rhino` starts a new one.
- Grasshopper, PBR, plugin, V-Ray, and Enscape tools need the plugin socket. They do not fall back to rhinocode.

## Reading results
- Success is `{"ok": true, ...}`. Failure is `{"ok": false, "error", "error_code"}`.
- Script-backed tools put their data under `script_result`, not `result`.
- Third-party plugin helpers (V-Ray, Enscape, Lands, VisualARQ, GH plugin tools, `install_plugin`) return `success`, not `ok`.
- Created ids come back under different keys per tool: `created`, `result_ids`, `result_id`, `ids`, `id`, `objects`. Read the one the tool documents.
- `EXECUTION_OUTCOME_UNKNOWN` means the command was sent but the outcome is ambiguous. Inspect the document before retrying.
- `TOOL_DISABLED` means an operator turned off that execution gate. Do not work around it.

## Values
- Points are `[x, y, z]` in document units. `[x, y]` is accepted by geometry creation and padded to z=0.
- Colors are `[r, g, b]` integers 0 to 255. PBR materials are the exception: floats 0 to 1.
- Angles are degrees everywhere.
- Object ids are GUIDs in 8-4-4-4-12 form. Layer names use `Parent::Child` for sublayers.

## Defaults that bite
- `delete_input` / `delete_sources` default to **true** in booleans, joins, splits, explodes, block creation, and mesh booleans. Pass `false` to keep the inputs.
- Tools that take `ids` fall back to the current selection when `ids` is omitted. Pass ids explicitly.
- `transform_rhino_objects` rotates and scales about the **world origin** unless you pass `rotate_center` / `scale_origin`.
- `align_geometry_to_point` and `set_object_display_color` with no ids act on **every object in the document**.
- `delete_rhino_objects(delete_all=true)` wipes the document. Never call it without an explicit user request.
- Recoloring or normalizing objects that carry imported materials deletes and re-adds them, so their GUIDs change. Re-query ids afterwards.

## Undo
Each MCP tool call is one undo record on the plugin backend. `undo_rhino(count=1)` reverts the whole last call. Failed plugin commands roll back automatically.

## Scripting
Prefer structured tools. Use `execute_rhino_python` only for gaps:
- Assign a JSON-safe value to `result`. Convert GUIDs with `str()` and points to `[x, y, z]`. A non-serialisable `result` is silently dropped.
- Set `result = {"ok": False, "error": "..."}` to fail the call and trigger rollback.
- Pass `verified_functions=[...]` after checking names with `search_rhinoscript_functions`, or the response carries an API warning.
- `clear_objects=["LayerName"]` deletes those layers' contents before the script runs, which makes re-runs idempotent.

## Finish every modeling task
1. `zoom_extents`
2. `set_display_mode(mode="Shaded")`
3. `capture_rhino_view` and look at the image before reporting.
4. Report layer names and object ids you created, and every default you assumed.

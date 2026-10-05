---
name: rhino-grasshopper-parametric
description: Build or edit a Grasshopper definition through Rhino MCP. Use when the user wants slider-driven, parametric, or scripted geometry rather than static objects.
---

# Grasshopper via Rhino MCP

Read `rhino-mcp-basics` first. Third-party plugin helpers: [plugins.md](plugins.md).

## Contract
- Plugin socket only. Grasshopper must be open with an active definition. `gh_new_definition(name)` opens the editor if needed.
- Every response is `{ok, result: {...}}`. Read fields from `result`.
- Components are addressed by **instance GUID**. Inputs and outputs are addressed by **nickname**, case-insensitive. Indexes and full names do not work.
- Standalone params (Slider, Panel, Number, Point) accept any string for their port name.

## GH1 build loop
1. `gh_search_components(query)` → pick the `guid` (a type GUID).
2. `gh_add_component(component_guid | type_name, x, y)` → `result.instance_guid` plus the real input/output nicknames. Prefer the GUID when a name could be ambiguous. Space components about 250 px apart in x.
3. Inputs: `gh_add_component` for a Number Slider or Panel, then `gh_set_slider(instance_guid, value)` (clamped to the slider's existing range, which cannot be changed from MCP), `gh_set_panel(instance_guid, text)`, `gh_set_number_param(instance_guid, values=[...])`, `gh_set_point_param(instance_guid, points=[[x,y,z],...])`.
4. Wire: `gh_connect_params(from_guid, from_output, to_guid, to_input)` with nicknames or 0-based indices from step 2. An error names the missing port. GH1 and GH2 wiring take the same four arguments.
5. `gh_run_solution(wait_ms=10000)`. Check `result.error_count` and `timed_out`.
6. If errors: `gh_get_errors()` lists component nickname, message, and level. Fix before adding more.
7. `gh_get_output(instance_guid, output_name)` to read values. Values are strings, and stale until a solution has run.
8. Bake only the final components: `gh_bake(instance_guid, layer)`. `gh_bake_all` bakes every intermediate param too. A `layer` of `A::B` creates one flat layer named that way, not a nested one.
9. Tidy: `gh_add_group(instance_guids, label, color)`, `gh_set_component_comment`. `gh_refactor_canvas(apply=False)` previews a layout; `apply=True` applies it.
10. `gh_save_definition(path)`. An unsaved document requires an explicit path.

## Script components
`gh_add_script_component(language="python"|"csharp", code, inputs=[...], outputs=[...], x, y)` places a script component and reshapes its variable ports to the names you pass. The result returns the final `inputs` and `outputs`; ports the component refuses to remove (such as `out`) are kept, so read the result rather than assuming. If the component cannot be reshaped or `code` cannot be injected, the call returns an explicit error. In Python, assign to the output variable names. Needs Rhino 8 and the RhinoScript and C# execution gates.

## Grasshopper 2 (Rhino 9 WIP only)
- `gh2_start`. If it says GH2 is not available, run `_Grasshopper2` in Rhino and retry.
- Build in one call: `gh2_apply_graph(components=[{"key", "type_name"|"component_guid", "x", "y"}, {"key", "type": "slider", "min", "max", "value", "decimals", "x", "y"}], wires=[{"from_key"|"from_guid", "from_output", "to_key"|"to_guid", "to_input"}])` → `{ok, placed: {key: instance_guid}, wired, errors, solve}`. Ports take a nickname or an integer index. Keys resolve against components placed in the same call. Nothing is rolled back on partial failure; read `errors`. By default the call re-solves and returns `solve.diagnostics` (`{instance_guid, name, level, message}` per message), so check `solve.solved` before adding more. Pass `solve=False` to batch and solve once.
- Add wires later with `gh2_connect(from_guid, from_output, to_guid, to_input)` (same shape as `gh_connect_params`) or `gh2_connect_many(wires=[{"from_guid", "from_output", "to_guid", "to_input"}])` → `connected`, `errors`.
- Port nicknames: `gh2_describe_component(instance_guid=...)` for a placed component, `gh2_describe_component(name=...)` for a library type, or `gh2_get_canvas_graph`.
- `gh2_solve_graph` returns `solved`, `error_count`, `warning_count`, `errors`, and `diagnostics`. `gh2_place_component` and `gh2_place_slider` return the same `solve` summary unless `solve=False`. `gh2_clear_canvas(confirm=True)` empties the canvas.
- `gh_migrate_to_gh2(confirm=True, allow_partial)` maps the active GH1 canvas to GH2 using the shipped component map. Unmapped components stop the run unless `allow_partial=True`; the result lists them. It does not verify semantic equivalence, so solve and inspect afterwards.

## Rules
- Expose every design-driving number as a slider or Number param and report their GUIDs and ranges.
- Run a solution after every batch of wires; never read outputs or bake without one.
- Keep the definition small. Offer two parametric variants when the brief is open.

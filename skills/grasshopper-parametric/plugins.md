# Third-party Grasshopper plugin helpers

All helpers share one pattern:
- They check `gh_search_components` for the plugin name and return `{"success": false, "message": "X is not installed..."}` if absent. Install with `install_plugin(plugin_name)` for Yak packages (pufferfish, elefront, weaverbird, anemone, human, lunchbox), then restart Rhino. Kangaroo ships with Rhino 8. Ladybug and Honeybee are manual installs.
- They return `{"success": bool, "instance_guid"?, "error"?}`. The key is `success`, not `ok`.
- They place the component and wire it to the source GUIDs you pass, using hard-coded input nicknames. Pass **standalone param GUIDs** (Geometry, Surface, Mesh, Curve) as sources, because the helper guesses the source output name and only standalone params ignore that name.
- Scalars are added as new Number params and Panels on the canvas, about 200 px to the left. Calling a configure helper twice adds a second param and merges wires; prefer editing the existing param with `gh_set_number_param`.
- None of them solve. Call `gh_run_solution` afterwards and `gh_get_errors` if `error_count` is above 0.
- On a partial failure the component stays placed and `instance_guid` is returned so you can wire it by hand with `gh_connect_params`.

| Plugin | Helpers | Notes |
|---|---|---|
| Pufferfish | `gh_pufferfish_tween_curves(curve1, curve2, count)`, `gh_pufferfish_morph_surface(geometry, source_surface, target_surface)`, `gh_pufferfish_blend_surfaces(s1, s2, count)`, `gh_pufferfish_twist` / `gh_pufferfish_bend(geometry, axis, angle_degrees)` | All ids are instance GUIDs |
| Weaverbird | `gh_wb_catmull_clark` / `gh_wb_loop` / `gh_wb_butterfly(mesh, iterations)`, `gh_wb_frame(mesh, offset)`, `gh_wb_thicken(mesh, thickness)`, `gh_wb_extrude_face(mesh, distance)` | Source must be a Mesh param |
| LunchBox | `gh_lunchbox_quad_panels` / `tri_panels` / `diamond_panels` / `hex_panels(surface, u_count, v_count)`, `gh_lunchbox_space_frame(surface, depth)` | Source must be a Surface param |
| Anemone | `gh_anemone_setup_loop(max_loops)` → `loop_start_instance_guid`, `loop_end_instance_guid`; `gh_anemone_set_max_loops` | You wire the loop body between Start and End |
| Kangaroo | `gh_kangaroo_setup_solver(iterations, threshold)` → `solver.instance_guid`; `gh_kangaroo_add_goal(goal_type)` with Length, Angle, Anchor, OnMesh, Spring, Pressure, Load, Hinge, Laplacian; `gh_kangaroo_connect_goal(solver, goal)`; `gh_kangaroo_run_physics(solver)` | run_physics is one solve step, not a continuous loop. Wire goal geometry inputs yourself |
| Ladybug / Honeybee | `gh_ladybug_load_weather(epw_file_path)` → location GUID; `gh_ladybug_sun_path(location)`; `gh_ladybug_radiation_analysis(geometry, location)`; `gh_ladybug_wind_rose(location)`; `gh_ladybug_utci_comfort(location, geometry)`; `gh_honeybee_create_room(geometry, room_name)`; `gh_honeybee_add_window(room, ratio)`; `gh_honeybee_run_energy(model)` | `north_angle` is ignored. `run_energy` only places the IDF component; it does not simulate |
| Human / Elefront | `gh_elefront_bake_attributes(component, layer, name, user_text)`, `gh_elefront_reference_by_filter(layer, name_filter, user_text_key)`, `gh_elefront_set_user_text`, `gh_human_get_attributes(rhino_object_id)`, `gh_human_set_user_text` | Nothing bakes until Elefront's own bake toggle fires. Generic names like "Set User Text" may resolve to the other plugin |

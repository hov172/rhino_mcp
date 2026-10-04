# `create_rhino_geometry` / `create_rhino_scene` type reference

`create_rhino_geometry(geometry_type, params, name?, layer?, color?, snap_to_grid?)` makes one object.
`create_rhino_scene(items, snap_to_grid?)` makes many; each item `{"type", "params", ...}`.
Defaults in parentheses. Points may be `[x,y]` or `[x,y,z]`; a missing point is the origin.

| type | params |
|---|---|
| `point` | `point` |
| `line` | `start`, `end` |
| `polyline` | `points` (repeat the first point to close) |
| `curve` / `nurbs_curve` | `points` (control points, not interpolated), `degree` (3) |
| `circle` | `center`, `radius` (1) |
| `ellipse` | `center`, `radius_x` (1), `radius_y` (0.5), on World XY |
| `arc` | `center`, `radius`, `start_angle` (0), `end_angle` (90); or `start`, `end`, `point_on_arc` |
| `sphere` | `center`, `radius` |
| `ellipsoid` | `center`, `radius_x`, `radius_y`, `radius_z` |
| `box` | centred: `center`, `size:[sx,sy,sz]` or `width`/`depth`/`height`. Grounded: `corner`, `width`, `depth`, `height` |
| `cylinder` / `cone` | `base`, `height` (1), `radius` (1), `cap` (true). Axis is +Z from base |
| `torus` | `center`, `major_radius` (2), `minor_radius` (0.5) |
| `plane_surface` | `center`, `width`, `height`, on XY |
| `plane` | `center`, `width`, `height`, `normal` ([0,0,1]) |
| `surface` | 3 or 4 corner `points`; or grid `points` with `count:[u,v]`, `degree` |
| `extrusion` | `profile_id` or `points` (≥3, auto-closed), `height` (1), `cap` (true) |
| `mesh` | `vertices`, `faces` (tri or quad, 0-based) |
| `text` | `text`, `point`, `height` (1) |
| `textdot` | `text`, `point`, `font_size` |
| `light` | `light_style` point/directional/spot/linear/rectangular/area, `location`, `intensity`, `diffuse_color`, `direction` |
| `block_insert` | `block_name`, `position`. Prefer the `insert_block` tool, which errors on a missing block |
| `dimension_linear` | `start`, `end`, `offset` (0.5) |
| `dimension_radial` | `center`, `radius`, `angle`, `offset`, `is_diameter` |
| `leader` | `points` (≥2), `text` |
| `hatch` | `curve_id` or `center`/`width`/`height`, `pattern` ("Solid"), `rotation`, `scale` |
| `clipping_plane` | `origin`, `normal`, `width` (10), `height` (10) |
| `subd` | `mesh_id`, or `center`/`width`/`depth`/`height`/`segments` |

Only point, line, circle, sphere, cylinder, cone, and text have a Rhino-command fallback when the Python path fails.

## Follow-on tools and their id keys
- `loft(curve_ids, closed, loft_type 0 normal/1 loose/2 tight/3 straight)` → `result_ids`
- `extrude_curve(curve_id, direction=[x,y,z] vector, cap)` → `result_id`
- `sweep1(rail_id, profile_ids)`, `sweep2(rail1_id, rail2_id, profile_ids)` → `result_ids` / `ids`
- `pipe(curve_id, radius, cap)` → `result_ids`
- `offset_curve(curve_id, distance, corner_style 1 sharp/2 round)` → `result_ids`; negative distance flips the side
- `boolean_union(object_ids)`, `boolean_difference(base_id, subtract_ids)`, `boolean_intersection(object_ids)` → `result_ids`; inputs must be closed solids; `delete_sources` true by default
- `create_planar_surface(curve_ids)` → `ids`; `revolve_curve(curve_id, axis_start, axis_end, angle)` → `id`
- `cap_planar_holes(brep_id)` → `{id, capped, is_solid}`
- `array_linear(ids, direction, count, spacing)`, `array_polar(ids, center, count, angle)`; `count` includes the original; polar is about world Z only
- `mirror_objects(ids, plane_origin, plane_normal, copy)`, `copy_objects(ids, translation)`
- `measure_area`, `measure_volume`, `get_bounding_box(object_ids)` → `{min, max, center, width, depth, height}`

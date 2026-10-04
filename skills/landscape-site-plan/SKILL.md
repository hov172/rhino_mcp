---
name: rhino-landscape-site-plan
description: Produce a landscape site plan in Rhino with terrain, paths, water, planting, and a ground plane. Use for parks, plazas, campuses, and residential landscapes. For massing and FAR studies use rhino-urban-massing-studio.
---

# Landscape site plans

Read `rhino-mcp-basics` first.

## What the Lands Design tools really do
The `lands_*` placement tools take no geometric parameters. They only launch Lands Design's interactive commands, and the user must finish each one with the mouse. Two tools work headlessly: `lands_set_season(season)` and `lands_export_plant_list(output_path)`. Do not promise automated planting through Lands Design. Build the plan with core geometry and use Lands only when the user is sitting at Rhino to complete the prompts.

## Layers
Create with `manage_rhino_layer(action="create", name, color)`: Site, Terrain, Paths, Water, Planting::Trees, Planting::Shrubs, Furniture, Annotation. Distinct colors; greens for planting, blue for water, warm grey for paths.

## Build order
1. **Ground plane.** `plane_surface` or 4-point `surface` with a margin of about 20 percent around the site, neutral color, on layer Site.
2. **Terrain.** Contours as `polyline` items at their elevations, then `create_patch(object_ids=[contour ids], u_spans, v_spans)` or `loft(curve_ids)` for a terrain surface. Keep the contours on a sublayer for editing.
3. **Paths.** Centreline `curve`, then `offset_curve(curve_id, distance=±width/2)` both sides, `join_curves`, and `create_planar_surface(curve_ids)`. For a path with thickness use `extrusion` items with `height=0.1`.
4. **Water.** Closed outline, `create_planar_surface`, then move down with `transform_rhino_objects(ids, move=[0,0,-0.3])`. Add a `plane_surface` for the bank.
5. **Planting.** Trees are a `cylinder` trunk plus a `sphere` or `ellipsoid` canopy, built once, then `create_block(object_ids, base_point, name="Tree_Species")` and placed with `insert_block(name, point, scale, rotation)`. Rows use `array_linear(ids, direction, count, spacing)`. Vary `scale` between 0.8 and 1.2 so the plan does not look stamped.
6. **Furniture and lighting.** Simple `box` items on layer Furniture; `light` items only for renders.
7. **Annotation.** `add_text(text, point, height)` for area labels; `add_leader(points, text)` for callouts. `measure_area(object_id)` for each surface, totalled into a small schedule.
8. **Finish.** `zoom_extents`, `set_display_mode("Shaded")`, `capture_rhino_view`. A Top view capture is the plan; `set_rhino_view(view="Top")` first.

## Schedules and reports
- Planting counts: `list_blocks` returns `instance_count` per block definition.
- Areas: sum `measure_area` by layer and present hard, soft, and water areas with percentages.
- Tag objects with `set_user_text(object_id, key, value)` for species, size, and quantity so the data survives export.

## Rules
- Planar areas are surfaces, never bare polylines.
- Offer two or three layout options on separate layers. The designer decides.
- Report areas, counts, and every default dimension you chose.

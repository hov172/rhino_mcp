---
name: rhino-text-to-3d
description: Build a Rhino 3D model from a written brief. Use when the user describes a building, object, or scene in words and wants it modeled in Rhino.
---

# Text to 3D in Rhino

Read `rhino-mcp-basics` first. Geometry type reference: [geometry-types.md](geometry-types.md).

## Before modeling
1. Restate the brief as dimensions, units, and a short parts list. Default missing dimensions (floor height 3 m, wall 0.2 m, slab 0.3 m) and say so. Ask only when no sensible default exists.
2. `health_check`, and `get_rhino_instances` if more than one Rhino may be open.

## Workflow
1. One layer per part with `manage_rhino_layer(action="create", name=..., color=[r,g,b])`. Distinct colors.
2. Build with `create_rhino_scene(items=[...])`. Each item is `{"type", "params", "name"?, "layer"?, "layer_color"?, "color"?}`. One call per logical group of parts. The result is `script_result.created` (ids, `None` for failures) plus `errors`.
3. Boxes are **centred on the origin** unless you pass `corner`. For anything sitting on the ground use `{"corner": [x,y,0], "width", "depth", "height"}`.
4. Planar site elements are surfaces: `plane_surface`, `surface` with 3 or 4 corner points, or `extrusion` with `height` for slabs. Never leave a site plan as curves only.
5. Derived shapes: `boolean_difference(base_id, subtract_ids)` for openings, `loft`, `extrude_curve(curve_id, direction=[0,0,h])`, `pipe`, `offset_curve`. These consume their inputs by default.
6. Organic objects: `generate_3d_from_text(prompt, service="rodin"|"hunyuan3d")`, then `poll_generation_job(job_id, service)` every 5 to 15 s until `done`, then `import_generated_model(job_id, service, scale, position)`. Rodin needs `HYPER3D_API_KEY`. Hunyuan3D needs no key but ignores `output_format` and can be slow. Job ids are lost if the server restarts.
7. `execute_rhino_python` only for what the structured tools cannot do. Assign `result`.
8. Finish: `zoom_extents`, `set_display_mode("Shaded")`, `capture_rhino_view`. Compare the image to the brief and fix before reporting.

## Rules
- Colors `[r,g,b]` 0 to 255, angles in degrees, points `[x,y,z]`.
- Return object ids by layer and every assumed dimension.
- When the brief is open-ended, offer two variants on separate layers and let the designer choose.

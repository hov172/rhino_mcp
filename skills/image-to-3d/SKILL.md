---
name: rhino-image-to-3d
description: Turn a sketch, floor plan, section, CAD PDF, or photo into Rhino geometry. Use when the user supplies an image or drawing file and wants it modeled.
---

# Image to 3D in Rhino

Read `rhino-mcp-basics` first. For reading the file itself see `rhino-document-reading`.

## Pick the route
- **Dimensioned drawing** (plan, section, CAD-exported PDF): trace it. Accuracy comes from scale calibration, not from guessing.
- **Photo or concept sketch of an object**: generate a mesh with Hunyuan3D or Rodin, then place it.
- **DWG/DXF available**: skip tracing. `import_file(path)` sets Wireframe with a dark background and zooms. Then extrude the imported curves.

## Tracing a plan
1. Read it: `read_image(path)` for rasters, `read_pdf(path, pages="1", dpi=150, scale_hint="1:100")` for PDFs. State the DPI you used.
2. Find one known dimension in the drawing. `calibrate_pdf_scale(pixel_point_1, pixel_point_2, real_distance, real_unit)` gives `real_units_per_px`. Without a known dimension, default to a door width of 0.9 m and say so.
3. For vector PDFs, `read_pdf_vectors(path, pages, real_units_per_px, real_unit, dpi=<same dpi>)` returns paths you can convert to `polyline` items directly. `extract_pdf_dimensions` pulls labelled dimensions as a cross-check.
4. Layers: Walls, Slabs, Openings, Site. Create them with `manage_rhino_layer`.
5. Walls: closed `polyline` outlines, then `extrude_curve(curve_id, direction=[0,0,height])` or `extrusion` items with `points` and `height`. Default floor height 3 m.
6. Slabs: `extrusion` with the floor outline and `height=0.3`, or `plane_surface`. Planar areas are surfaces, never bare curves.
7. Openings: `boolean_difference(base_id=wall_id, subtract_ids=[opening_box_id])`.
8. `zoom_extents`, `set_display_mode("Shaded")`, `capture_rhino_view`. Compare to the source and correct.

## Photo or sketch to mesh
1. `generate_3d_from_images(image_paths=[...], service="hunyuan3d"|"rodin", prompt?)`. Images must be under the home directory. Hunyuan3D uses only the first image and needs no key. Rodin uses all images and needs `HYPER3D_API_KEY`.
2. `poll_generation_job(job_id, service)` every 5 to 15 s until `status` is `done` or `failed`.
3. `import_generated_model(job_id, service, scale, position=[x,y,z])`. Scale is applied before the move. Import runs a document-wide material normalize, so re-query object ids afterwards.
4. Put generated meshes on their own layer so they can be swapped out.

## Rules
- Report the scale, DPI, and every defaulted dimension.
- Trace the outline first, confirm with a capture, then add openings. Do not model every detail in one pass.

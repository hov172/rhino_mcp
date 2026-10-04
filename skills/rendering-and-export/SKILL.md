---
name: rhino-rendering-and-export
description: Apply materials, set up views and environments, capture renders, and export Rhino models to other formats. Use when the user wants images, presentation views, or files for other software.
---

# Rendering and export

Read `rhino-mcp-basics` first.

## Materials
- Quick color: `edit_rhino_object_attributes(ids, color=[r,g,b])` or `set_object_display_color(color, object_ids)`. Both create an `MCP_Color_RRGGBB` material so the color shows in Shaded and Rendered modes. Objects with imported materials get new GUIDs.
- Basic material: `create_material(name, diffuse=[r,g,b], transparency, shininess)` → `index`; `set_object_material(id, material_name)`. `set_material_*` tools edit a shared material in place, so every object using it changes.
- PBR: `create_pbr_material(name, base_color=[r,g,b] floats 0 to 1, metallic, roughness, opacity, *_texture paths)`. `emission` only works with `emission_multiplier` above 0. `ior` sets the opacity IOR; the result reports it under `applied` or `not_applied`. Bump and displacement strength are not adjustable through MCP. Assign with `assign_pbr_material_to_objects(material_name, object_ids | all_objects)`.
- Textures from Poly Haven: `search_polyhaven_assets(asset_type="textures", categories=["wood"])`, then `apply_polyhaven_texture(asset_id, object_id, resolution="2k", channel="all")`. Check `textures_applied`.
- Layer material: `add_material_to_layer(layer_name, color, transparency)` affects only objects whose material source is the layer.

## Environment and lighting
- HDRI: `apply_polyhaven_hdri(asset_id | filepath, rotation, intensity)` for Poly Haven assets, or `set_environment_map(filepath, rotation, intensity, use_for_background, use_for_lighting, use_for_reflections)` for any local HDR or EXR. Check `not_applied` in the result; intensity depends on the texture exposing a multiplier.
- `set_render_settings(background_color, use_transparent_background, enable_ground_plane, ground_plane_altitude)`. Each is applied independently and the result lists `applied` and `not_applied`. Renderer engine and sample counts are not exposed through MCP.
- Lights: `create_rhino_geometry("light", {"light_style": "directional"|"point"|"spot"|"rectangular", "location", "direction", "intensity"})`.

## Views
- `set_rhino_view(view="Perspective", camera=[x,y,z], target=[x,y,z], lens=35)`. Camera and target must be given together.
- `set_display_mode(mode="Shaded"|"Rendered"|"Arctic"|"Pen"|"Technical")`, `add_named_view(name)`, `restore_named_view(name)`, `zoom_extents`, `zoom_to_layer(layer_name)`.
- Quick image to look at: `capture_rhino_view(width=800, height=600)` returns the image inline.
- File output: `export_viewport_image(path, width=1920, height=1080, display_mode="Rendered", transparent_background)`. PNG, JPG, BMP, TIFF. It leaves the viewport in that display mode.
- `render_to_image(output_path, width, height, return_base64=False)` runs the Rhino renderer but saves a viewport capture; treat it like `export_viewport_image`.
- Resize or convert afterwards with `convert_image(source_path, output_path, width, height, quality)`. One dimension keeps the aspect ratio; both force the exact size.

## V-Ray and Enscape
Both need the vendor plugin loaded and return `success` plus `applied` / `not_applied`:
- V-Ray: `vray_render(output_path, width, height, quality_preset="low"|"medium"|"high"|"ultra")` and `vray_set_render_settings(width, height, quality_preset)` apply through V-Ray's Python module when it is importable; otherwise everything lands in `not_applied`. `vray_create_material(name, diffuse_color, opacity)` makes a plain Rhino material that V-Ray converts. `vray_add_light(light_type)` and `vray_set_environment()` launch interactive commands. `vray_export_vrscene(output_path)` works.
- Enscape: `enscape_start`, `enscape_set_time_of_day(hour, minute)`, `enscape_create_view(name)`, `enscape_screenshot(output_path)`, `enscape_export_panorama(output_path)`, and `enscape_export_standalone(output_path)` launch Enscape commands. Size and resolution follow Enscape's own settings. `enscape_set_atmosphere()` only opens the visual settings dialog.
Tell the user when a step needs them at the keyboard.

## Export
All exporters take `object_ids`; with none they export the whole document. Check `applied` against `requested` in the result, and read `note` when a fallback used Rhino's current exporter settings.
- `export_3dm(path, rhino_version=8, object_ids?)`. A subset export drops layer and material tables.
- `export_dwg(path .dwg|.dxf, autocad_version="2000"|"2004"|"2007"|"2010"|"2013"|"2018")`. `export_step(path, schema="AP203"|"AP214"|"AP242")` uses the document tolerance. `export_iges(path, tolerance)`.
- `export_obj(path, export_materials, export_texture_coordinates)` converts Z-up to Y-up. `export_fbx(path, file_type="binary7"|"binary6"|"ascii7"|"ascii6")`. `export_glb(path, draco_compression, export_materials)`; `.glb` embeds textures, `.gltf` writes them externally, reported under `textures`.
- `export_stl(path, binary=True, tolerance)`, `export_3mf(path)`.
- Simple fallback for any format: `export_rhino_document(path)` runs Rhino's exporter with current settings.

## Deliverable checklist
1. Set units if needed with `set_unit_system`. It does not scale geometry.
2. Materials and environment, then named views for each sheet image.
3. Export images at the requested size, then the model files.
4. Report file paths, sizes if known, and any option that was requested but not applied.

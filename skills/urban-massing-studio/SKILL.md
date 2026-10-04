---
name: rhino-urban-massing-studio
description: Run urban massing, FAR, solar, AI render, and report workflows in Rhino. Use for site capacity studies, typology comparisons, and studio presentation output.
---

# Urban massing and studio pipeline

Read `rhino-mcp-basics` first. These tools drive Grasshopper definitions shipped in `grasshopper/urban/`; the plugin socket and Grasshopper must be available.

## Intake
1. `parse_urban_prompt(prompt)` → typology, site size, FAR target, use mix, climate zone, and `missing_fields`. Ask the user for anything in `missing_fields`. Site width, depth, and FAR target are mandatory.
2. Site boundary in GeoJSON? Project it to metres first. `create_urban_scheme` treats coordinates as model units.

## Massing
- Typologies: `tower`, `podium_tower`, `courtyard`, `perimeter_block`, `street_grid`. Each has its own slider names; see [typologies.md](typologies.md). Unknown keys in `params` are dropped silently, and `far_target` and `office_pct` are not sliders.
- `optimize_plan(target_far, site_width, site_depth, typology)` → `recommended_params`. It is a heuristic FAR fit.
- `urban_generate_massing(typology, site_origin=[x,y,0], site_width, site_depth, params, layer_prefix="Urban")` bakes to `Urban::Massing::<typology>` in lowercase and returns heuristic metrics with `estimated: true`.
- `urban_capture_and_evaluate()` returns metrics plus a viewport image. Look at it.
- Iterate with `urban_update_param(param_name, value)`. To change typology, `urban_clear_massing()` then regenerate. Clearing also wipes design language, renders, and pipeline history.
- `calculate_urban_metrics(site_width, site_depth, gfa_m2, far_target)` → `far_within_2pct` for the compliance check. Units assume 70 m² each.
- `generate_site_layout(site_width, site_depth, block_width, block_depth, road_width, grid_rotation, bake)` for parcel grids.

## Solar
`urban_run_analysis(analysis_type="solar", geometry_layer="Urban::Massing::<typology>", climate_zone, epw_path?, analysis_period="Jun 21 9am-5pm")`. Climate zones: London, New York, Dubai, Tokyo, Sydney, Singapore, Berlin, each needing an EPW under `~/ladybug/EPWs/`. Pass the exact baked layer name. Needs Ladybug Tools. After this the massing sliders are stale; regenerate before more `urban_update_param` calls.

## Design language, renders, report
1. `urban_generate_design_language(brief, typology, far, climate_zone, style_hints)`. Needs `ANTHROPIC_API_KEY`. Returns palette, facade vocabulary, and a diffusion prompt. Edit fields with `urban_update_design_language(field, value)`.
2. `urban_render_views(views=["Perspective","Top","Front","Right"], strength=0.65, seed)`. Needs `FAL_KEY`. Without it every view fails with no fallback image. `urban_render_style_preview(style_prompt)` is a text-only mood image.
3. `urban_export_report(project_name, scheme_name, author, include_solar, format="pdf"|"html")`. PDF needs `DOCRAPTOR_API_KEY`, otherwise HTML with a warning. S3 upload only with `URBAN_AGENT_S3_BUCKET` and AWS keys; otherwise saved under `~/.urbanagent/reports/`. `urban_preview_report()` gives quick HTML.

## One-call pipeline
`urban_run_studio_pipeline(project_name, scheme_name, brief, render_views, include_solar, skip_steps)` runs design_language → renders → solar → export. Generate massing first or metrics are zero. The solar step uses the layer the massing was actually baked to, the climate zone parsed from `brief`, and the current FAR; defaults are London and 3.5 when nothing is stored. Without `ANTHROPIC_API_KEY` the run aborts unless you skip `design_language`. Check `step_log` and `errors` in the result.

## Export and versions
- `export_model(output_format="3dm"|"glb"|"gltf"|"geojson"|"pdf", path)`. Paths must be under home or temp. GeoJSON is a bounding-box manifest, not real GIS.
- `save_project_version(project_name, version_name, directory, metadata)`; check `export.ok` inside the result.

## Rules
- Never call `urban_clear_massing` between design language or renders and the report.
- Report metrics with their `source` and `estimated` flags. Heuristic numbers are estimates and should be labelled as such.

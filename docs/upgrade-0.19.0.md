# Upgrading to 0.19.0

0.19.0 is a contract-correction release. The Rhino plugin changed, so install the matching plugin and restart Rhino and the AI client. All 358 tools remain; several lost parameters that were never applied. The [0.18.0 PDF changes](upgrade-0.18.0.md), the [0.17.1 registration repair](upgrade-0.17.1.md), and the [TLS requirements](secure-operation.md) still apply.

## Plugin update is required

Grasshopper 2 wiring, script component ports, and environment maps are implemented in the C# plugin. A 0.19.0 server against a 0.18.0 plugin will still see `gh2_connect` fail and `set_environment_map` return `success: false`. Quit Rhino, install the 0.19.0 package or copy the bundle, then restart. On macOS the `rhino-mcp-configure` LaunchAgent re-installs from `/Users/Shared/rhino_mcp/plugin` at login, so a hand-copied bundle must also be copied there or it is rolled back.

## Removed parameters

Calls that pass these now fail validation. Drop them.

| Tool | Removed | Why |
|---|---|---|
| `export_fbx` | `fbx_version`, `embed_textures`, `save_textures_as_references` | No such options in RhinoCommon. Use `file_type`. |
| `export_obj` | `weld_angle` | No settable option. |
| `export_step` | `tolerance` | Document tolerance is used. |
| `export_iges` | `trim_type` | No such option. |
| `export_dwg` | `export_layout` | No such option. |
| `export_3mf` | `mesh_quality` | Document render-mesh settings are used. |
| `export_glb` | `embed_textures` | `.glb` always embeds, `.gltf` always writes external files. |
| `create_pbr_material` | `bump_scale`, `displacement_scale` | Not adjustable through RhinoCommon textures. |
| `set_render_settings` | `engine`, `samples`, `enable_shadows`, `ambient_occlusion` | No cross-engine API. |
| `vray_create_material` | `roughness`, `metalness`, `ior` | Creates a plain Rhino material that V-Ray converts. |
| `vray_add_light` | `position`, `target`, `intensity`, `color` | Interactive command. |
| `vray_set_environment` | all | Opens the asset editor. |
| `vray_set_render_settings` | `aa_subdivs`, `gi_preset`, `time_limit_seconds` | No documented scripting access. |
| `vray_export_vrscene` | `compressed` | No such option. |
| `enscape_screenshot`, `enscape_export_panorama` | `width`, `height`, `resolution` | Enscape settings control output size. |
| `enscape_set_atmosphere` | all | Opens the visual settings dialog. |
| `lands_*` placement tools | every geometric parameter | Interactive commands; no scripting API. |
| `lands_export_plant_list` | `format` | Follows the file extension. |
| `varq_*` placement tools | every geometric parameter | Interactive commands; no scripting API. |
| `varq_export_ifc` | `ifc_version` | No command-line option. |

## Changed results

- Export, render, PBR, V-Ray, Enscape, Lands, and VisualARQ tools return `applied` and `not_applied`. Read them instead of assuming a request took effect.
- `gh2_connect_many` returns `connected`, not `wired`. `gh2_apply_graph` returns `{ok, placed, wired, errors}` and now really resolves `from_key` / `to_key`.
- `gh_add_script_component` returns the final `inputs` and `outputs`. Ports a component refuses to remove are kept and reported.
- `urban_run_studio_pipeline` no longer needs `skip_steps=["solar"]` to avoid a wrong layer. Generate massing first; the pipeline reads the baked layer from state.
- `set_environment_map` succeeds when a render environment can be created. `intensity` depends on the texture exposing a multiplier and is listed under `not_applied` otherwise.

## Skills

The new `skills/` folder holds Agent Skills written against the tool source. Copy them into `~/.claude/skills/` or `~/.codex/skills/`, or paste a `SKILL.md` into ChatGPT Skill Creator. See `skills/README.md`.

## Verification limits

The C# changes compile against RhinoCommon 8 and are covered by unit tests of the Python contracts, but environment map assignment, script component port reshaping, and GH2 placement were not exercised in a live Rhino before this release. V-Ray and Enscape macros follow vendor documentation and were not run against installed plugins.

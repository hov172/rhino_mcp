# Upgrading to 0.20.0

0.20.0 unifies the Grasshopper 1 and Grasshopper 2 tool contracts and adds solve diagnostics to the GH2 write tools. The Rhino plugin changed, so install the matching plugin and restart Rhino and the AI client. All 358 tools remain. The [0.19.0 contract corrections](upgrade-0.19.0.md) and the [TLS requirements](secure-operation.md) still apply.

## Plugin update is required

Name-based `gh_add_component`, index-based GH1 ports, and the GH2 solve summary are implemented in the C# plugin. A 0.20.0 server against a 0.19.0 plugin will see `gh_add_component(type_name=...)` fail with "component_guid is required" and `solve` missing from GH2 results. Quit Rhino, install the 0.20.0 package or copy the bundle, then restart. On macOS the `rhino-mcp-configure` LaunchAgent re-installs from `/Users/Shared/rhino_mcp/plugin` at login, so a hand-copied bundle must also be copied there or it is rolled back.

## Renamed arguments

| Tool | Was | Now |
|---|---|---|
| `gh2_connect` | `from_instance`, `to_instance` | `from_guid`, `to_guid`, in the order `from_guid, from_output, to_guid, to_input` |

Calls that still pass `from_instance` or `to_instance` to `gh2_connect` fail validation. `gh2_connect_many` keeps accepting both spellings inside each wire.

## Widened arguments

| Tool | Change |
|---|---|
| `gh_add_component` | `component_guid` is optional when `type_name` is given. `x` and `y` default to 0. |
| `gh_connect_params`, `gh_disconnect_params` | `from_output` and `to_input` accept a 0-based index as well as a nickname, and default to 0. |
| `gh2_apply_graph`, `gh2_place_component`, `gh2_place_slider` | New `solve` flag, default `true`. |

## Changed result keys

| Tool | Added |
|---|---|
| `gh2_apply_graph`, `gh2_place_component`, `gh2_place_slider` | `solve: {solved, error_count, warning_count, errors, diagnostics}`, or `null` when `solve=false`. Each diagnostic is `{instance_guid, name, level, message}` with level `error`, `warning`, or `remark`. `ok` still reflects placement only. |
| `gh2_solve_graph` | `solved`, `warning_count`, `diagnostics` alongside the existing `error_count` and `errors`. |

## Verification limits

The GH2 solve summary, name-based GH1 placement, and index-based GH1 ports compile against RhinoCommon 8 and are covered at the Python contract level. They were not exercised in a live Rhino before this release; Grasshopper 2 needs Rhino 9 WIP.

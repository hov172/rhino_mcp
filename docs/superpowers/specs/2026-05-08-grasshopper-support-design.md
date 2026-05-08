# Grasshopper MCP Support — Design Spec
**Date:** 2026-05-08  
**Status:** Approved for implementation

---

## Overview

Add full Grasshopper support to rhino-mcp: canvas manipulation (place components, draw wires, manage groups), parameter control (sliders, panels, script components), solution execution, and baking to the Rhino document.

**30 Python MCP tools + 30 C# plugin commands** across 4 domain-split modules.

---

## 1. Architecture & Threading Model

Grasshopper's solver runs on a **background thread**. Canvas mutations must execute on the **main UI thread**. Every C# handler that touches the canvas wraps its body in `RhinoApp.InvokeOnUiThread(action)`. Read-only handlers that inspect already-computed data skip the thread hop.

```
MCP request (socket thread)
    → CommandDispatcher
    → GH*Handlers method
    → RhinoApp.InvokeOnUiThread(action)   ← all mutations
        → GH canvas / param manipulation
    → doc.ExpireSolution(true)            ← triggers background solver
    → wait for GH_Document.SolutionEnd event (with timeout)
    → serialize results → McpResponse
```

**Rhino version targets:**
- Rhino 8 primary — all 27 commands supported
- Rhino 7 best-effort — `GHCanvasHandlers`, `GHDocumentHandlers`, `GHSolutionHandlers` degrade gracefully; `gh_add_script_component` / `gh_set_script_code` return a "Rhino 8 required" error on Rhino 7

**NuGet addition to `RhinoMCPPlugin.csproj`:**
```xml
<PackageReference Include="Grasshopper" Version="8.17.25066.7001" ExcludeAssets="runtime" />
```

---

## 2. C# Command Surface (27 commands)

All commands registered in `CommandDispatcher.cs`. Read-only commands added to the `readOnly` HashSet to bypass undo recording.

### GHDocumentHandlers.cs
| Command | Params | Returns | Read-only |
|---|---|---|---|
| `gh_get_definition_info` | — | name, path, component_count, group_count, solution_state, error_count | ✓ |
| `gh_open_document` | `path` | name, component_count, solution_state | |
| `gh_new_document` | `name?` | definition_id | |
| `gh_save_document` | `path?` | saved_path | |
| `gh_close_document` | — | ok | |

**Key APIs:** `Grasshopper.Instances.ActiveCanvas?.Document`, `GH_DocumentIO.Open()`, `GH_DocumentIO.SaveQuiet()`, `GH_RhinoScriptInterface.CloseDocument()`

### GHCanvasHandlers.cs
| Command | Params | Returns | Read-only |
|---|---|---|---|
| `gh_search_components` | `query`, `limit?` | `[{name, category, subcategory, guid, description}]` | ✓ |
| `gh_list_components` | — | `[{instance_guid, name, type, x, y}]` | ✓ |
| `gh_get_canvas` | `include_wires?` | `{components[], wires[], groups[]}` | ✓ |
| `gh_get_component_info` | `instance_guid` | name, type, inputs[], outputs[], locked, state | ✓ |
| `gh_add_component` | `component_guid`, `x`, `y` | instance_guid, inputs[], outputs[] | |
| `gh_remove_component` | `instance_guid` | ok | |
| `gh_move_component` | `instance_guid`, `x`, `y` | ok | |
| `gh_rename_component` | `instance_guid`, `new_name` | ok | |
| `gh_set_component_comment` | `instance_guid`, `comment` | ok | |
| `gh_connect_wire` | `from_guid`, `from_output` (param name), `to_guid`, `to_input` (param name) | ok | |
| `gh_disconnect_wire` | `from_guid`, `from_output` (param name), `to_guid`, `to_input` (param name) | ok | |
| `gh_add_group` | `instance_guids[]`, `label?`, `color?` ([r,g,b] 0-255) | group_id | |

**Key APIs:** `Grasshopper.Instances.ComponentServer.FindObjects()`, `ComponentServer.EmitObject(guid)`, `GH_Document.AddObject()`, `Attributes.Pivot = new PointF(x,y)`, `IGH_Param.AddSource()`, `IGH_Param.RemoveSource()`, `GH_Group`

### GHParamHandlers.cs
| Command | Params | Returns | Read-only |
|---|---|---|---|
| `gh_get_output` | `instance_guid`, `output_name?` | `{values[], data_type, path_count}` | ✓ |
| `gh_get_solution_errors` | `instance_guid?` | `[{component, message, level}]` | ✓ |
| `gh_set_slider` | `instance_guid`, `value` | clamped_value | |
| `gh_set_panel` | `instance_guid`, `text` | ok | |
| `gh_set_number_param` | `instance_guid`, `values[]` | ok | |
| `gh_set_point_param` | `instance_guid`, `points[]` ([x,y,z] each) | ok | |
| `gh_add_script_component` | `language` (python/csharp), `code`, `inputs[]`, `outputs[]`, `x`, `y` | instance_guid | |
| `gh_set_script_code` | `instance_guid`, `code` | ok | |

**Key APIs:** `IGH_Param.VolatileData`, `GH_Component.RuntimeMessages()`, `GH_NumberSlider`, `GH_Panel`, `GH_PersistentParam<T>.SetPersistentData()`, `GH_Structure<T>`, script component GUIDs: C# `{0D6525D3-5B8A-4FE2-A24E-AB076F640835}`, Python `{6B17E69B-0F24-41F1-BFC3-FD80C0A049D8}`

### GHSolutionHandlers.cs
| Command | Params | Returns | Read-only |
|---|---|---|---|
| `gh_get_solution_state` | — | state (idle/computing/failed), duration_ms, error_count | ✓ |
| `gh_run_solution` | `instance_guids[]?`, `wait_ms?` (default 10000) | state, duration_ms, error_count, timed_out? | |
| `gh_bake_component` | `instance_guid`, `layer?` | `[rhino_object_guids]` | |
| `gh_bake_all` | `layer?` | `[rhino_object_guids]` | |
| `gh_enable_component` | `instance_guid`, `enabled` | ok | |

**Key APIs:** `GH_Document.SolutionState` (GH_ProcessStep enum), `GH_Document.ExpireSolution(true)`, `GH_Document.SolutionEnd` event, `GH_RhinoScriptInterface.BakeDataInObject()`, `((GH_ActiveObject)comp).Locked`

---

## 3. Python MCP Tool Layer (30 tools)

Four new modules in `src/rhmcp/tools/`. Auto-discovered by existing `pkgutil.iter_modules()` loader. All tools are **plugin-only** — no rhinocode fallback (GH has no CLI equivalent). `OSError` on socket → structured error returned.

### gh_document.py (5 tools)
```
gh_open_definition(path, rhino_id?)           readOnlyHint=True
gh_new_definition(name?, rhino_id?)           destructiveHint=True
gh_save_definition(path?, rhino_id?)          destructiveHint=True
gh_close_definition(rhino_id?)                destructiveHint=True
gh_get_definition_info(rhino_id?)             readOnlyHint=True
```

### gh_canvas.py (9 tools)
```
gh_search_components(query, limit?, rhino_id?)                           readOnlyHint=True
gh_list_components(rhino_id?)                                            readOnlyHint=True
gh_get_canvas(include_wires?, rhino_id?)                                 readOnlyHint=True
gh_get_component_info(instance_guid, rhino_id?)                          readOnlyHint=True
gh_add_component(component_guid, x, y, rhino_id?)                        destructiveHint=True
gh_remove_component(instance_guid, rhino_id?)                            destructiveHint=True
gh_move_component(instance_guid, x, y, rhino_id?)                        destructiveHint=True
gh_rename_component(instance_guid, new_name, rhino_id?)                  destructiveHint=True
gh_set_component_comment(instance_guid, comment, rhino_id?)              destructiveHint=True
gh_connect_params(from_guid, from_output, to_guid, to_input, rhino_id?)  destructiveHint=True
gh_disconnect_params(from_guid, from_output, to_guid, to_input, rhino_id?) destructiveHint=True
gh_add_group(instance_guids, label?, color?, rhino_id?)                  destructiveHint=True
```

### gh_params.py (8 tools)
```
gh_set_slider(instance_guid, value, rhino_id?)                                      destructiveHint=True
gh_set_panel(instance_guid, text, rhino_id?)                                        destructiveHint=True
gh_set_number_param(instance_guid, values: list[float], rhino_id?)                  destructiveHint=True
gh_set_point_param(instance_guid, points: list[list[float]], rhino_id?)             destructiveHint=True
gh_get_output(instance_guid, output_name?, rhino_id?)                               readOnlyHint=True
gh_get_errors(instance_guid?, rhino_id?)                                            readOnlyHint=True
gh_add_script_component(language, code, inputs, outputs, x, y, rhino_id?)          destructiveHint=True
gh_set_script_code(instance_guid, code, rhino_id?)                                  destructiveHint=True
```

### gh_solution.py (5 tools)
```
gh_run_solution(instance_guids?, wait_ms?, rhino_id?)   destructiveHint=True
gh_get_solution_state(rhino_id?)                        readOnlyHint=True
gh_bake(instance_guid, layer?, rhino_id?)               destructiveHint=True
gh_bake_all(layer?, rhino_id?)                          destructiveHint=True
gh_enable_component(instance_guid, enabled, rhino_id?)  destructiveHint=True
```

**Note:** `gh_canvas.py` has 12 tools (9 listed above + connect/disconnect counted as canvas ops), `gh_params.py` has 8. Total: 5 + 12 + 8 + 5 = **30 Python MCP tools**.

---

## 4. Error Handling

| Scenario | Response |
|---|---|
| GH plugin not loaded | `{"ok": false, "error": "Grasshopper is not loaded"}` |
| No active GH document | `{"ok": false, "error": "No active Grasshopper definition"}` |
| Component GUID not found | `{"ok": false, "error": "Component {guid} not found in active definition"}` |
| Solution timeout | `{"ok": true, "timed_out": true, "state": "computing"}` |
| Threading violation | Exception caught in `InvokeOnUiThread`, returned as structured error |
| Baking stale/errored geometry | Warning included in response: `{"ok": true, "warning": "Solution has errors — baked geometry may be incomplete", "objects": [...]}` |
| Script component on Rhino 7 | `{"ok": false, "error": "Script components require Rhino 8"}` |

---

## 5. Testing

### Unit tests (no Rhino, extend `tests/test_tools_unit.py`)
- `gh_open_definition` with no path → validation error
- `gh_add_component` with malformed GUID → error before socket call
- `gh_connect_params` with missing required param → error
- `gh_set_slider` with non-numeric value → type error
- Plugin socket `OSError` → all GH tools return structured error (no fallback)

### Integration tests (`tests/test_gh_integration.py`, `@pytest.mark.integration`)
- Full round-trip: new definition → add slider + component → connect wire → run solution → read output → bake → verify Rhino objects via `get_rhino_objects()`
- `gh_search_components("circle")` → at least one result with guid/name/category
- `gh_bake()` GUIDs appear in subsequent `get_rhino_objects()` call
- Script component: add Python script → set code → run → `gh_get_output()` returns expected value

---

## 6. File Checklist

**New C# files:**
- `rhino_plugin/RhinoMCPPlugin/GHDocumentHandlers.cs`
- `rhino_plugin/RhinoMCPPlugin/GHCanvasHandlers.cs`
- `rhino_plugin/RhinoMCPPlugin/GHParamHandlers.cs`
- `rhino_plugin/RhinoMCPPlugin/GHSolutionHandlers.cs`

**Modified C# files:**
- `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs` — 27 new cases + readOnly entries
- `rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj` — Grasshopper NuGet reference

**New Python files:**
- `src/rhmcp/tools/gh_document.py`
- `src/rhmcp/tools/gh_canvas.py`
- `src/rhmcp/tools/gh_params.py`
- `src/rhmcp/tools/gh_solution.py`

**Modified Python files:**
- `tests/test_tools_unit.py` — GH unit tests appended
- `tests/test_gh_integration.py` — new file

**No changes needed:** `__init__.py`, `backend.py`, `Protocol.cs` (all compatible as-is)

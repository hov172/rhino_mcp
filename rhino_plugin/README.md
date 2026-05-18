# RhinoMCPPlugin

The Rhino-side TCP socket server for the Rhino MCP project. This plugin runs inside Rhino 3D and handles all incoming commands from the Python MCP server.

---

## Rhino Commands

| Command | Description |
|---|---|
| `MCPStart` | Start the socket server. Binds to `127.0.0.1:1999` by default. Prints confirmation: `RhinoMCP: Listening on 127.0.0.1:1999`. |
| `MCPStop` | Stop the socket server and release the port. |
| `MCPStatus` | Print the current server status. Prints `Rhino MCP server running on {address}:{port}` or `Rhino MCP server is stopped.` |
| `MCPHelp` | Open the full documentation in the default browser. |

**Auto-start tip:** Add `MCPStart` to *Rhino Options → General → Command Lists → Startup commands* so the server starts automatically every time Rhino opens.

---

## Protocol

The Python MCP server connects over a local TCP socket and sends newline-delimited JSON messages. Each message has the shape:

```json
{"type": "<command_type>", "params": { ... }, "secret": "<psk-or-omit>"}
```

The `secret` field is optional. Include it when `RHINO_MCP_PLUGIN_SECRET` is configured on the plugin side — the plugin rejects requests with a missing or wrong secret.

The plugin dispatches to a C# handler, executes on the Rhino main UI thread via `RhinoApp.InvokeOnUiThread`, and replies with:

```json
{"status": "ok", "result": { ... }}
```

or on error:

```json
{"status": "error", "message": "<message>"}
```

---

## Supported Command Types

The plugin handles the following command types (dispatched in `CommandDispatcher.cs`):

### Geometry & Objects

| Command | Description |
|---|---|
| `create_object` | Create a single geometric object (box, sphere, cylinder, cone, torus, curve, surface, mesh, text, etc.) |
| `create_objects` | Batch create multiple objects in one round-trip |
| `get_objects` | List objects with optional type/layer/name/color filters; `include_hidden=true` includes hidden objects |
| `get_object_info` | Get detailed properties of a specific object by GUID |
| `modify_object` | Transform (move/rotate/scale) or change attributes of an object |
| `modify_objects` | Batch attribute/transform updates |
| `delete_object` | Delete one or more objects by GUID |
| `select_objects` | Select objects by GUID, name, layer, or type |
| `get_selected_objects` | Return GUIDs and properties of the current selection |

### Layers & Materials

| Command | Description |
|---|---|
| `manage_layer` | Create, delete, rename, recolor, or set the current layer |
| `get_materials` | List all document materials |
| `create_material` | Create a standard or PBR material |
| `set_object_material` | Assign a material to objects |
| `delete_material` | Delete a material |

### Document & Views

| Command | Description |
|---|---|
| `get_document_summary` | Object counts, layer list, materials, units, tolerance. Returns `object_count` and `unit_system` (snake_case). |
| `save_document` | Save the active document |
| `export_document` | Export to `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg`, `.pdf` |
| `set_view` | Activate a named view or set camera position/target/lens |
| `capture_viewport` | Capture the active viewport to a PNG file |

### Scripting

| Command | Description |
|---|---|
| `execute_rhinoscript_python_code` | Run Python code inside Rhino (RhinoScriptSyntax + RhinoCommon); captures both `print()` output and command-window lines |
| `execute_rhinocommon_csharp_code` | Run C# code via Roslyn scripting |
| `run_command` | Execute a Rhino command macro string; `echo=true` echoes it to the command history; response includes captured `output` |
| `undo` | Undo the last N operations (`steps`); stops automatically when the stack is exhausted and returns `undone_steps` / `requested_steps` |
| `redo` | Redo the last N undone operations (`steps`); stops automatically when the redo stack is exhausted |

### Plugins

| Command | Description |
|---|---|
| `list_plugins` | Return all loaded Rhino plugins with name, GUID, loaded state, and path |
| `get_plugin_commands` | List commands registered by a specific plugin |

### Grasshopper Canvas

All GH commands require Grasshopper to be open.

| Command | Description |
|---|---|
| `gh_search_components` | Search the GH component library |
| `gh_list_components` | List all objects on the active canvas |
| `gh_get_canvas` | Full canvas snapshot (components, wires, groups) |
| `gh_get_component_info` | Detailed info for one component |
| `gh_add_component` | Place a component by GUID |
| `gh_remove_component` | Remove a component |
| `gh_move_component` | Move a component to new canvas coordinates |
| `gh_connect_wire` | Draw a wire between two parameters |
| `gh_disconnect_wire` | Remove a wire |
| `gh_add_group` | Create a named group |
| `gh_set_slider` | Set a number slider value |
| `gh_set_panel` | Set panel text |
| `gh_set_number_param` | Set persistent number values |
| `gh_set_point_param` | Set persistent point values |
| `gh_get_output` | Read computed output data |
| `gh_get_errors` | Get runtime errors and warnings |
| `gh_get_solution_state` | Check solver state |
| `gh_run_solution` | Trigger a solution and wait |
| `gh_bake` | Bake a component's geometry into the Rhino doc |
| `gh_bake_all` | Bake all bakeable geometry |
| `gh_enable_component` | Enable or disable a component |
| `gh_get_definition_info` | Definition metadata |
| `gh_new_definition` | Create a new blank definition |
| `gh_open_definition` | Open a `.gh` / `.ghx` file |
| `gh_save_definition` | Save the active definition |
| `gh_close_definition` | Close the active definition |

### Grasshopper 2 Canvas

All GH2 commands require **Rhino 9** with Grasshopper 2 loaded. Grasshopper 2 is not available in stable Rhino 8. Commands use runtime reflection — no compile-time dependency on Grasshopper2.dll. On Rhino 8, all GH2 commands return a clear error and degrade gracefully.

| Command | Description |
|---|---|
| `gh2_start` | Launch the Grasshopper 2 editor. |
| `gh2_get_canvas_graph` | Full snapshot of the active GH2 canvas: components, wires, volatile data samples. `sample_size` controls how many data items to return per output. |
| `gh2_apply_graph` | Atomically place components and wire them in one call. Accepts `components` (list of `{key, type_name, x, y}`) and `wires` (list of `{from_key, from_output, to_key, to_input}`). Returns `{ok, placed: {key: instanceGuid}, wired: N, errors: [...]}`. |
| `gh2_place_component` | Place a GH2 component by `name` (type name) or `component_guid`. Returns `instance_guid`. |
| `gh2_place_slider` | Place a GH2 Number Slider with `min`, `max`, `value`, `decimals`, and canvas `x`/`y`. Returns `instance_guid`. |
| `gh2_connect` | Wire a single output to an input. `from_output` and `to_input` can be index (int) or param name (str). |
| `gh2_connect_many` | Wire multiple connections at once; continues past individual failures. Returns `{ok, wired: N, errors: [...]}`. |
| `gh2_describe_component` | Get metadata for a component (category, description, input/output param names and types). Accepts `instance_guid` or `name`. |
| `gh2_search_components` | Search available GH2 components by name, nickname, or description. Optional `category` filter. |
| `gh2_solve_graph` | Expire and re-solve the active GH2 canvas. Returns list of errors. |
| `gh2_clear_canvas` | Clear all objects from the active GH2 canvas. Requires `confirm: true`. |

---

## Thread Safety

All command handlers that touch Rhino or Grasshopper state run on the Rhino main UI thread via `RhinoApp.InvokeOnUiThread`. The socket listener runs on a background thread. Never call Rhino or Grasshopper APIs directly from the socket thread — doing so causes crashes.

---

## Upgrading

Having two copies of the plugin installed simultaneously causes a port conflict — both attempt to bind port 1999 on load and the second one fails silently. Before upgrading, remove the old installation:

```bash
# macOS — remove from both possible locations
rm -f "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp"
rm -rf "$HOME/Library/Application Support/McNeel/Rhinoceros/packages/8.0/rhino-mcp"
```

```powershell
# Windows
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\8.0\Plug-ins\rhino-mcp.rhp" -ErrorAction SilentlyContinue
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\packages\8.0\rhino-mcp" -Recurse -ErrorAction SilentlyContinue
```

Restart Rhino, then install the new version.

---

## Building

```bash
# Requires .NET 8 SDK
./scripts/build-plugin.sh
```

On macOS, the PostBuild step in `RhinoMCPPlugin.csproj` copies the built `rhino-mcp.rhp` to `/Applications/Rhino 8.app/Contents/PlugIns/` automatically. Restart Rhino after each build.

> **If you previously installed via Yak or PackageManager**, remove the Yak package before building from source — otherwise both copies will try to load and the build copy will lose the port race. Run `rm -rf "$HOME/Library/Application Support/McNeel/Rhinoceros/packages/8.0/rhino-mcp"` (macOS) first.

```bash
# Package for Yak distribution
./scripts/package-plugin.sh
```

The package script also stages release assets in `rhino_plugin/release/` so GitHub releases can ship both the direct-install `.rhp` and the Yak package together.
The repository also includes `.github/workflows/release-plugin.yml` for automated GitHub Release uploads from a self-hosted macOS runner with Rhino installed.

---

## Environment

| Setting | Default | Description |
|---|---|---|
| Bind address | `127.0.0.1` | Set via `RHINO_MCP_BIND_HOST` env var. Use `0.0.0.0` for network access. |
| Port | `1999` | TCP port the plugin listens on |
| Protocol | TCP, JSON (one request per connection) | |
| Rhino versions | Rhino 7 and Rhino 8 | |
| Target framework | `net8.0` | |
| `RHINO_MCP_BIND_HOST` | `127.0.0.1` | Bind address. `0.0.0.0` = any interface. |
| `RHINO_MCP_PLUGIN_SECRET` | *(unset)* | Pre-shared key for authentication. Required when binding to a non-loopback address. |

**Slot Announcement**

The plugin writes a `{pid}.json` file to `Path.GetTempPath()/rhino-mcp-slots/` when the TCP listener starts. This allows the Python server to discover all running Rhino instances via `get_rhino_instances`. The file is removed when the plugin unloads or the server stops.

JSON fields: `pid`, `host`, `port`, `version`, `rhino_version`, `started_at`.

# RhinoMCPPlugin

The Rhino-side TCP socket server for the Rhino MCP project. This plugin runs inside Rhino 3D and handles all incoming commands from the Python MCP server.

---

## Rhino Commands

| Command | Description |
|---|---|
| `MCPStart` | Start the socket server. Binds to `127.0.0.1:1999` by default. Prints confirmation: `RhinoMCP: Listening on 127.0.0.1:1999`. |
| `MCPStop` | Stop the socket server and release the port. |
| `MCPStatus` | Print the current server status (running / stopped, bound address). |

**Auto-start tip:** Add `MCPStart` to *Rhino Options → General → Command Lists → Startup commands* so the server starts automatically every time Rhino opens.

---

## Protocol

The Python MCP server connects over a local TCP socket and sends newline-delimited JSON messages. Each message has the shape:

```json
{"type": "<command_type>", "params": { ... }}
```

The plugin dispatches to a C# handler, executes on the Rhino main UI thread via `RhinoApp.InvokeOnUiThread`, and replies with:

```json
{"ok": true, "result": { ... }}
```

or on error:

```json
{"ok": false, "error": "<message>"}
```

---

## Supported Command Types

The plugin handles the following command types (dispatched in `CommandDispatcher.cs`):

### Geometry & Objects

| Command | Description |
|---|---|
| `create_object` | Create a single geometric object (box, sphere, cylinder, cone, torus, curve, surface, mesh, text, etc.) |
| `create_objects` | Batch create multiple objects in one round-trip |
| `get_objects` | List objects with optional type/layer/name filters |
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
| `get_document_summary` | Object counts, layer list, materials, units, tolerance |
| `save_document` | Save the active document |
| `export_document` | Export to `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg`, `.pdf` |
| `set_view` | Activate a named view or set camera position/target/lens |
| `capture_viewport` | Capture the active viewport to a PNG file |

### Scripting

| Command | Description |
|---|---|
| `execute_rhinoscript_python_code` | Run Python code inside Rhino (RhinoScriptSyntax + RhinoCommon) |
| `execute_rhinocommon_csharp_code` | Run C# code via Roslyn scripting |
| `run_command` | Execute a Rhino command macro string |

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

---

## Thread Safety

All command handlers that touch Rhino or Grasshopper state run on the Rhino main UI thread via `RhinoApp.InvokeOnUiThread`. The socket listener runs on a background thread. Never call Rhino or Grasshopper APIs directly from the socket thread — doing so causes crashes.

---

## Building

```bash
# Requires .NET 8 SDK
./scripts/build-plugin.sh
```

On macOS, the PostBuild step in `RhinoMCPPlugin.csproj` copies the built `rhino-mcp.rhp` to `/Applications/Rhino 8.app/Contents/PlugIns/` automatically. Restart Rhino after each build.

```bash
# Package for Yak distribution
./scripts/package-plugin.sh
```

The package script also stages release assets in `rhino_plugin/release/` so GitHub releases can ship both the direct-install `.rhp` and the Yak package together.
The repository also includes `.github/workflows/release-plugin.yml` for automated GitHub Release uploads from a self-hosted macOS runner with Rhino installed.

---

## Environment

| Setting | Value |
|---|---|
| Bind address | `127.0.0.1` |
| Port | `1999` |
| Protocol | TCP, newline-delimited JSON |
| Rhino versions | Rhino 7 and Rhino 8 |
| Target framework | `net8.0` |

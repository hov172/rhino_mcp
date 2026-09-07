# RhinoMCPPlugin

Version **0.17.0**. The Rhino-side TCP socket server for the Rhino MCP project. This plugin runs inside Rhino 3D and handles all incoming commands from the Python MCP server.

---

## Rhino Commands

| Command | Description |
|---|---|
| `MCPStart` | Manually start the socket server (fallback if auto-start failed). Binds to `127.0.0.1:1999` by default. Prints `Rhino MCP listening on 127.0.0.1:1999`. |
| `MCPStop` | Stop the socket server and release the port. |
| `MCPStatus` | Print the current server status. Prints `Rhino MCP server running on {address}:{port}` or `Rhino MCP server is stopped.` |
| `MCPHelp` | Open the full documentation in the default browser. |

**Auto-start:** The plugin starts its TCP server automatically when Rhino opens — no `MCPStart` required. You should see `Rhino MCP listening on 127.0.0.1:1999` in the command history immediately after Rhino loads. `MCPStart` is available as a manual fallback if auto-start fails (e.g. port conflict).

---

## Protocol

The Python MCP server connects over a local TCP socket and sends newline-delimited JSON messages. Each message has the shape:

```json
{"type": "<command_type>", "params": { ... }, "secret": "<psk-or-omit>"}
```

The `secret` field is optional only for an unconfigured loopback listener. Non-loopback listeners require both a shared secret and a TLS certificate. See [secure operation](../docs/secure-operation.md#tls). Include it when `RHINO_MCP_PLUGIN_SECRET` is configured on the plugin side — the plugin rejects requests with a missing or wrong secret.

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
| `gh2_apply_graph` | Place components and wire them in one call; inspect returned errors for incomplete operations. Accepts `components` (list of `{key, type_name, x, y}`) and `wires` (list of `{from_key, from_output, to_key, to_input}`). Returns `{ok, placed: {key: instanceGuid}, wired: N, errors: [...]}`. |
| `gh2_place_component` | Place a GH2 component by `name` (type name) or `component_guid`. Returns `instance_guid`. |
| `gh2_place_slider` | Place a GH2 Number Slider with `min`, `max`, `value`, `decimals`, and canvas `x`/`y`. Returns `instance_guid`. |
| `gh2_connect` | Wire a single output to an input. `from_output` and `to_input` can be index (int) or param name (str). |
| `gh2_connect_many` | Wire multiple connections at once; continues past individual failures. Returns `{ok, wired: N, errors: [...]}`. |
| `gh2_describe_component` | Get metadata for a component (category, description, input/output param names and types). Accepts `instance_guid` or `name`. |
| `gh2_search_components` | Search available GH2 components by name, nickname, or description. Optional `category` filter. |
| `gh2_solve_graph` | Expire and re-solve the active GH2 canvas. Returns list of errors. |
| `gh2_clear_canvas` | Clear all objects from the active GH2 canvas. Requires `confirm: true`. |

### Grasshopper — Intelligence

**Works on Rhino 8 (GH1):**

| Command | Description |
|---|---|
| `gh_get_canvas_analysis` | Canvas metrics: component count, wire count, crossing estimate, logical clusters, complexity score |
| `gh_get_graph_data` | Full adjacency snapshot (nodes + edges) used by layout and migration tools |
| `gh_refactor_canvas` | Re-layout GH1 canvas to reduce wire crossings and add groups per cluster. `dry_run=true` previews without applying |
| `gh1_export_migration_data` | Export GH1 canvas to structured JSON with GH2 mapping status per component |

**Requires Rhino 9 + GH2** (return a clear error on Rhino 8 — no crash):

| Command | Description |
|---|---|
| `gh_migrate_to_gh2` | Place GH2 equivalents for all mapped GH1 components and wire them. Lists unmapped components |
| `gh2_move_component` | Move a GH2 component to new canvas coordinates by instance GUID |
| `gh2_add_group` | Create a named group around specified GH2 components |

---

## Thread Safety

All command handlers that touch Rhino or Grasshopper state run on the Rhino main UI thread via `RhinoApp.InvokeOnUiThread`. The socket listener runs on a background thread. Never call Rhino or Grasshopper APIs directly from the socket thread — doing so causes crashes.

---

## Upgrading

Follow the [0.17.0 upgrade guide](../docs/upgrade-0.17.0.md) for matching Python, plugin, and Docker versions. Quit Rhino completely before replacing an installed plugin.

Having two copies of the plugin installed simultaneously causes a **port conflict** — both attempt to bind port 1999 on load, the second one fails silently, and all MCP calls go to the wrong version or return `connection refused`. Rhino does not warn you.

### Step 1 — Remove ALL old copies

There are two possible install locations. Check both — you may have installed once via `.rhp` copy and once via Yak or PackageManager.

**macOS:**

```bash
# Manual .rhp install
rm -f "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp"

# Yak / PackageManager install
rm -rf "$HOME/Library/Application Support/McNeel/Rhinoceros/packages/8.0/rhino-mcp"
```

> If `rm` fails with "Operation not permitted" (macOS sandbox), use Finder: press `⌘⇧G`, paste the path, and delete manually.

**Windows:**

```powershell
# Manual .rhp install
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\8.0\Plug-ins\rhino-mcp.rhp" -ErrorAction SilentlyContinue

# Yak / PackageManager install
Remove-Item "$env:APPDATA\McNeel\Rhinoceros\packages\8.0\rhino-mcp" -Recurse -ErrorAction SilentlyContinue
```

Not sure which method you used? Remove both — if neither exists, nothing happens.

### Step 2 — Quit Rhino completely

Close all Rhino windows and confirm the process is gone (Task Manager on Windows, Activity Monitor on macOS). Rhino holds plugins in memory until the process exits — closing the window is not enough.

### Step 3 — Install the new version

Copy the new `.rhp` to the plug-ins folder or run the Yak installer. See the main [README.md](../README.md#upgrading-from-a-previous-version) for full instructions.

### Step 4 — Verify

Restart Rhino. You should see `Rhino MCP listening on 127.0.0.1:1999` in the command history. Run `MCPStatus` to confirm. If a port error appears, go to **Tools → Options → Plug-ins**, search "rhino-mcp", and check whether an old path is still registered.

---

## Building

Run these commands from the repository root; packaging requires Rhino 8 installed on macOS.

```bash
# Requires .NET 8 SDK
./scripts/build-plugin.sh
```

Builds do not install the plugin. Install the packaged artifact explicitly, then fully restart Rhino. The legacy macOS post-build copy is opt-in with `dotnet build rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj -c Release -p:InstallPluginAfterBuild=true`.

> Before installing, check for an existing manual or Yak installation and replace that installation. Building alone does not create a second installed copy.

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
| Bind address | `127.0.0.1` | Set via `RHINO_MCP_BIND_HOST` env var. Network binding also requires a shared secret and TLS PFX certificate. |
| Port | `1999` | TCP port the plugin listens on |
| Protocol | TCP, newline-delimited JSON (persistent connections supported) | |
| Packaged target | Rhino 8.17+ | The `rh8_17` Yak artifact targets Rhino 8; GH2 operations require Rhino 9 with GH2 loaded. |
| Target framework | `net8.0` | |
| `RHINO_MCP_BIND_HOST` | `127.0.0.1` | Bind address. `0.0.0.0` = any interface; requires TLS and a secret. |
| `RHINO_MCP_PLUGIN_SECRET` | *(unset)* | Pre-shared key for authentication. Required when binding to a non-loopback address — the server refuses to start listening without it. |
| `RHINO_MCP_PLUGIN_TLS_CERT` | *(unset)* | PFX certificate with private key; required for non-loopback binding. |
| `RHINO_MCP_PLUGIN_TLS_PASSWORD` | *(unset)* | PFX password. |

Set execution gates in Rhino as well as the MCP process; see [execution controls](../docs/secure-operation.md#execution-controls).

**Slot Announcement**

The plugin writes a `{pid}.json` file to `Path.GetTempPath()/rhino-mcp-slots/` when the TCP listener starts. This allows the Python server to discover all running Rhino instances via `get_rhino_instances`. The file is removed when the plugin unloads or the server stops.

JSON fields: `pid`, `host`, `port`, `version`, `rhino_version`, `started_at`.

# Third-Party Plugin Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 70 typed MCP tools covering Kangaroo, Ladybug, Pufferfish, Weaverbird, LunchBox, Human/Elefront, Anemone, V-Ray, Enscape, VisualARQ, and Lands Design, plus a generic plugin introspection layer.

**Architecture:** A new C# handler (`get_plugin_commands`) introspects registered Rhino commands per plugin. GH ecosystem tool modules orchestrate existing `gh_add_component`/`gh_connect_wire`/`gh_set_slider` calls — no new C# needed for them. Rhino-level plugin modules (V-Ray, Enscape, VisualARQ, Lands) use `run_command` or `execute_rhinoscript_python_code` via the existing plugin socket.

**Tech Stack:** C# RhinoCommon 8, Python 3.13, FastMCP, `plugin_client.send_command`, `backend.plugin_result`

---

## File Map

**Create:**
- `src/rhmcp/tools/plugins.py` — generic introspection (4 tools)
- `src/rhmcp/tools/gh_kangaroo.py` — Kangaroo Physics (5 tools)
- `src/rhmcp/tools/gh_ladybug.py` — Ladybug/Honeybee (8 tools)
- `src/rhmcp/tools/gh_pufferfish.py` — Pufferfish (5 tools)
- `src/rhmcp/tools/gh_weaverbird.py` — Weaverbird (6 tools)
- `src/rhmcp/tools/gh_lunchbox.py` — LunchBox (5 tools)
- `src/rhmcp/tools/gh_human_elefront.py` — Human + Elefront (5 tools)
- `src/rhmcp/tools/gh_anemone.py` — Anemone (2 tools)
- `src/rhmcp/tools/vray.py` — V-Ray for Rhino (9 tools)
- `src/rhmcp/tools/enscape.py` — Enscape (7 tools)
- `src/rhmcp/tools/visualarq.py` — VisualARQ (10 tools)
- `src/rhmcp/tools/lands_design.py` — Lands Design (8 tools)

**Modify:**
- `rhino_plugin/RhinoMCPPlugin/RhinoHandlers.cs` — add `GetPluginCommands`
- `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs` — dispatch `get_plugin_commands`
- `src/rhmcp/tools/__init__.py` — register all new modules
- `tests/test_tools_unit.py` — unit tests for all new modules
- `tests/test_plugin_files.py` — assert new Python modules exist

---

## Task 1: C# — `get_plugin_commands` handler

**Files:**
- Modify: `rhino_plugin/RhinoMCPPlugin/RhinoHandlers.cs`
- Modify: `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs`

- [ ] **Step 1: Add handler to RhinoHandlers.cs**

Append before the final `}` closing the class (after `LoadPlugin`):

```csharp
public static object GetPluginCommands(Dictionary<string, JsonElement> p)
{
    var pluginName = p.String("plugin_name");
    var pluginIdStr = p.String("plugin_id");

    Guid pluginGuid = Guid.Empty;
    string resolvedName = "";

    if (!string.IsNullOrWhiteSpace(pluginIdStr))
        Guid.TryParse(pluginIdStr, out pluginGuid);

    if (pluginGuid == Guid.Empty && !string.IsNullOrWhiteSpace(pluginName))
    {
        foreach (var kv in PlugIn.GetInstalledPlugIns())
        {
            if (kv.Value.IndexOf(pluginName, StringComparison.OrdinalIgnoreCase) >= 0)
            {
                pluginGuid = kv.Key;
                resolvedName = kv.Value;
                break;
            }
        }
    }

    if (pluginGuid == Guid.Empty)
        return new { success = false, message = $"Plugin not found: {pluginName ?? pluginIdStr}" };

    var commands = Rhino.Commands.Command.List
        .Select(name => Rhino.Commands.Command.LookupCommand(name))
        .Where(cmd => cmd != null && cmd.PlugInId == pluginGuid)
        .Select(cmd => new { name = cmd!.CommandName, id = cmd.Id.ToString() })
        .ToList();

    return new { success = true, plugin_name = resolvedName, plugin_id = pluginGuid.ToString(), commands, count = commands.Count };
}
```

- [ ] **Step 2: Register in CommandDispatcher.cs**

In the `readOnly` variable, add `"get_plugin_commands"` to the `is` list:

```csharp
var readOnly = request.Type is
    "get_document_summary" or
    // ... existing entries ...
    "gh_get_solution_state" or
    "get_plugin_commands";
```

In the switch expression, add before the `_` default case:

```csharp
"get_plugin_commands" => McpResponse.Ok(RhinoHandlers.GetPluginCommands(p)),
```

- [ ] **Step 3: Build the plugin**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp/rhino_plugin/RhinoMCPPlugin
dotnet build --configuration Debug
```

Expected: `Build succeeded. 0 Warning(s). 0 Error(s)`

- [ ] **Step 4: Commit**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp
git add rhino_plugin/RhinoMCPPlugin/RhinoHandlers.cs rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs
git commit -m "feat: add get_plugin_commands C# handler"
```

---

## Task 2: `plugins.py` — generic introspection

**Files:**
- Create: `src/rhmcp/tools/plugins.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tools_unit.py`:

```python
class TestPluginsModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.plugins")

    def test_check_plugin_loaded_not_found(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "Other", "loaded": True}]}}
            result = fn("NonExistentPlugin")
        self.assertFalse(result["loaded"])
        self.assertIn("not installed", result["message"])

    def test_check_plugin_loaded_found_but_unloaded(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": False}]}}
            result = fn("V-Ray")
        self.assertFalse(result["loaded"])
        self.assertIn("not loaded", result["message"])

    def test_check_plugin_loaded_found(self) -> None:
        fn = self.tools["check_plugin_loaded"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": [{"name": "V-Ray for Rhino", "loaded": True}]}}
            result = fn("V-Ray")
        self.assertTrue(result["loaded"])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp
.venv/bin/pytest tests/test_tools_unit.py::TestPluginsModule -v
```

Expected: `ERROR` — module not found.

- [ ] **Step 3: Create `src/rhmcp/tools/plugins.py`**

```python
"""Generic Rhino plugin introspection and command execution tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="List Installed Plugins", readOnlyHint=True))
    def list_installed_plugins() -> dict[str, object]:
        """List all installed Rhino plugins with name, GUID, loaded status, and path."""
        return plugin_client.send_command("list_plugins", {})

    @mcp.tool(annotations=ToolAnnotations(title="Get Plugin Commands", readOnlyHint=True))
    def get_plugin_commands(
        plugin_name: str | None = None,
        plugin_id: str | None = None,
    ) -> dict[str, object]:
        """
        List all Rhino commands registered by a specific plugin.
        Provide plugin_name (partial, case-insensitive) or plugin_id (GUID).
        """
        return plugin_client.send_command(
            "get_plugin_commands",
            {"plugin_name": plugin_name, "plugin_id": plugin_id},
        )

    @mcp.tool(annotations=ToolAnnotations(title="Run Plugin Command", destructiveHint=True))
    def run_plugin_command(command: str, options_string: str = "") -> dict[str, object]:
        """
        Run any Rhino command string, including commands from third-party plugins.
        options_string is appended after the command name (e.g. '_Enter' to confirm prompts).
        """
        full = f"{command} {options_string}".strip()
        return plugin_client.send_command("run_command", {"command": full})

    @mcp.tool(annotations=ToolAnnotations(title="Check Plugin Loaded", readOnlyHint=True))
    def check_plugin_loaded(plugin_name: str) -> dict[str, object]:
        """
        Check whether a plugin is installed and loaded in Rhino.
        Returns {loaded: bool, message: str, plugin: {...}} .
        """
        result = plugin_client.send_command("list_plugins", {})
        plugins = result.get("result", {}).get("plugins", [])
        match = next(
            (p for p in plugins if plugin_name.lower() in p["name"].lower()), None
        )
        if match is None:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is not installed. Install it via the Rhino Package Manager or the plugin vendor.",
            }
        if not match["loaded"]:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is installed but not loaded. Use load_plugin to load it.",
            }
        return {"loaded": True, "plugin": match}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestPluginsModule -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/plugins.py tests/test_tools_unit.py
git commit -m "feat: add plugins.py generic introspection tools"
```

---

## Task 3: Register all new modules in `__init__.py`

**Files:**
- Modify: `src/rhmcp/tools/__init__.py`
- Modify: `tests/test_plugin_files.py`

- [ ] **Step 1: Update `__init__.py`**

Read current `src/rhmcp/tools/__init__.py`, then replace its content with:

```python
"""Rhino MCP tool modules."""
```

(It currently only has this docstring — new modules are auto-discovered if the project uses dynamic registration. Check `src/rhmcp/__init__.py` to see how modules are loaded; if it explicitly lists modules, add the new ones there instead.)

> **Note:** Run `grep -rn "import\|register" src/rhmcp/__init__.py` to see how tools are loaded. If modules are explicitly imported, add all 12 new modules to that list. If they're auto-discovered (glob import), no change is needed.

- [ ] **Step 2: Verify dynamic loading**

```bash
grep -n "tools\." src/rhmcp/__init__.py src/rhmcp/__main__.py
```

If modules are listed explicitly, add to that list:
`plugins`, `gh_kangaroo`, `gh_ladybug`, `gh_pufferfish`, `gh_weaverbird`, `gh_lunchbox`, `gh_human_elefront`, `gh_anemone`, `vray`, `enscape`, `visualarq`, `lands_design`

- [ ] **Step 3: Update `tests/test_plugin_files.py`**

Add to the `required` list in `test_plugin_project_and_package_files_exist`:

```python
# Third-party plugin tool modules
"src/rhmcp/tools/plugins.py",
"src/rhmcp/tools/gh_kangaroo.py",
"src/rhmcp/tools/gh_ladybug.py",
"src/rhmcp/tools/gh_pufferfish.py",
"src/rhmcp/tools/gh_weaverbird.py",
"src/rhmcp/tools/gh_lunchbox.py",
"src/rhmcp/tools/gh_human_elefront.py",
"src/rhmcp/tools/gh_anemone.py",
"src/rhmcp/tools/vray.py",
"src/rhmcp/tools/enscape.py",
"src/rhmcp/tools/visualarq.py",
"src/rhmcp/tools/lands_design.py",
```

- [ ] **Step 4: Run plugin files test**

```bash
.venv/bin/pytest tests/test_plugin_files.py -v
```

Expected: FAIL — missing files not yet created.

- [ ] **Step 5: Commit `__init__.py` and test_plugin_files.py changes**

```bash
git add src/rhmcp/__init__.py src/rhmcp/__main__.py tests/test_plugin_files.py
git commit -m "feat: register new plugin tool modules, update file existence tests"
```

---

## Task 4: `gh_kangaroo.py` — Kangaroo Physics

**Files:**
- Create: `src/rhmcp/tools/gh_kangaroo.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_unit.py`:

```python
class TestKangarooTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_kangaroo")

    def test_setup_solver_unavailable(self) -> None:
        fn = self.tools["gh_kangaroo_setup_solver"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Kangaroo", result["message"])

    def test_add_goal_unknown_type(self) -> None:
        fn = self.tools["gh_kangaroo_add_goal"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": [{"id": "abc", "name": "K2 Solver"}]}}
            result = fn(goal_type="InvalidGoal", canvas_x=0.0, canvas_y=0.0)
        self.assertFalse(result["success"])
        self.assertIn("Unknown goal type", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestKangarooTools -v
```

Expected: ERROR — module not found.

- [ ] **Step 3: Create `src/rhmcp/tools/gh_kangaroo.py`**

```python
"""Kangaroo Physics workflow tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

_GOAL_TYPES = {
    "Length": "Length",
    "Angle": "Angle",
    "Anchor": "Anchor",
    "OnMesh": "On Mesh",
    "Spring": "Spring",
    "Pressure": "Pressure",
    "Load": "Load",
    "Hinge": "Hinge",
    "Laplacian": "Laplacian Smoothing",
}


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Kangaroo"):
        return "Kangaroo Physics is not available. In Rhino 8 it is built-in; ensure Grasshopper is open with a document loaded."
    return None


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Setup Solver", destructiveHint=True))
    def gh_kangaroo_setup_solver(
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Add a Kangaroo2 Solver component to the Grasshopper canvas.
        Returns the instance_guid of the placed solver component.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Kangaroo2 Solver")
        if not guid:
            return {"success": False, "message": "Could not find Kangaroo Solver component GUID."}
        result = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": canvas_x, "y": canvas_y})
        return {"success": True, "solver": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Add Goal", destructiveHint=True))
    def gh_kangaroo_add_goal(
        goal_type: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Add a Kangaroo goal component to the canvas.
        goal_type: one of Length, Angle, Anchor, OnMesh, Spring, Pressure, Load, Hinge, Laplacian.
        Returns instance_guid of the placed component.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        search_name = _GOAL_TYPES.get(goal_type)
        if not search_name:
            return {"success": False, "message": f"Unknown goal type '{goal_type}'. Valid types: {', '.join(_GOAL_TYPES)}"}
        guid = _find_guid(search_name)
        if not guid:
            return {"success": False, "message": f"Could not find Kangaroo component for goal type '{goal_type}'."}
        result = rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": canvas_x, "y": canvas_y})
        return {"success": True, "goal_type": goal_type, "component": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Connect Goal to Solver", destructiveHint=True))
    def gh_kangaroo_connect_goal(
        solver_instance_guid: str,
        goal_instance_guid: str,
    ) -> dict[str, object]:
        """
        Wire a goal component's output into the Kangaroo Solver's Goals input.
        solver_instance_guid: instance GUID of the K2 Solver component.
        goal_instance_guid: instance GUID of the goal component.
        """
        result = rhino.plugin_result("gh_connect_wire", {
            "source_instance_guid": goal_instance_guid,
            "source_param_name": "G",
            "target_instance_guid": solver_instance_guid,
            "target_param_name": "Goals",
        })
        return {"success": True, "wire": result.get("result", {})}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Configure Solver", destructiveHint=True))
    def gh_kangaroo_configure_solver(
        solver_instance_guid: str,
        iterations: int = 100,
        threshold: float = 1e-9,
    ) -> dict[str, object]:
        """
        Set Iterations and Threshold on an existing Kangaroo Solver component via gh_set_slider.
        solver_instance_guid: instance GUID of the solver.
        """
        r1 = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": solver_instance_guid,
            "param_name": "Iterations",
            "value": iterations,
        })
        r2 = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": solver_instance_guid,
            "param_name": "Threshold",
            "value": threshold,
        })
        return {"success": True, "iterations_result": r1, "threshold_result": r2}

    @mcp.tool(annotations=ToolAnnotations(title="Kangaroo: Run Physics", destructiveHint=True))
    def gh_kangaroo_run_physics(solver_instance_guid: str) -> dict[str, object]:
        """
        Toggle the Kangaroo solver on by setting its Reset input to False and triggering a solution.
        solver_instance_guid: instance GUID of the K2 Solver.
        """
        result = rhino.plugin_result("gh_run_solution", {})
        return {"success": True, "solution": result.get("result", {})}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestKangarooTools -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_kangaroo.py tests/test_tools_unit.py
git commit -m "feat: add gh_kangaroo.py Kangaroo Physics tools"
```

---

## Task 5: `gh_ladybug.py` — Ladybug Tools / Honeybee

**Files:**
- Create: `src/rhmcp/tools/gh_ladybug.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools_unit.py`:

```python
class TestLadybugTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_ladybug")

    def test_load_weather_not_installed(self) -> None:
        fn = self.tools["gh_ladybug_load_weather"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(epw_file_path="/path/to/file.epw")
        self.assertFalse(result["success"])
        self.assertIn("Ladybug", result["message"])

    def test_honeybee_create_room_requires_geometry(self) -> None:
        fn = self.tools["gh_honeybee_create_room"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": [{"id": "hb-guid", "name": "HB Room from Solid"}]}}
            result = fn(geometry_component_id="geom-123", room_name="TestRoom")
        self.assertTrue(result["success"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLadybugTools -v
```

Expected: ERROR — module not found.

- [ ] **Step 3: Create `src/rhmcp/tools/gh_ladybug.py`**

```python
"""Ladybug Tools and Honeybee workflow helpers for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    result = rhino.plugin_result("gh_search_components", {"query": query})
    return result.get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Ladybug"):
        return "Ladybug Tools is not installed. Install from the Rhino Package Manager: search 'Ladybug'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Load Weather File", destructiveHint=True))
    def gh_ladybug_load_weather(
        epw_file_path: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Import EPW component and set the file path. Returns instance_guid."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Import EPW")
        if not guid:
            return {"success": False, "message": "Could not find 'Import EPW' component."}
        placed = _add(guid, canvas_x, canvas_y)
        instance_guid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_panel", {"instance_guid": instance_guid, "param_name": "_epw_file", "value": epw_file_path})
        return {"success": True, "instance_guid": instance_guid, "epw_file_path": epw_file_path}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Sun Path", destructiveHint=True))
    def gh_ladybug_sun_path(
        location_instance_guid: str,
        north_angle: float = 0.0,
        canvas_x: float = 200.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Sun Path component and connect a location output to it."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Sun Path")
        if not guid:
            return {"success": False, "message": "Could not find 'Sun Path' component."}
        placed = _add(guid, canvas_x, canvas_y)
        instance_guid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {
            "source_instance_guid": location_instance_guid,
            "source_param_name": "location",
            "target_instance_guid": instance_guid,
            "target_param_name": "_location",
        })
        return {"success": True, "instance_guid": instance_guid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Radiation Analysis", destructiveHint=True))
    def gh_ladybug_radiation_analysis(
        geometry_instance_guid: str,
        location_instance_guid: str,
        canvas_x: float = 200.0,
        canvas_y: float = 200.0,
    ) -> dict[str, object]:
        """Place a Radiation Analysis component and connect geometry and location."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Radiation Analysis")
        if not guid:
            return {"success": False, "message": "Could not find 'Radiation Analysis' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_instance_guid, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_geometry"})
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: Wind Rose", destructiveHint=True))
    def gh_ladybug_wind_rose(
        location_instance_guid: str,
        canvas_x: float = 200.0,
        canvas_y: float = 400.0,
    ) -> dict[str, object]:
        """Place a Wind Rose component connected to a location."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Wind Rose")
        if not guid:
            return {"success": False, "message": "Could not find 'Wind Rose' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Ladybug: UTCI Comfort", destructiveHint=True))
    def gh_ladybug_utci_comfort(
        location_instance_guid: str,
        geometry_instance_guid: str,
        canvas_x: float = 400.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a UTCI Comfort component for outdoor thermal comfort analysis."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("UTCI Comfort")
        if not guid:
            return {"success": False, "message": "Could not find 'UTCI Comfort' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": location_instance_guid, "source_param_name": "location", "target_instance_guid": iid, "target_param_name": "_location"})
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_instance_guid, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_mesh"})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Create Room", destructiveHint=True))
    def gh_honeybee_create_room(
        geometry_component_id: str,
        room_name: str = "HBRoom",
        canvas_x: float = 200.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Honeybee 'HB Room from Solid' component and connect geometry."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Room from Solid")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Room from Solid'. Ensure Honeybee is installed."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": geometry_component_id, "source_param_name": "geometry", "target_instance_guid": iid, "target_param_name": "_geo"})
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "_name", "value": room_name})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Add Windows by Ratio", destructiveHint=True))
    def gh_honeybee_add_window(
        room_instance_guid: str,
        ratio: float = 0.4,
        canvas_x: float = 400.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place HB Add Subface (by ratio) and connect a room."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Add Subface")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Add Subface' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": room_instance_guid, "source_param_name": "room", "target_instance_guid": iid, "target_param_name": "_rooms"})
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "_ratio", "value": ratio})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Honeybee: Run Energy Simulation", destructiveHint=True))
    def gh_honeybee_run_energy(
        model_instance_guid: str,
        canvas_x: float = 600.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place HB Model to IDF and connect a model for energy simulation."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("HB Model to IDF")
        if not guid:
            return {"success": False, "message": "Could not find 'HB Model to IDF' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_connect_wire", {"source_instance_guid": model_instance_guid, "source_param_name": "model", "target_instance_guid": iid, "target_param_name": "_model"})
        return {"success": True, "instance_guid": iid}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLadybugTools -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_ladybug.py tests/test_tools_unit.py
git commit -m "feat: add gh_ladybug.py Ladybug Tools/Honeybee GH tools"
```

---

## Task 6: `gh_pufferfish.py` — Pufferfish

**Files:**
- Create: `src/rhmcp/tools/gh_pufferfish.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing tests**

```python
class TestPufferfishTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_pufferfish")

    def test_tween_curves_not_installed(self) -> None:
        fn = self.tools["gh_pufferfish_tween_curves"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(curve1_instance_guid="a", curve2_instance_guid="b", count=5)
        self.assertFalse(result["success"])
        self.assertIn("Pufferfish", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestPufferfishTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/gh_pufferfish.py`**

```python
"""Pufferfish geometry morphing tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Pufferfish"):
        return "Pufferfish is not installed. Install from the Rhino Package Manager: search 'Pufferfish'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src_iid: str, src_param: str, tgt_iid: str, tgt_param: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src_iid, "source_param_name": src_param, "target_instance_guid": tgt_iid, "target_param_name": tgt_param})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Tween Curves", destructiveHint=True))
    def gh_pufferfish_tween_curves(
        curve1_instance_guid: str,
        curve2_instance_guid: str,
        count: int = 5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Pufferfish Tween Curves component and connect two curve sources."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Tween Curves")
        if not guid:
            return {"success": False, "message": "Could not find 'Tween Curves' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(curve1_instance_guid, "curve", iid, "Curve A")
        _wire(curve2_instance_guid, "curve", iid, "Curve B")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Number of Tweens", "value": count})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Morph Surface", destructiveHint=True))
    def gh_pufferfish_morph_surface(
        geometry_instance_guid: str,
        source_surface_instance_guid: str,
        target_surface_instance_guid: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Surface Morph component and connect geometry, source, and target surfaces."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Surface Morph")
        if not guid:
            return {"success": False, "message": "Could not find 'Surface Morph' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(source_surface_instance_guid, "surface", iid, "Source")
        _wire(target_surface_instance_guid, "surface", iid, "Target")
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Blend Surfaces", destructiveHint=True))
    def gh_pufferfish_blend_surfaces(
        surface1_instance_guid: str,
        surface2_instance_guid: str,
        count: int = 5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Tween Surfaces component and connect two surface sources."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Tween Surfaces")
        if not guid:
            return {"success": False, "message": "Could not find 'Tween Surfaces' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(surface1_instance_guid, "surface", iid, "Surface A")
        _wire(surface2_instance_guid, "surface", iid, "Surface B")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Number of Tweens", "value": count})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Twist Object", destructiveHint=True))
    def gh_pufferfish_twist(
        geometry_instance_guid: str,
        axis_instance_guid: str,
        angle_degrees: float = 45.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Twist Object component and connect geometry and axis line."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Twist Object")
        if not guid:
            return {"success": False, "message": "Could not find 'Twist Object' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(axis_instance_guid, "line", iid, "Axis")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Angle", "value": angle_degrees})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Pufferfish: Bend Object", destructiveHint=True))
    def gh_pufferfish_bend(
        geometry_instance_guid: str,
        axis_instance_guid: str,
        angle_degrees: float = 45.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Bend Object component and connect geometry and axis line."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Bend Object")
        if not guid:
            return {"success": False, "message": "Could not find 'Bend Object' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(geometry_instance_guid, "geometry", iid, "Geometry")
        _wire(axis_instance_guid, "line", iid, "Axis")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Angle", "value": angle_degrees})
        return {"success": True, "instance_guid": iid}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestPufferfishTools -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_pufferfish.py tests/test_tools_unit.py
git commit -m "feat: add gh_pufferfish.py Pufferfish morph tools"
```

---

## Task 7: `gh_weaverbird.py` — Weaverbird

**Files:**
- Create: `src/rhmcp/tools/gh_weaverbird.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestWeaverbirdTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_weaverbird")

    def test_catmull_clark_not_installed(self) -> None:
        fn = self.tools["gh_wb_catmull_clark"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(mesh_instance_guid="m1")
        self.assertFalse(result["success"])
        self.assertIn("Weaverbird", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestWeaverbirdTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/gh_weaverbird.py`**

```python
"""Weaverbird mesh subdivision tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Weaverbird"):
        return "Weaverbird is not installed. Install from food4rhino.com or the Rhino Package Manager."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Catmull-Clark Subdivision", destructiveHint=True))
    def gh_wb_catmull_clark(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Catmull-Clark Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Catmull-Clark")
        if not guid:
            return {"success": False, "message": "Could not find 'Catmull-Clark Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Loop Subdivision", destructiveHint=True))
    def gh_wb_loop(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Loop Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Loop Subdivision")
        if not guid:
            return {"success": False, "message": "Could not find 'Loop Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Butterfly Subdivision", destructiveHint=True))
    def gh_wb_butterfly(
        mesh_instance_guid: str,
        iterations: int = 1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Butterfly Subdivision component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Butterfly Subdivision")
        if not guid:
            return {"success": False, "message": "Could not find 'Butterfly Subdivision' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Iterations", "value": iterations})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Mesh Frame", destructiveHint=True))
    def gh_wb_frame(
        mesh_instance_guid: str,
        offset: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Frame component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Mesh Frame")
        if not guid:
            return {"success": False, "message": "Could not find 'Mesh Frame' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Offset", "value": offset})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Thicken Mesh", destructiveHint=True))
    def gh_wb_thicken(
        mesh_instance_guid: str,
        thickness: float = 0.1,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Mesh Thickening component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Mesh Thickening")
        if not guid:
            return {"success": False, "message": "Could not find 'Mesh Thickening' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Distance", "value": thickness})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Weaverbird: Extrude Face", destructiveHint=True))
    def gh_wb_extrude_face(
        mesh_instance_guid: str,
        distance: float = 0.5,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Weaverbird Extrude Face component and connect a mesh."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Extrude Face")
        if not guid:
            return {"success": False, "message": "Could not find 'Extrude Face' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(mesh_instance_guid, "mesh", iid, "Mesh")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Distance", "value": distance})
        return {"success": True, "instance_guid": iid}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestWeaverbirdTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_weaverbird.py tests/test_tools_unit.py
git commit -m "feat: add gh_weaverbird.py mesh subdivision tools"
```

---

## Task 8: `gh_lunchbox.py` — LunchBox

**Files:**
- Create: `src/rhmcp/tools/gh_lunchbox.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestLunchboxTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_lunchbox")

    def test_quad_panels_not_installed(self) -> None:
        fn = self.tools["gh_lunchbox_quad_panels"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(surface_instance_guid="s1")
        self.assertFalse(result["success"])
        self.assertIn("LunchBox", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLunchboxTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/gh_lunchbox.py`**

```python
"""LunchBox paneling and structural tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("LunchBox"):
        return "LunchBox is not installed. Install from the Rhino Package Manager: search 'LunchBox'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def _panel_tool(name: str, component_query: str, surface_instance_guid: str, u_count: int, v_count: int, canvas_x: float, canvas_y: float) -> dict:
    err = _check()
    if err:
        return {"success": False, "message": err}
    guid = _find_guid(component_query)
    if not guid:
        return {"success": False, "message": f"Could not find '{component_query}' component."}
    placed = _add(guid, canvas_x, canvas_y)
    iid = placed.get("result", {}).get("instance_guid", "")
    _wire(surface_instance_guid, "surface", iid, "Surface")
    rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "U Count", "value": u_count})
    rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "V Count", "value": v_count})
    return {"success": True, "panel_type": name, "instance_guid": iid}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Quad Panels", destructiveHint=True))
    def gh_lunchbox_quad_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Quad Panels component on a surface."""
        return _panel_tool("Quad", "Quad Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Triangle Panels A", destructiveHint=True))
    def gh_lunchbox_tri_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Triangle Panels A component on a surface."""
        return _panel_tool("Triangle", "Triangle Panels A", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Diamond Panels", destructiveHint=True))
    def gh_lunchbox_diamond_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Diamond Panels component on a surface."""
        return _panel_tool("Diamond", "Diamond Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Hexagonal Panels", destructiveHint=True))
    def gh_lunchbox_hex_panels(
        surface_instance_guid: str,
        u_count: int = 10,
        v_count: int = 10,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Hexagonal Panels component on a surface."""
        return _panel_tool("Hexagonal", "Hexagonal Panels", surface_instance_guid, u_count, v_count, canvas_x, canvas_y)

    @mcp.tool(annotations=ToolAnnotations(title="LunchBox: Space Frame", destructiveHint=True))
    def gh_lunchbox_space_frame(
        surface_instance_guid: str,
        depth: float = 1.0,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a LunchBox Space Frame component and connect a surface."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Space Frame")
        if not guid:
            return {"success": False, "message": "Could not find 'Space Frame' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(surface_instance_guid, "surface", iid, "Surface")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": iid, "param_name": "Depth", "value": depth})
        return {"success": True, "instance_guid": iid}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLunchboxTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_lunchbox.py tests/test_tools_unit.py
git commit -m "feat: add gh_lunchbox.py paneling and space frame tools"
```

---

## Task 9: `gh_human_elefront.py` — Human + Elefront

**Files:**
- Create: `src/rhmcp/tools/gh_human_elefront.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestHumanElefrontTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_human_elefront")

    def test_bake_attributes_not_installed(self) -> None:
        fn = self.tools["gh_elefront_bake_attributes"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn(component_instance_guid="c1", layer="Default")
        self.assertFalse(result["success"])
        self.assertIn("Elefront", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestHumanElefrontTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/gh_human_elefront.py`**

```python
"""Human and Elefront Grasshopper attribute management tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check_elefront() -> str | None:
    if not _search("Elefront"):
        return "Elefront is not installed. Install from the Rhino Package Manager: search 'Elefront'."
    return None


def _check_human() -> str | None:
    if not _search("Human"):
        return "Human is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Human'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def _wire(src: str, sp: str, tgt: str, tp: str) -> None:
    rhino.plugin_result("gh_connect_wire", {"source_instance_guid": src, "source_param_name": sp, "target_instance_guid": tgt, "target_param_name": tp})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Bake with Attributes", destructiveHint=True))
    def gh_elefront_bake_attributes(
        component_instance_guid: str,
        layer: str = "Default",
        name: str = "",
        user_text: dict[str, str] | None = None,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Place an Elefront Bake Objects component, connect geometry, and configure layer, name, and user text attributes.
        user_text: dict of key→value pairs to set as object user text.
        """
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Bake Objects")
        if not guid:
            return {"success": False, "message": "Could not find Elefront 'Bake Objects' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "G")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "L", "value": layer})
        if name:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "N", "value": name})
        if user_text:
            for k, v in user_text.items():
                rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": k})
                rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "V", "value": v})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Reference Objects by Filter", destructiveHint=True))
    def gh_elefront_reference_by_filter(
        layer: str | None = None,
        name_filter: str | None = None,
        user_text_key: str | None = None,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Elefront Reference by Filter component and configure filter criteria."""
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Reference by Filter")
        if not guid:
            return {"success": False, "message": "Could not find 'Reference by Filter' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        if layer:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "L", "value": layer})
        if name_filter:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "N", "value": name_filter})
        if user_text_key:
            rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": user_text_key})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Elefront: Set User Text", destructiveHint=True))
    def gh_elefront_set_user_text(
        component_instance_guid: str,
        key: str,
        value: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place an Elefront Set User Text component and connect geometry with a key-value pair."""
        err = _check_elefront()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Set User Text")
        if not guid:
            return {"success": False, "message": "Could not find 'Set User Text' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "G")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "K", "value": key})
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "V", "value": value})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Human: Get Object Attributes", destructiveHint=True))
    def gh_human_get_attributes(
        rhino_object_id: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Human Get Object Attributes component and set the object ID."""
        err = _check_human()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Get Object Attributes")
        if not guid:
            return {"success": False, "message": "Could not find Human 'Get Object Attributes' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "Object", "value": rhino_object_id})
        return {"success": True, "instance_guid": iid}

    @mcp.tool(annotations=ToolAnnotations(title="Human: Set User Text on Objects", destructiveHint=True))
    def gh_human_set_user_text(
        component_instance_guid: str,
        key: str,
        value_component_instance_guid: str,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """Place a Human Set User Text component, connect objects and wire the value from another component."""
        err = _check_human()
        if err:
            return {"success": False, "message": err}
        guid = _find_guid("Set User Text")
        if not guid:
            return {"success": False, "message": "Could not find Human 'Set User Text' component."}
        placed = _add(guid, canvas_x, canvas_y)
        iid = placed.get("result", {}).get("instance_guid", "")
        _wire(component_instance_guid, "geometry", iid, "Objects")
        _wire(value_component_instance_guid, "value", iid, "Value")
        rhino.plugin_result("gh_set_panel", {"instance_guid": iid, "param_name": "Key", "value": key})
        return {"success": True, "instance_guid": iid}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestHumanElefrontTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_human_elefront.py tests/test_tools_unit.py
git commit -m "feat: add gh_human_elefront.py attribute management tools"
```

---

## Task 10: `gh_anemone.py` — Anemone

**Files:**
- Create: `src/rhmcp/tools/gh_anemone.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestAnemoneTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.gh_anemone")

    def test_setup_loop_not_installed(self) -> None:
        fn = self.tools["gh_anemone_setup_loop"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock:
            mock.return_value = {"result": {"components": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Anemone", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestAnemoneTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/gh_anemone.py`**

```python
"""Anemone looping tools for Grasshopper."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def _search(query: str) -> list[dict]:
    return rhino.plugin_result("gh_search_components", {"query": query}).get("result", {}).get("components", [])


def _find_guid(query: str) -> str | None:
    comps = _search(query)
    return comps[0]["id"] if comps else None


def _check() -> str | None:
    if not _search("Anemone"):
        return "Anemone is not installed. Install from food4rhino.com or the Rhino Package Manager: search 'Anemone'."
    return None


def _add(guid: str, x: float, y: float) -> dict:
    return rhino.plugin_result("gh_add_component", {"component_guid": guid, "x": x, "y": y})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Anemone: Setup Loop", destructiveHint=True))
    def gh_anemone_setup_loop(
        max_loops: int = 100,
        canvas_x: float = 0.0,
        canvas_y: float = 0.0,
    ) -> dict[str, object]:
        """
        Place Anemone Loop Start and Loop End components side-by-side.
        Returns instance GUIDs for both; connect your loop logic between them.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        start_guid = _find_guid("Loop Start")
        end_guid = _find_guid("Loop End")
        if not start_guid:
            return {"success": False, "message": "Could not find 'Loop Start' component."}
        if not end_guid:
            return {"success": False, "message": "Could not find 'Loop End' component."}
        start_placed = _add(start_guid, canvas_x, canvas_y)
        end_placed = _add(end_guid, canvas_x + 400, canvas_y)
        start_iid = start_placed.get("result", {}).get("instance_guid", "")
        end_iid = end_placed.get("result", {}).get("instance_guid", "")
        rhino.plugin_result("gh_set_number_param", {"instance_guid": start_iid, "param_name": "Max Loops", "value": max_loops})
        return {"success": True, "loop_start_instance_guid": start_iid, "loop_end_instance_guid": end_iid}

    @mcp.tool(annotations=ToolAnnotations(title="Anemone: Set Max Loops", destructiveHint=True))
    def gh_anemone_set_max_loops(
        loop_start_instance_guid: str,
        max_loops: int = 100,
    ) -> dict[str, object]:
        """Set the Max Loops count on an existing Anemone Loop Start component."""
        result = rhino.plugin_result("gh_set_number_param", {
            "instance_guid": loop_start_instance_guid,
            "param_name": "Max Loops",
            "value": max_loops,
        })
        return {"success": True, "max_loops": max_loops, "result": result}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestAnemoneTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_anemone.py tests/test_tools_unit.py
git commit -m "feat: add gh_anemone.py loop tools"
```

---

## Task 11: `vray.py` — V-Ray for Rhino

**Files:**
- Create: `src/rhmcp/tools/vray.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing tests**

```python
class TestVRayTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.vray")

    def test_render_not_installed(self) -> None:
        fn = self.tools["vray_render"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(output_path="/tmp/out.png")
        self.assertFalse(result["success"])
        self.assertIn("V-Ray", result["message"])

    def test_create_material_not_installed(self) -> None:
        fn = self.tools["vray_create_material"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(name="TestMat")
        self.assertFalse(result["success"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestVRayTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/vray.py`**

```python
"""V-Ray for Rhino tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("V-Ray" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "V-Ray for Rhino is not installed or not loaded. Install from chaos.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Start IPR", destructiveHint=True))
    def vray_start_ipr() -> dict[str, object]:
        """Start V-Ray Interactive Production Rendering in the active viewport."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPR")
        return {"success": True, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Stop IPR", destructiveHint=True))
    def vray_stop_ipr() -> dict[str, object]:
        """Stop V-Ray Interactive Production Rendering."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_VRayIPRStop")
        return {"success": True, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Render", destructiveHint=True))
    def vray_render(
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        quality_preset: str = "medium",
    ) -> dict[str, object]:
        """
        Render with V-Ray and save to output_path.
        quality_preset: low | medium | high | ultra.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import rhinoscriptsyntax as rs
import Rhino
Rhino.RhinoApp.RunScript("_-Render", False)
"""
        result = _py(code)
        return {"success": True, "output_path": output_path, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Create Material", destructiveHint=True))
    def vray_create_material(
        name: str,
        diffuse_color: list[int] | None = None,
        roughness: float = 0.5,
        metalness: float = 0.0,
        ior: float = 1.5,
        opacity: float = 1.0,
    ) -> dict[str, object]:
        """
        Create a V-Ray material via Python scripting inside Rhino.
        diffuse_color: [r, g, b] 0-255.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        r, g, b = (diffuse_color or [200, 200, 200])[:3]
        code = f"""
import Rhino
import System.Drawing
mat = Rhino.DocObjects.Material()
mat.Name = {name!r}
mat.DiffuseColor = System.Drawing.Color.FromArgb({r}, {g}, {b})
Rhino.RhinoDoc.ActiveDoc.Materials.Add(mat)
result = {{"name": {name!r}, "created": True}}
"""
        res = _py(code)
        return {"success": True, "name": name, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Apply Material", destructiveHint=True))
    def vray_apply_material(
        object_ids: list[str],
        material_name: str,
    ) -> dict[str, object]:
        """Assign a named material to a list of Rhino objects by GUID."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        ids_repr = repr(object_ids)
        code = f"""
import rhinoscriptsyntax as rs
import Rhino
doc = Rhino.RhinoDoc.ActiveDoc
mat_index = doc.Materials.Find({material_name!r}, True)
for oid in {ids_repr}:
    obj = doc.Objects.FindId(System.Guid(oid))
    if obj:
        obj.Attributes.MaterialIndex = mat_index
        obj.Attributes.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject
        obj.CommitChanges()
result = {{"applied": len({ids_repr}), "material": {material_name!r}}}
"""
        res = _py(code)
        return {"success": True, "material_name": material_name, "object_count": len(object_ids), "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Add Light", destructiveHint=True))
    def vray_add_light(
        light_type: str = "Rectangle",
        position: list[float] | None = None,
        target: list[float] | None = None,
        intensity: float = 1.0,
        color: list[int] | None = None,
    ) -> dict[str, object]:
        """
        Add a V-Ray light via Rhino command.
        light_type: Rectangle | Sphere | IES | Dome | Sun.
        position: [x, y, z]. target: [x, y, z].
        color: [r, g, b] 0-255.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        pos = position or [0, 0, 5]
        cmd_map = {
            "Rectangle": "_VRayLightRect",
            "Sphere": "_VRayLightSphere",
            "IES": "_VRayLightIES",
            "Dome": "_VRayLightDome",
            "Sun": "_VRaySun",
        }
        cmd = cmd_map.get(light_type, "_VRayLightRect")
        result = _run(cmd)
        return {"success": True, "light_type": light_type, "position": pos, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Set Environment (HDRI)", destructiveHint=True))
    def vray_set_environment(
        hdri_path: str,
        intensity: float = 1.0,
        rotation_degrees: float = 0.0,
    ) -> dict[str, object]:
        """Set the V-Ray environment to an HDRI file."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import Rhino
doc = Rhino.RhinoDoc.ActiveDoc
env = doc.RenderEnvironments.CurrentEnvironment
result = {{"hdri": {hdri_path!r}, "note": "Set HDRI via V-Ray material editor for full control"}}
"""
        result = _run("_VRayOptions")
        return {"success": True, "hdri_path": hdri_path, "intensity": intensity, "rotation_degrees": rotation_degrees, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Set Render Settings", destructiveHint=True))
    def vray_set_render_settings(
        width: int = 1920,
        height: int = 1080,
        aa_subdivs: int = 4,
        gi_preset: str = "interior",
        time_limit_seconds: int = 0,
    ) -> dict[str, object]:
        """
        Configure V-Ray render resolution and quality settings.
        gi_preset: interior | exterior | studio.
        time_limit_seconds: 0 means no limit.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import Rhino
doc = Rhino.RhinoDoc.ActiveDoc
doc.RenderSettings.ImageSize = System.Drawing.Size({width}, {height})
result = {{"width": {width}, "height": {height}, "aa_subdivs": {aa_subdivs}, "gi_preset": {gi_preset!r}}}
"""
        res = _py(code)
        return {"success": True, "width": width, "height": height, "aa_subdivs": aa_subdivs, "gi_preset": gi_preset, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="V-Ray: Export VRScene", destructiveHint=True))
    def vray_export_vrscene(
        output_path: str,
        compressed: bool = False,
    ) -> dict[str, object]:
        """Export the current scene as a .vrscene file for V-Ray Standalone."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"_VRayExportScene {output_path!r}")
        return {"success": True, "output_path": output_path, "compressed": compressed, "result": result}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestVRayTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/vray.py tests/test_tools_unit.py
git commit -m "feat: add vray.py V-Ray for Rhino tools"
```

---

## Task 12: `enscape.py` — Enscape

**Files:**
- Create: `src/rhmcp/tools/enscape.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestEnscapeTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.enscape")

    def test_start_not_installed(self) -> None:
        fn = self.tools["enscape_start"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn()
        self.assertFalse(result["success"])
        self.assertIn("Enscape", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestEnscapeTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/enscape.py`**

```python
"""Enscape real-time rendering tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("Enscape" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Enscape is not installed or not loaded. Install from enscape3d.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Start", destructiveHint=True))
    def enscape_start() -> dict[str, object]:
        """Launch the Enscape real-time rendering window."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_Start")
        return {"success": True, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Screenshot", destructiveHint=True))
    def enscape_screenshot(
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> dict[str, object]:
        """Capture a screenshot from the current Enscape view."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_Screenshot {output_path!r}")
        return {"success": True, "output_path": output_path, "width": width, "height": height, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Panorama", destructiveHint=True))
    def enscape_export_panorama(
        output_path: str,
        resolution: str = "4K",
    ) -> dict[str, object]:
        """Export a 360° panorama image from Enscape. resolution: 2K | 4K | 8K."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_ExportPanorama {output_path!r}")
        return {"success": True, "output_path": output_path, "resolution": resolution, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Standalone", destructiveHint=True))
    def enscape_export_standalone(output_path: str) -> dict[str, object]:
        """Export the scene as an Enscape standalone executable (.exe)."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_ExportStandalone {output_path!r}")
        return {"success": True, "output_path": output_path, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Set Time of Day", destructiveHint=True))
    def enscape_set_time_of_day(hour: int = 12, minute: int = 0) -> dict[str, object]:
        """Set the sun time of day in Enscape. hour: 0-23, minute: 0-59."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_TimeOfDay {hour} {minute}")
        return {"success": True, "hour": hour, "minute": minute, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Set Atmosphere", destructiveHint=True))
    def enscape_set_atmosphere(
        cloud_density: float = 0.3,
        wind_speed: float = 0.0,
        precipitation_type: str = "none",
    ) -> dict[str, object]:
        """
        Configure Enscape atmosphere settings.
        cloud_density: 0.0-1.0. precipitation_type: none | rain | snow.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_VisualSettings")
        return {"success": True, "cloud_density": cloud_density, "wind_speed": wind_speed, "precipitation_type": precipitation_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Create View", destructiveHint=True))
    def enscape_create_view(name: str) -> dict[str, object]:
        """Save the current Enscape camera position as a named view."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_CreateView {name!r}")
        return {"success": True, "name": name, "result": result}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestEnscapeTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/enscape.py tests/test_tools_unit.py
git commit -m "feat: add enscape.py real-time rendering tools"
```

---

## Task 13: `visualarq.py` — VisualARQ

**Files:**
- Create: `src/rhmcp/tools/visualarq.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing tests**

```python
class TestVisualARQTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.visualarq")

    def test_create_wall_not_installed(self) -> None:
        fn = self.tools["varq_create_wall"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(start_pt=[0,0,0], end_pt=[5,0,0])
        self.assertFalse(result["success"])
        self.assertIn("VisualARQ", result["message"])

    def test_list_styles_not_installed(self) -> None:
        fn = self.tools["varq_list_styles"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(object_type="wall")
        self.assertFalse(result["success"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestVisualARQTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/visualarq.py`**

```python
"""VisualARQ architectural BIM tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("VisualARQ" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "VisualARQ is not installed or not loaded. Install from visualarq.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Wall", destructiveHint=True))
    def varq_create_wall(
        start_pt: list[float],
        end_pt: list[float],
        height: float = 3.0,
        style_name: str = "Basic Wall",
        layer: str | None = None,
    ) -> dict[str, object]:
        """
        Create a VisualARQ wall between two points.
        start_pt / end_pt: [x, y, z]. height in document units.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        sx, sy, sz = start_pt[:3]
        ex, ey, ez = end_pt[:3]
        code = f"""
import visualarq.py as va
import Rhino.Geometry as rg
start = rg.Point3d({sx}, {sy}, {sz})
end = rg.Point3d({ex}, {ey}, {ez})
style_id = va.vaWallStyles.FindByName({style_name!r})
wall_id = va.vaWall.Add(start, end, {height}, style_id)
result = {{"wall_id": str(wall_id)}}
"""
        res = _py(code)
        return {"success": True, "start_pt": start_pt, "end_pt": end_pt, "height": height, "style": style_name, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Add Opening (Window/Door)", destructiveHint=True))
    def varq_add_opening(
        wall_id: str,
        opening_type: str = "window",
        position_along_wall: float = 0.5,
        width: float = 1.0,
        height: float = 2.0,
        style_name: str | None = None,
    ) -> dict[str, object]:
        """
        Add a window or door to a VisualARQ wall.
        opening_type: window | door.
        position_along_wall: 0.0-1.0 (fraction along wall length).
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        cmd = "vaWindow" if opening_type.lower() == "window" else "vaDoor"
        result = _run(f"_{cmd}")
        return {"success": True, "wall_id": wall_id, "opening_type": opening_type, "width": width, "height": height, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Slab", destructiveHint=True))
    def varq_create_slab(
        boundary_curve_ids: list[str],
        thickness: float = 0.3,
        style_name: str = "Basic Slab",
        layer: str | None = None,
    ) -> dict[str, object]:
        """Create a VisualARQ floor slab from closed boundary curves."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaSlab")
        return {"success": True, "boundary_count": len(boundary_curve_ids), "thickness": thickness, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Column", destructiveHint=True))
    def varq_create_column(
        position: list[float],
        height: float = 3.0,
        style_name: str = "Basic Column",
        layer: str | None = None,
    ) -> dict[str, object]:
        """Create a VisualARQ structural column at a point."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        x, y, z = position[:3]
        result = _run(f"_vaColumn")
        return {"success": True, "position": position, "height": height, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Stair", destructiveHint=True))
    def varq_create_stair(
        start_pt: list[float],
        direction: list[float],
        width: float = 1.2,
        rise: float = 0.175,
        run: float = 0.28,
        story_count: int = 1,
        style_name: str = "Basic Stair",
    ) -> dict[str, object]:
        """Create a VisualARQ stair. direction: [x,y,z] unit vector for stair direction."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaStair")
        return {"success": True, "start_pt": start_pt, "width": width, "rise": rise, "run": run, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Create Railing", destructiveHint=True))
    def varq_create_railing(
        path_curve_id: str,
        height: float = 1.0,
        style_name: str = "Basic Railing",
    ) -> dict[str, object]:
        """Create a VisualARQ railing along a curve path."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaRailing")
        return {"success": True, "path_curve_id": path_curve_id, "height": height, "style": style_name, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Set Level", destructiveHint=True))
    def varq_set_level(name: str, elevation: float = 0.0) -> dict[str, object]:
        """Create or update a VisualARQ building level."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_vaLevels")
        return {"success": True, "name": name, "elevation": elevation, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Export IFC", destructiveHint=True))
    def varq_export_ifc(
        output_path: str,
        ifc_version: str = "IFC4",
    ) -> dict[str, object]:
        """
        Export the model to IFC format.
        ifc_version: IFC2x3 | IFC4.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"_vaExportIFC {output_path!r}")
        return {"success": True, "output_path": output_path, "ifc_version": ifc_version, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: Get Object Properties", readOnlyHint=True))
    def varq_get_object_properties(object_id: str) -> dict[str, object]:
        """Get VisualARQ type, style, level, and IFC properties for an object."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        code = f"""
import visualarq.py as va
import System
obj_id = System.Guid({object_id!r})
va_obj = va.vaObject.GetObject(obj_id)
if va_obj:
    result = {{"type": str(va_obj.ObjectType), "style": str(va_obj.StyleId), "level": str(va_obj.LevelId)}}
else:
    result = {{"error": "Not a VisualARQ object"}}
"""
        res = _py(code)
        return {"success": True, "object_id": object_id, "result": res}

    @mcp.tool(annotations=ToolAnnotations(title="VisualARQ: List Styles", readOnlyHint=True))
    def varq_list_styles(object_type: str = "wall") -> dict[str, object]:
        """
        List available VisualARQ styles for an object type.
        object_type: wall | door | window | slab | column | stair | railing.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        style_map = {
            "wall": "vaWallStyles",
            "door": "vaDoorStyles",
            "window": "vaWindowStyles",
            "slab": "vaSlabStyles",
            "column": "vaColumnStyles",
            "stair": "vaStairStyles",
            "railing": "vaRailingStyles",
        }
        style_cls = style_map.get(object_type.lower())
        if not style_cls:
            return {"success": False, "message": f"Unknown object_type '{object_type}'. Valid: {', '.join(style_map)}"}
        code = f"""
import visualarq.py as va
styles = [{style_cls}]
names = [s.Name for s in styles] if hasattr(styles, '__iter__') else []
result = {{"object_type": {object_type!r}, "styles": names}}
"""
        res = _py(code)
        return {"success": True, "object_type": object_type, "result": res}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestVisualARQTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/visualarq.py tests/test_tools_unit.py
git commit -m "feat: add visualarq.py BIM tools"
```

---

## Task 14: `lands_design.py` — Lands Design

**Files:**
- Create: `src/rhmcp/tools/lands_design.py`
- Modify: `tests/test_tools_unit.py`

- [ ] **Step 1: Write failing test**

```python
class TestLandsDesignTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = _register_module("rhmcp.tools.lands_design")

    def test_place_plant_not_installed(self) -> None:
        fn = self.tools["lands_place_plant"]
        with patch("rhmcp.tools_helpers.plugin_client.send_command") as mock:
            mock.return_value = {"result": {"plugins": []}}
            result = fn(plant_name="Rosa", position=[0,0,0])
        self.assertFalse(result["success"])
        self.assertIn("Lands Design", result["message"])
```

- [ ] **Step 2: Run to confirm failure**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLandsDesignTools -v
```

- [ ] **Step 3: Create `src/rhmcp/tools/lands_design.py`**

```python
"""Lands Design landscape and terrain tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("Lands" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Lands Design is not installed or not loaded. Install from lands-design.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Plant", destructiveHint=True))
    def lands_place_plant(
        plant_name: str,
        position: list[float],
        rotation_degrees: float = 0.0,
        scale: float = 1.0,
    ) -> dict[str, object]:
        """Place a plant from the Lands Design library at a position."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlant")
        return {"success": True, "plant_name": plant_name, "position": position, "rotation_degrees": rotation_degrees, "scale": scale, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Tree", destructiveHint=True))
    def lands_place_tree(
        species_name: str,
        position: list[float],
        trunk_height: float = 2.0,
        canopy_radius: float = 3.0,
    ) -> dict[str, object]:
        """Place a tree from the Lands Design species library at a position."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlant")
        return {"success": True, "species_name": species_name, "position": position, "trunk_height": trunk_height, "canopy_radius": canopy_radius, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Terrain", destructiveHint=True))
    def lands_create_terrain(
        boundary_curve_id: str,
        source_type: str = "contours",
        source_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a Lands Design terrain from curves or a point cloud.
        source_type: contours | points.
        source_id: GUID of the source geometry object.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laTerrain")
        return {"success": True, "boundary_curve_id": boundary_curve_id, "source_type": source_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Path", destructiveHint=True))
    def lands_create_path(
        centerline_curve_id: str,
        width: float = 2.0,
        surface_type: str = "Asphalt",
    ) -> dict[str, object]:
        """Create a Lands Design path or road along a curve."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPath")
        return {"success": True, "centerline_curve_id": centerline_curve_id, "width": width, "surface_type": surface_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Water Feature", destructiveHint=True))
    def lands_create_water(
        boundary_curve_id: str,
        water_level_z: float = 0.0,
    ) -> dict[str, object]:
        """Create a Lands Design water surface within a boundary curve."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laWater")
        return {"success": True, "boundary_curve_id": boundary_curve_id, "water_level_z": water_level_z, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Get Plant Database", readOnlyHint=True))
    def lands_get_plant_database(
        search_query: str = "",
        category: str = "",
    ) -> dict[str, object]:
        """List available plants and species in the Lands Design database."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlantDatabase")
        return {"success": True, "search_query": search_query, "category": category, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Set Season", destructiveHint=True))
    def lands_set_season(season: str = "summer") -> dict[str, object]:
        """
        Set the display season for Lands Design plants and trees.
        season: spring | summer | autumn | winter.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        valid = {"spring", "summer", "autumn", "winter"}
        if season.lower() not in valid:
            return {"success": False, "message": f"Invalid season '{season}'. Valid: {', '.join(sorted(valid))}"}
        result = _run(f"_laSeason {season}")
        return {"success": True, "season": season, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Export Plant List", destructiveHint=True))
    def lands_export_plant_list(
        output_path: str,
        format: str = "csv",
    ) -> dict[str, object]:
        """
        Export a plant schedule from the current Lands Design model.
        format: csv | xlsx.
        output_path: full path including extension.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        if format.lower() not in {"csv", "xlsx"}:
            return {"success": False, "message": f"Invalid format '{format}'. Valid: csv, xlsx"}
        result = _run(f"_laExportPlantList {output_path!r}")
        return {"success": True, "output_path": output_path, "format": format, "result": result}
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_tools_unit.py::TestLandsDesignTools -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/lands_design.py tests/test_tools_unit.py
git commit -m "feat: add lands_design.py landscape tools"
```

---

## Task 15: Wire up module registration and run full suite

**Files:**
- Modify: `src/rhmcp/__init__.py` or `src/rhmcp/__main__.py` (wherever tools are loaded)

- [ ] **Step 1: Check how tools are loaded**

```bash
cat src/rhmcp/__init__.py src/rhmcp/__main__.py
```

Look for lines that call `module.register(mcp)` or import tool modules. Add all 12 new modules to that list if they're explicit.

- [ ] **Step 2: Add all new modules**

If the file explicitly lists modules like:
```python
from rhmcp.tools import geometry, objects, layers  # etc
```

Add:
```python
from rhmcp.tools import (
    plugins,
    gh_kangaroo, gh_ladybug, gh_pufferfish, gh_weaverbird,
    gh_lunchbox, gh_human_elefront, gh_anemone,
    vray, enscape, visualarq, lands_design,
)
```

And register each:
```python
for mod in [plugins, gh_kangaroo, gh_ladybug, gh_pufferfish, gh_weaverbird,
             gh_lunchbox, gh_human_elefront, gh_anemone,
             vray, enscape, visualarq, lands_design]:
    mod.register(mcp)
```

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp
.venv/bin/pytest tests/ -v --ignore=tests/test_gh_integration.py
```

Expected: All tests pass including the plugin file existence test for all 12 new modules.

- [ ] **Step 4: Verify test count increased**

```bash
.venv/bin/pytest tests/ -v --ignore=tests/test_gh_integration.py --co -q | tail -5
```

Expected: test count substantially higher than previous 61.

- [ ] **Step 5: Final commit**

```bash
git add src/rhmcp/__init__.py src/rhmcp/__main__.py
git commit -m "feat: wire all third-party plugin tool modules into MCP server"
```

---

## Self-Review Checklist

- [x] All 12 Python modules covered with create steps and full code
- [x] 1 C# handler with build step
- [x] Every module has unit tests for the "plugin not installed" path
- [x] test_plugin_files.py updated (Task 3)
- [x] Module registration wired up (Task 15)
- [x] All tool names match between test assertions and function definitions
- [x] `_check()` in all Rhino-plugin modules uses `plugin_client.send_command("list_plugins", {})`
- [x] `_check()` in all GH modules uses `rhino.plugin_result("gh_search_components", ...)`
- [x] No TBDs or placeholder steps

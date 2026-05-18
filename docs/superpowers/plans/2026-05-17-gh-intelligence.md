# GH Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GH canvas analysis, GH1/GH2 de-spaghettify, and GH1→GH2 migration tools to rhino_mcp (v0.12.0), matching and exceeding mcneel/RhinoMCP using direct tool execution instead of script generation.

**Architecture:** Three new C# handlers read GH1 canvas data; two new C# GH2 handlers write via reflection. A single Python topological-sort layout function shared by both GH1 and GH2 refactor tools. Four new Python tools in `gh_intelligence.py` orchestrate the workflows. GH1→GH2 type mapping lives in a versioned YAML file.

**Tech Stack:** C# (.NET 8, Grasshopper API, reflection for GH2), Python 3.10+, PyYAML (already in deps), pytest, FastMCP.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `rhino_plugin/RhinoMCPPlugin/GHIntelligenceHandlers.cs` | Create | 3 read-only C# handlers: canvas analysis, graph data, GH1 export |
| `rhino_plugin/RhinoMCPPlugin/GH2IntelligenceHandlers.cs` | Create | 2 GH2 write handlers: move component, add group (reflection-based) |
| `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs` | Modify | Wire 5 new handlers; add to read-only list |
| `rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj` | Modify | Version 0.11.0 → 0.12.0 |
| `src/rhmcp/tools/gh_intelligence.py` | Create | 4 Python tools + `_compute_layout` + `_clamp_positions` + `_load_gh1_to_gh2_map` + `_gh_intel` |
| `src/rhmcp/data/gh1_to_gh2_map.yml` | Create | Versioned GH1 type GUID → GH2 type name mapping |
| `tests/test_gh_intelligence.py` | Create | Unit tests (no live Rhino) |
| `tests/test_gh_intelligence_integration.py` | Create | Integration tests (live Rhino required) |
| `tests/fixtures/messy_canvas.gh` | Create | GH1 fixture with ≥8 crossings, ≥3 clusters |
| `tests/fixtures/simple_migration.gh` | Create | GH1 fixture, all components have GH2 equivalents |
| `tests/fixtures/messy_gh2_canvas.gh` | Create | GH2 fixture (Rhino 9 only) |
| `tests/test_smoke.py` | Modify | Update expected tool count to 353 |
| `pyproject.toml` | Modify | Version 0.11.0 → 0.12.0 |
| `CHANGELOG.md` | Modify | Add v0.12.0 entry |

---

## Task 1: C# — GHIntelligenceHandlers.cs (3 read-only handlers)

**Files:**
- Create: `rhino_plugin/RhinoMCPPlugin/GHIntelligenceHandlers.cs`

These three handlers are read-only introspection of the GH1 canvas. All run on UI thread via `RhinoApp.InvokeOnUiThread`. Follow the exact same pattern as `GHCanvasHandlers.cs`.

- [ ] **Step 1: Create the file**

```csharp
// rhino_plugin/RhinoMCPPlugin/GHIntelligenceHandlers.cs
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Rhino;

namespace RhinoMCPPlugin;

/// <summary>
/// Read-only GH1 canvas introspection handlers for canvas analysis,
/// graph data export, and migration data export.
/// All handlers run on the Rhino UI thread.
/// </summary>
public static class GHIntelligenceHandlers
{
    // -----------------------------------------------------------------------
    // gh_get_canvas_analysis
    // -----------------------------------------------------------------------

    public static object GetCanvasAnalysis(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetCanvasAnalysis did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var all  = doc.Objects.ToList();
                var comps  = all.Where(o => !(o is GH_Group)).ToList();
                var groups = all.OfType<GH_Group>().ToList();

                // Build adjacency (both directions for cluster detection)
                var fwd = new Dictionary<Guid, List<Guid>>();
                var rev = new Dictionary<Guid, List<Guid>>();
                foreach (var o in comps) { fwd[o.InstanceGuid] = new(); rev[o.InstanceGuid] = new(); }

                int connectionCount = 0;
                int crossingEstimate = 0;

                foreach (var obj in comps)
                {
                    if (obj is not IGH_Component comp) continue;
                    foreach (var op in comp.Params.Output)
                    {
                        foreach (var r in op.Recipients)
                        {
                            var toGuid = r.Attributes.GetTopLevel.DocObject.InstanceGuid;
                            if (!fwd.ContainsKey(toGuid)) continue;
                            fwd[obj.InstanceGuid].Add(toGuid);
                            rev[toGuid].Add(obj.InstanceGuid);
                            connectionCount++;
                            // Backward edge heuristic: right-to-left wires cross left-to-right wires
                            if (obj.Attributes.Pivot.X > r.Attributes.GetTopLevel.DocObject.Attributes.Pivot.X)
                                crossingEstimate++;
                        }
                    }
                }

                // BFS cluster detection (connected components)
                var visited  = new HashSet<Guid>();
                var clusters = new List<object>();
                foreach (var obj in comps)
                {
                    if (visited.Contains(obj.InstanceGuid)) continue;
                    var members = new List<string>();
                    var queue   = new Queue<Guid>();
                    queue.Enqueue(obj.InstanceGuid);
                    visited.Add(obj.InstanceGuid);
                    while (queue.Count > 0)
                    {
                        var cur = queue.Dequeue();
                        members.Add(cur.ToString());
                        foreach (var nb in fwd[cur].Concat(rev[cur]))
                        {
                            if (visited.Add(nb)) queue.Enqueue(nb);
                        }
                    }
                    clusters.Add(new { member_ids = members, label = $"Cluster {clusters.Count + 1}" });
                }

                // Grouped IDs
                var groupedIds = new HashSet<Guid>(groups.SelectMany(g => g.ObjectIDs));
                int ungrouped  = comps.Count(c => !groupedIds.Contains(c.InstanceGuid));
                int isolated   = comps.Count(c => !fwd[c.InstanceGuid].Any() && !rev[c.InstanceGuid].Any());

                // Canvas bounds
                var xs = comps.Select(c => (int)c.Attributes.Pivot.X).ToList();
                var ys = comps.Select(c => (int)c.Attributes.Pivot.Y).ToList();
                var bounds = xs.Count > 0
                    ? (object)new { x_min = xs.Min(), x_max = xs.Max(), y_min = ys.Min(), y_max = ys.Max() }
                    : new { x_min = 0, x_max = 0, y_min = 0, y_max = 0 };

                // Complexity score 0–100
                int score = Math.Min(100,
                    Math.Min(30, comps.Count) +
                    Math.Min(30, crossingEstimate * 3) +
                    Math.Min(20, comps.Count > 0 ? ungrouped * 20 / comps.Count : 0) +
                    Math.Min(20, isolated * 5));

                // Suggestions
                var suggestions = new List<string>();
                if (crossingEstimate >= 5)
                    suggestions.Add($"{crossingEstimate} estimated wire crossings — refactor recommended");
                if (ungrouped > 5)
                    suggestions.Add($"{ungrouped} components could be organised into {clusters.Count} logical groups");
                if (isolated > 0)
                    suggestions.Add($"{isolated} isolated components have no connections");

                result = new
                {
                    ok = true,
                    component_count          = comps.Count,
                    connection_count         = connectionCount,
                    wire_crossing_estimate   = crossingEstimate,
                    cluster_count            = clusters.Count,
                    clusters,
                    ungrouped_component_count = ungrouped,
                    isolated_component_count  = isolated,
                    complexity_score         = score,
                    canvas_bounds            = bounds,
                    suggestions
                };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // gh_get_graph_data — raw positions + adjacency for Python layout algorithm
    // -----------------------------------------------------------------------

    public static object GetGraphData(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetGraphData did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc   = GHDocumentHandlers.ActiveDoc();
                var comps = doc.Objects.Where(o => !(o is GH_Group)).ToList();

                var components = comps.Select(o => new
                {
                    id   = o.InstanceGuid.ToString(),
                    x    = (float)o.Attributes.Pivot.X,
                    y    = (float)o.Attributes.Pivot.Y,
                    name = o.NickName ?? ""
                }).ToList<object>();

                var connections = new List<object>();
                foreach (var obj in comps)
                {
                    if (obj is not IGH_Component comp) continue;
                    foreach (var op in comp.Params.Output)
                        foreach (var r in op.Recipients)
                            connections.Add(new
                            {
                                from_id = obj.InstanceGuid.ToString(),
                                to_id   = r.Attributes.GetTopLevel.DocObject.InstanceGuid.ToString()
                            });
                }

                result = new { ok = true, components, connections };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // gh1_export_migration_data — full component export for GH2 migration
    // -----------------------------------------------------------------------

    public static object ExportMigrationData(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "ExportMigrationData did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc      = GHDocumentHandlers.ActiveDoc();
                var exported = new List<object>();

                foreach (var obj in doc.Objects)
                {
                    if (obj is GH_Group) continue;

                    var inputs      = new List<object>();
                    var outputs     = new List<object>();
                    var values      = new Dictionary<string, object>();
                    var connections = new List<object>();

                    if (obj is IGH_Component comp)
                    {
                        foreach (var ip in comp.Params.Input)
                            inputs.Add(new { name = ip.NickName, type_name = ip.TypeName });
                        foreach (var op in comp.Params.Output)
                        {
                            outputs.Add(new { name = op.NickName, type_name = op.TypeName });
                            foreach (var r in op.Recipients)
                                connections.Add(new
                                {
                                    from_output = op.NickName,
                                    to_id       = r.Attributes.GetTopLevel.DocObject.InstanceGuid.ToString(),
                                    to_input    = r.NickName
                                });
                        }
                    }

                    // Capture slider state
                    if (obj is GH_NumberSlider sl)
                    {
                        values["value"]    = (double)sl.CurrentValue;
                        values["minimum"]  = (double)sl.Slider.Minimum;
                        values["maximum"]  = (double)sl.Slider.Maximum;
                        values["decimals"] = sl.Slider.DecimalPlaces;
                    }
                    // Capture panel text via reflection (GH_Panel is not in the public API)
                    else if (obj.GetType().Name == "GH_Panel")
                    {
                        var textProp = obj.GetType().GetProperty("UserText");
                        if (textProp != null)
                            values["text"] = textProp.GetValue(obj)?.ToString() ?? "";
                    }

                    exported.Add(new
                    {
                        instance_guid = obj.InstanceGuid.ToString(),
                        type_guid     = obj.ComponentGuid.ToString(),
                        nick_name     = obj.NickName ?? "",
                        type_name     = obj.GetType().Name,
                        x             = (float)obj.Attributes.Pivot.X,
                        y             = (float)obj.Attributes.Pivot.Y,
                        inputs,
                        outputs,
                        values,
                        connections
                    });
                }

                result = new { ok = true, components = exported, count = exported.Count };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }
}
```

- [ ] **Step 2: Verify file compiles (build check only)**

```bash
cd /path/to/rhino_mcp
dotnet build rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj -c Release 2>&1 | tail -5
```
Expected: `Build succeeded` (may warn about missing wiring — that is fixed in Task 3).

- [ ] **Step 3: Commit**

```bash
git add rhino_plugin/RhinoMCPPlugin/GHIntelligenceHandlers.cs
git commit -m "feat(plugin): add GHIntelligenceHandlers — canvas analysis, graph data, migration export"
```

---

## Task 2: C# — GH2IntelligenceHandlers.cs (gh2_move_component, gh2_add_group)

**Files:**
- Create: `rhino_plugin/RhinoMCPPlugin/GH2IntelligenceHandlers.cs`

Uses reflection like `GH2Handlers.cs` — no compile-time Grasshopper2.dll dependency.

- [ ] **Step 1: Create the file**

```csharp
// rhino_plugin/RhinoMCPPlugin/GH2IntelligenceHandlers.cs
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

/// <summary>
/// GH2 write handlers for canvas refactoring: move component and add group.
/// All GH2 types accessed via reflection — no compile-time Grasshopper2.dll dependency.
/// Returns GH2_NOT_AVAILABLE on Rhino 8 where GH2 is absent.
/// </summary>
public static class GH2IntelligenceHandlers
{
    private static Assembly? _gh2Asm;

    private static Assembly? GetGH2Assembly()
    {
        if (_gh2Asm != null) return _gh2Asm;
        _gh2Asm = AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name == "Grasshopper2");
        return _gh2Asm;
    }

    private static bool Gh2Available() => GetGH2Assembly() != null;

    private static object NotAvailable() => new
    {
        ok         = false,
        error      = "Grasshopper 2 is not available in this Rhino installation.",
        error_code = "GH2_NOT_AVAILABLE"
    };

    private static object? GetActiveGH2Doc()
    {
        var asm = GetGH2Assembly();
        if (asm == null) return null;
        foreach (var typeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.Instances" })
        {
            var t = asm.GetType(typeName);
            if (t == null) continue;
            foreach (var propName in new[] { "ActiveDocument", "ActiveDoc", "Document" })
            {
                var prop = t.GetProperty(propName, BindingFlags.Static | BindingFlags.Public);
                if (prop != null) return prop.GetValue(null);
            }
        }
        // Fallback via canvas
        foreach (var typeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.Instances" })
        {
            var t = asm.GetType(typeName);
            if (t == null) continue;
            var canvasProp = t.GetProperty("ActiveCanvas", BindingFlags.Static | BindingFlags.Public);
            var canvas = canvasProp?.GetValue(null);
            if (canvas == null) continue;
            var docProp = canvas.GetType().GetProperty("Document");
            if (docProp != null) return docProp.GetValue(canvas);
        }
        return null;
    }

    // -----------------------------------------------------------------------
    // gh2_move_component
    // -----------------------------------------------------------------------

    public static object MoveComponent(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        var guidStr = p.String("instance_guid");
        if (string.IsNullOrWhiteSpace(guidStr) || !Guid.TryParse(guidStr, out var guid))
            return new { ok = false, error = "instance_guid is required and must be a valid UUID" };

        var x = (float)p.Double("x", 0);
        var y = (float)p.Double("y", 0);

        object result = new { ok = false, error = "MoveComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null) { result = new { ok = false, error = "No active GH2 document" }; return; }

                // Enumerate objects to find target
                var objsProp = doc.GetType().GetProperty("Objects");
                if (objsProp?.GetValue(doc) is not System.Collections.IEnumerable objects)
                {
                    result = new { ok = false, error = "GH2 Objects not enumerable" };
                    return;
                }

                object? target = null;
                foreach (var obj in objects)
                {
                    var idProp = obj.GetType().GetProperty("Id")
                              ?? obj.GetType().GetProperty("InstanceGuid");
                    if (idProp?.GetValue(obj) is Guid objGuid && objGuid == guid)
                    {
                        target = obj;
                        break;
                    }
                }

                if (target == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found in GH2 canvas" };
                    return;
                }

                // Set pivot via Attributes.Pivot or direct Position property
                var attrProp  = target.GetType().GetProperty("Attributes");
                var attrs     = attrProp?.GetValue(target);
                var pivotProp = attrs?.GetType().GetProperty("Pivot");

                if (pivotProp != null)
                {
                    pivotProp.SetValue(attrs, new PointF(x, y));
                    result = new { ok = true };
                    return;
                }

                var posProp = target.GetType().GetProperty("Position");
                if (posProp != null)
                {
                    posProp.SetValue(target, new PointF(x, y));
                    result = new { ok = true };
                    return;
                }

                result = new { ok = false, error = "Could not find position property on GH2 component" };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // gh2_add_group
    // -----------------------------------------------------------------------

    public static object AddGroup(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        var asm = GetGH2Assembly()!;
        object result = new { ok = false, error = "AddGroup did not complete" };

        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null) { result = new { ok = false, error = "No active GH2 document" }; return; }

                var guids = p.StringList("instance_guids").Select(Guid.Parse).ToList();
                var label = p.String("label") ?? "";

                // Locate GH2 group type (name varies between builds)
                Type? groupType = null;
                foreach (var name in new[] { "Grasshopper2.GH_Group", "Grasshopper2.Components.GH_Group",
                                              "Grasshopper2.Special.GH_Group", "Grasshopper2.Kernel.GH_Group" })
                {
                    groupType = asm.GetType(name);
                    if (groupType != null) break;
                }

                if (groupType == null)
                {
                    result = new { ok = false, error = "GH2 Group type not found in this build" };
                    return;
                }

                var grp = Activator.CreateInstance(groupType);
                if (grp == null) { result = new { ok = false, error = "Could not instantiate GH2 Group" }; return; }

                // Set label
                (groupType.GetProperty("NickName") ?? groupType.GetProperty("Label"))
                    ?.SetValue(grp, label);

                // Add member GUIDs
                var addMeth = groupType.GetMethod("AddObject") ?? groupType.GetMethod("Add");
                if (addMeth != null)
                    foreach (var g in guids)
                        addMeth.Invoke(grp, new object[] { g });

                // Add group to document
                doc.GetType().GetMethod("AddObject")?.Invoke(doc, new object[] { grp, false });

                var groupId = (groupType.GetProperty("InstanceGuid") ?? groupType.GetProperty("Id"))
                    ?.GetValue(grp)?.ToString() ?? Guid.NewGuid().ToString();

                result = new { ok = true, group_id = groupId };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }
}
```

- [ ] **Step 2: Build check**

```bash
dotnet build rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj -c Release 2>&1 | tail -5
```
Expected: `Build succeeded`

- [ ] **Step 3: Commit**

```bash
git add rhino_plugin/RhinoMCPPlugin/GH2IntelligenceHandlers.cs
git commit -m "feat(plugin): add GH2IntelligenceHandlers — gh2_move_component, gh2_add_group (reflection)"
```

---

## Task 3: Wire C# handlers in CommandDispatcher + csproj + build + install

**Files:**
- Modify: `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs`
- Modify: `rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj`

- [ ] **Step 1: Add to read-only list in CommandDispatcher.cs**

In the `readOnly` variable declaration (around line 13), add these three entries after the existing GH2 read-only entries:

```csharp
            // GH Intelligence read-only
            "gh_get_canvas_analysis" or
            "gh_get_graph_data" or
            "gh1_export_migration_data";
```

The end of the existing `readOnly` block currently ends with:
```csharp
            "gh2_describe_component";
```
Change it to:
```csharp
            "gh2_describe_component" or
            // GH Intelligence read-only
            "gh_get_canvas_analysis" or
            "gh_get_graph_data" or
            "gh1_export_migration_data";
```

- [ ] **Step 2: Add dispatch cases in CommandDispatcher.cs**

After the existing GH2 entries in the switch (after `"gh2_clear_canvas"`), add:

```csharp
                // GH Intelligence — read-only
                "gh_get_canvas_analysis"    => McpResponse.Ok(GHIntelligenceHandlers.GetCanvasAnalysis(p)),
                "gh_get_graph_data"         => McpResponse.Ok(GHIntelligenceHandlers.GetGraphData(p)),
                "gh1_export_migration_data" => McpResponse.Ok(GHIntelligenceHandlers.ExportMigrationData(p)),
                // GH2 Intelligence — write
                "gh2_move_component"        => McpResponse.Ok(GH2IntelligenceHandlers.MoveComponent(p)),
                "gh2_add_group"             => McpResponse.Ok(GH2IntelligenceHandlers.AddGroup(p)),
```

- [ ] **Step 3: Bump version in RhinoMCPPlugin.csproj**

Change line 10:
```xml
    <Version>0.11.0</Version>
```
to:
```xml
    <Version>0.12.0</Version>
```

Also update the `ping` version string in `CommandDispatcher.cs` line 48:
```csharp
                "ping" => McpResponse.Ok(new { ok = true, version = "0.11.0", ...
```
to:
```csharp
                "ping" => McpResponse.Ok(new { ok = true, version = "0.12.0", ...
```

- [ ] **Step 4: Build the plugin**

```bash
./scripts/build-plugin.sh
```
Expected last lines:
```
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

- [ ] **Step 5: Reinstall plugin into Rhino**

Follow the upgrade steps (remove old, restart Rhino, copy new `.rhp`):
```bash
rm -f "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/rhino-mcp.rhp"
cp rhino_plugin/package/rhino-mcp.rhp \
   "$HOME/Library/Application Support/McNeel/Rhinoceros/8.0/Plug-ins/"
```
Restart Rhino, verify `Rhino MCP listening on 127.0.0.1:1999` appears.

- [ ] **Step 6: Commit**

```bash
git add rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs \
        rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj \
        rhino_plugin/package/rhino-mcp.rhp \
        rhino_plugin/package/rhino-mcp.deps.json
git commit -m "feat(plugin): wire GH intelligence handlers, bump plugin to 0.12.0"
```

---

## Task 4: gh1_to_gh2_map.yml

**Files:**
- Create: `src/rhmcp/data/gh1_to_gh2_map.yml`

- [ ] **Step 1: Create the mapping file**

```yaml
# GH1 component type GUID → GH2 type name mapping
# last_verified_rhino_version: keep up to date when testing against new Rhino 9 builds
last_verified_rhino_version: "9.0-wip"

mappings:
  # Math
  - gh1_guid: "57da07bd-ecab-415d-9d86-be1145e9f0eb"
    gh2_name: "Point"
  - gh1_guid: "f9a19ce4-3001-4fb2-a2be-b16d5f5de13d"
    gh2_name: "Number"
  - gh1_guid: "bc60a801-7d52-46bc-b3af-bd1a5d51c0e0"
    gh2_name: "Integer"
  - gh1_guid: "59e0b89a-e487-49f8-bab8-b5bab16be14c"
    gh2_name: "Panel"
  - gh1_guid: "57da07bd-ecab-415d-9d86-be1145e9f0f1"
    gh2_name: "NumberSlider"
  - gh1_guid: "e1de9900-1f29-4479-af45-8ad5b04f2c59"
    gh2_name: "Addition"
  - gh1_guid: "0f4dd8f2-ef33-4a69-a717-67ef07c7f1da"
    gh2_name: "Subtraction"
  - gh1_guid: "d69dc0fe-e234-4b5f-9fd7-2de1c1d9bd44"
    gh2_name: "Multiplication"
  - gh1_guid: "5f90d98d-ef25-49a2-9c90-0e9e09e8e79b"
    gh2_name: "Division"
  - gh1_guid: "87f87f55-92ef-4298-ba26-3d7dbde42ad8"
    gh2_name: "Circle"
  - gh1_guid: "80f3cd54-64c0-434c-b25a-40e7e27fe607"
    gh2_name: "Line"
  - gh1_guid: "213c1f14-0d62-4e23-a5b8-3f9fb8a1cf0e"
    gh2_name: "Vector"
  - gh1_guid: "61b95ac1-7186-4e7e-b376-4a5b5d90e3c5"
    gh2_name: "Move"
  - gh1_guid: "ff5f2e78-a78c-4a4c-bb56-e30a2b7b6291"
    gh2_name: "Rotate"
  - gh1_guid: "89b64e74-c8b3-4bd5-b688-c0bed73f92d2"
    gh2_name: "Scale"
  - gh1_guid: "dbc1258d-aaae-4490-9d18-fd7a1d1e8b7f"
    gh2_name: "BrepBox"
  - gh1_guid: "a138e3c6-97ac-43ab-a3c0-ee6bc51b27c3"
    gh2_name: "Sphere"
  - gh1_guid: "36884b96-de3a-4080-9600-7adada56da35"
    gh2_name: "Extrude"
  - gh1_guid: "bcc16c7b-c5ca-41f0-8975-b99dff4f1b42"
    gh2_name: "Loft"
  - gh1_guid: "7a30c92f-03b8-47bf-acf0-98f0ef57adef"
    gh2_name: "BooleanUnion"
```

> **Note:** These GUIDs are representative — verify against actual Grasshopper component GUIDs before shipping. Use `gh_search_components` to look up real GUIDs. Extend this file as GH2 component coverage grows.

- [ ] **Step 2: Commit**

```bash
git add src/rhmcp/data/gh1_to_gh2_map.yml
git commit -m "feat: add gh1_to_gh2_map.yml — initial GH1→GH2 type mapping"
```

---

## Task 5: Python — gh_intelligence.py skeleton + layout utility + gh_analyze_canvas

**Files:**
- Create: `src/rhmcp/tools/gh_intelligence.py`
- Create: `tests/test_gh_intelligence.py`

- [ ] **Step 1: Write failing tests for layout utility and gh_analyze_canvas**

```python
# tests/test_gh_intelligence.py
from __future__ import annotations

import importlib
import unittest
from unittest.mock import MagicMock, patch

from mcp.server.fastmcp import FastMCP


def _register() -> dict[str, object]:
    mod = importlib.import_module("rhmcp.tools.gh_intelligence")
    mcp = FastMCP("test-gh-intelligence")
    mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


_PLUGIN_OK_ANALYSIS = {
    "ok": True,
    "component_count": 10,
    "connection_count": 8,
    "wire_crossing_estimate": 5,
    "cluster_count": 2,
    "clusters": [
        {"member_ids": ["aaa", "bbb", "ccc"], "label": "Cluster 1"},
        {"member_ids": ["ddd", "eee"], "label": "Cluster 2"},
    ],
    "ungrouped_component_count": 8,
    "isolated_component_count": 1,
    "complexity_score": 45,
    "canvas_bounds": {"x_min": 0, "x_max": 1000, "y_min": 0, "y_max": 500},
    "suggestions": ["5 wire crossings detected"],
}

_PLUGIN_OK_GRAPH = {
    "ok": True,
    "components": [
        {"id": "aaa", "x": 0.0, "y": 0.0, "name": "Point"},
        {"id": "bbb", "x": 200.0, "y": 0.0, "name": "Circle"},
        {"id": "ccc", "x": 400.0, "y": 0.0, "name": "Extrude"},
    ],
    "connections": [
        {"from_id": "aaa", "to_id": "bbb"},
        {"from_id": "bbb", "to_id": "ccc"},
    ],
}


class TestLayoutUtility(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("rhmcp.tools.gh_intelligence")

    def test_compute_layout_linear_chain(self):
        """A→B→C should get layers 0, 1, 2 (left to right)."""
        components = [
            {"id": "a", "x": 100.0, "y": 50.0},
            {"id": "b", "x": 50.0, "y": 200.0},
            {"id": "c", "x": 300.0, "y": 100.0},
        ]
        connections = [{"from_id": "a", "to_id": "b"}, {"from_id": "b", "to_id": "c"}]
        layout = self.mod._compute_layout(components, connections)
        self.assertIn("a", layout)
        self.assertIn("b", layout)
        self.assertIn("c", layout)
        # a is source → lowest x; c is sink → highest x
        self.assertLess(layout["a"]["x"], layout["b"]["x"])
        self.assertLess(layout["b"]["x"], layout["c"]["x"])

    def test_compute_layout_isolated_node(self):
        """Isolated node (no edges) must still appear in output."""
        components = [{"id": "x", "x": 0.0, "y": 0.0}]
        layout = self.mod._compute_layout(components, [])
        self.assertIn("x", layout)

    def test_clamp_positions_within_bounds(self):
        layout = {"a": {"x": 200.0, "y": 100.0}}
        result = self.mod._clamp_positions(layout)
        self.assertEqual(result["a"]["x"], 200.0)

    def test_clamp_positions_exceeds_max(self):
        layout = {"a": {"x": 999_999.0, "y": -999_999.0}}
        result = self.mod._clamp_positions(layout)
        self.assertEqual(result["a"]["x"], 100_000.0)
        self.assertEqual(result["a"]["y"], -100_000.0)

    def test_load_gh1_to_gh2_map_returns_dict(self):
        mapping = self.mod._load_gh1_to_gh2_map()
        self.assertIsInstance(mapping, dict)

    def test_load_gh1_to_gh2_map_missing_file_returns_empty(self):
        with patch("rhmcp.tools.gh_intelligence._MAP_PATH", "/nonexistent/path.yml"):
            mapping = self.mod._load_gh1_to_gh2_map()
        self.assertEqual(mapping, {})


class TestGhAnalyzeCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def test_returns_ok_fields(self):
        """gh_analyze_canvas passes through the plugin response."""
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=_PLUGIN_OK_ANALYSIS):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertIn("complexity_score", result)
        self.assertIn("suggestions", result)

    def test_plugin_error_propagated(self):
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn()
        self.assertFalse(result["ok"])

    def test_oserror_returns_error(self):
        fn = self.tools["gh_analyze_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=OSError):
            result = fn()
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run pytest tests/test_gh_intelligence.py -v 2>&1 | tail -15
```
Expected: Multiple failures — `ModuleNotFoundError: rhmcp.tools.gh_intelligence`

- [ ] **Step 3: Create gh_intelligence.py with skeleton, layout utility, and gh_analyze_canvas**

```python
# src/rhmcp/tools/gh_intelligence.py
"""
GH Intelligence tools: canvas analysis, refactor (de-spaghettify), GH1→GH2 migration.
Requires the RhinoMCP plugin (all tools are plugin-only — no rhinocode fallback).
"""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_COORD = 100_000.0
_MAP_PATH = Path(__file__).parent.parent / "data" / "gh1_to_gh2_map.yml"
_GROUP_NAME_RE = re.compile(r'^[\w\s.\-]{1,64}$')
_LAYER_W = 200.0    # horizontal spacing between layers
_NODE_H  = 120.0    # vertical spacing within a layer

# ---------------------------------------------------------------------------
# Layout utility (shared by GH1 and GH2 refactor)
# ---------------------------------------------------------------------------

def _compute_layout(
    components: list[dict],
    connections: list[dict],
) -> dict[str, dict]:
    """
    Topological sort → layer assignment → {id: {x, y}} positions.

    components: list of {id, x, y, name}
    connections: list of {from_id, to_id}
    Returns dict of {id: {x: float, y: float}} with left-to-right data flow.
    Nodes in cycles or with no path keep their relative position at layer 0.
    """
    ids    = [c["id"] for c in components]
    id_set = set(ids)

    in_deg   = {id_: 0   for id_ in ids}
    children = {id_: []  for id_ in ids}

    for conn in connections:
        f = conn.get("from_id", "")
        t = conn.get("to_id", "")
        if f in id_set and t in id_set:
            children[f].append(t)
            in_deg[t] += 1

    # BFS to assign layers (longest-path to handle diamonds correctly)
    layer: dict[str, int] = {id_: 0 for id_ in ids if in_deg[id_] == 0}
    queue = deque(id_ for id_ in ids if in_deg[id_] == 0)
    in_deg_work = dict(in_deg)

    while queue:
        node = queue.popleft()
        for child in children[node]:
            in_deg_work[child] -= 1
            layer[child] = max(layer.get(child, 0), layer[node] + 1)
            if in_deg_work[child] == 0:
                queue.append(child)

    # Assign x/y by layer
    layer_rows: dict[int, int] = {}
    result: dict[str, dict] = {}
    for id_ in ids:
        lyr = layer.get(id_, 0)
        row = layer_rows.get(lyr, 0)
        result[id_] = {"x": float(lyr * _LAYER_W), "y": float(row * _NODE_H)}
        layer_rows[lyr] = row + 1

    return result


def _clamp_positions(layout: dict[str, dict]) -> dict[str, dict]:
    """Clamp all x/y values to ±_MAX_COORD."""
    return {
        id_: {
            "x": max(-_MAX_COORD, min(_MAX_COORD, pos["x"])),
            "y": max(-_MAX_COORD, min(_MAX_COORD, pos["y"])),
        }
        for id_, pos in layout.items()
    }

# ---------------------------------------------------------------------------
# GH1→GH2 type mapping
# ---------------------------------------------------------------------------

def _load_gh1_to_gh2_map() -> dict[str, str]:
    """Load gh1_to_gh2_map.yml. Returns empty dict on any error."""
    try:
        with open(_MAP_PATH) as f:
            data = yaml.safe_load(f)
        result: dict[str, str] = {}
        for entry in data.get("mappings", []):
            gh1 = entry.get("gh1_guid", "")
            gh2 = entry.get("gh2_name", "")
            if gh1 and gh2:
                result[gh1.lower()] = gh2
        return result
    except Exception:
        return {}


_GH1_TO_GH2_MAP: dict[str, str] = _load_gh1_to_gh2_map()

# ---------------------------------------------------------------------------
# Plugin dispatch helper
# ---------------------------------------------------------------------------

def _gh_intel(
    command: str,
    params: dict[str, object],
    rhino_id: str | None = None,
) -> dict[str, object]:
    """Plugin-only dispatch with optional rhino_id routing."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Analyze GH Canvas Complexity", readOnlyHint=True))
    def gh_analyze_canvas(rhino_id: str | None = None) -> dict[str, object]:
        """
        Analyze the active Grasshopper canvas and return complexity metrics.

        Returns component_count, connection_count, wire_crossing_estimate,
        cluster_count, ungrouped_component_count, isolated_component_count,
        complexity_score (0-100), canvas_bounds, and suggestions[].
        No side effects — safe to call at any time.
        """
        return _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)
```

- [ ] **Step 4: Run tests — expect layout/analyze tests to pass, refactor/migrate to fail**

```bash
uv run pytest tests/test_gh_intelligence.py -v 2>&1 | tail -20
```
Expected: Layout and analyze tests pass. Refactor/migrate tests will fail (not written yet).

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_intelligence.py tests/test_gh_intelligence.py
git commit -m "feat: gh_intelligence.py skeleton — layout utility + gh_analyze_canvas + unit tests"
```

---

## Task 6: Python — gh_refactor_canvas

**Files:**
- Modify: `src/rhmcp/tools/gh_intelligence.py`
- Modify: `tests/test_gh_intelligence.py`

- [ ] **Step 1: Add failing tests for gh_refactor_canvas**

Append to `tests/test_gh_intelligence.py`:

```python
class TestGhRefactorCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def _mock_plugin(self, command, params, rhino_id=None):
        if command == "gh_get_canvas_analysis":
            return _PLUGIN_OK_ANALYSIS
        if command == "gh_get_graph_data":
            return _PLUGIN_OK_GRAPH
        if command == "gh_move_component":
            return {"ok": True}
        if command == "gh_add_group":
            return {"ok": True, "group_id": "new-group-id"}
        return {"ok": False, "error": f"Unexpected command: {command}"}

    def test_preview_mode_makes_no_mutations(self):
        """apply=False must not call gh_move_component."""
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=self._mock_plugin) as mock_pr:
            result = fn(apply=False)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("preview"))
        # gh_move_component must never have been called
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
        self.assertEqual(len(move_calls), 0)

    def test_apply_mode_calls_move_for_each_component(self):
        """apply=True must call gh_move_component once per component."""
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=self._mock_plugin) as mock_pr:
            result = fn(apply=True)
        self.assertTrue(result.get("ok"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
        self.assertEqual(len(move_calls), len(_PLUGIN_OK_GRAPH["components"]))

    def test_dry_run_fails_on_out_of_bounds_position(self):
        """If layout produces out-of-bounds positions, abort before first move."""
        fn = self.tools["gh_refactor_canvas"]

        def bad_graph(command, params, rhino_id=None):
            if command == "gh_get_canvas_analysis":
                return _PLUGIN_OK_ANALYSIS
            if command == "gh_get_graph_data":
                return {"ok": True, "components": [{"id": "z", "x": 0.0, "y": 0.0, "name": "X"}], "connections": []}
            return {"ok": False, "error": "unexpected"}

        # Patch _compute_layout to return an out-of-bounds position
        mod = importlib.import_module("rhmcp.tools.gh_intelligence")
        original = mod._compute_layout
        mod._compute_layout = lambda comps, conns: {"z": {"x": 200_000.0, "y": 0.0}}
        try:
            with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=bad_graph) as mock_pr:
                result = fn(apply=True)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("error_code"), "LAYOUT_VALIDATION_FAILED")
            move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh_move_component"]
            self.assertEqual(len(move_calls), 0)
        finally:
            mod._compute_layout = original

    def test_analysis_error_propagated(self):
        fn = self.tools["gh_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn(apply=False)
        self.assertFalse(result["ok"])
```

- [ ] **Step 2: Run tests — expect new tests to fail**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGhRefactorCanvas -v 2>&1 | tail -10
```
Expected: `AttributeError` or `KeyError` — `gh_refactor_canvas` not registered yet.

- [ ] **Step 3: Implement gh_refactor_canvas in gh_intelligence.py**

Inside `register(mcp)`, after `gh_analyze_canvas`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Refactor GH1 Canvas Layout", destructiveHint=True))
    def gh_refactor_canvas(
        apply: bool = False,
        group_clusters: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reorganise the active GH1 canvas to reduce wire crossings and add logical groups.

        apply: False (default) returns the layout plan without touching the canvas.
               True executes all moves and group additions.
        group_clusters: Add GH groups per detected cluster when apply=True (default True).

        Returns {ok, preview, moves[], groups_to_add, estimated_crossings_after} when apply=False.
        Returns {ok, moved, groups_added, crossings_before, crossings_after} when apply=True.
        """
        analysis = _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)
        if not analysis.get("ok"):
            return analysis

        graph = _gh_intel("gh_get_graph_data", {}, rhino_id=rhino_id)
        if not graph.get("ok"):
            return graph

        components        = graph.get("components", [])
        connections       = graph.get("connections", [])
        clusters          = analysis.get("clusters", [])
        crossings_before  = int(analysis.get("wire_crossing_estimate", 0))

        # Compute layout via shared Python algorithm
        raw_layout = _compute_layout(components, connections)
        layout     = _clamp_positions(raw_layout)

        # Dry-run: validate all positions are within bounds
        invalid = [id_ for id_, pos in layout.items()
                   if abs(pos["x"]) > _MAX_COORD or abs(pos["y"]) > _MAX_COORD]
        if invalid:
            return {
                "ok":         False,
                "error":      "Layout validation failed — positions out of bounds",
                "error_code": "LAYOUT_VALIDATION_FAILED",
                "invalid_ids": invalid,
            }

        # Build moves list (include from position for preview)
        pos_by_id = {c["id"]: {"x": c["x"], "y": c["y"]} for c in components}
        moves = [
            {"component_id": id_, "from": pos_by_id.get(id_, {}), "to": pos}
            for id_, pos in layout.items()
        ]

        if not apply:
            return {
                "ok":                       True,
                "preview":                  True,
                "moves":                    moves,
                "groups_to_add":            len(clusters) if group_clusters else 0,
                "estimated_crossings_after": max(0, crossings_before - len(moves) // 4),
            }

        # Apply moves
        moved  = 0
        failed = []
        for id_, pos in layout.items():
            r = _gh_intel("gh_move_component",
                          {"instance_guid": id_, "x": pos["x"], "y": pos["y"]},
                          rhino_id=rhino_id)
            if r.get("ok"):
                moved += 1
            else:
                failed.append({"id": id_, "error": r.get("error", "")})

        if failed:
            return {"ok": False, "moved": moved, "failed": failed}

        # Add groups per cluster
        groups_added = 0
        if group_clusters:
            for cluster in clusters:
                member_ids = cluster.get("member_ids", [])
                if len(member_ids) >= 2:
                    r = _gh_intel(
                        "gh_add_group",
                        {"instance_guids": member_ids, "label": cluster.get("label", "")},
                        rhino_id=rhino_id,
                    )
                    if r.get("ok"):
                        groups_added += 1

        # Re-read crossings after
        after = _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)
        crossings_after = int(after.get("wire_crossing_estimate", 0)) if after.get("ok") else 0

        return {
            "ok":              True,
            "moved":           moved,
            "groups_added":    groups_added,
            "crossings_before": crossings_before,
            "crossings_after": crossings_after,
        }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGhRefactorCanvas -v 2>&1 | tail -10
```
Expected: All 4 tests pass.

- [ ] **Step 5: Run all gh_intelligence tests**

```bash
uv run pytest tests/test_gh_intelligence.py -v 2>&1 | tail -10
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/rhmcp/tools/gh_intelligence.py tests/test_gh_intelligence.py
git commit -m "feat: gh_refactor_canvas — GH1 de-spaghettify with preview mode + unit tests"
```

---

## Task 7: Python — gh2_refactor_canvas

**Files:**
- Modify: `src/rhmcp/tools/gh_intelligence.py`
- Modify: `tests/test_gh_intelligence.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_gh_intelligence.py`:

```python
class TestGh2RefactorCanvas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    _GH2_GRAPH = {
        "ok": True,
        "components": [
            {"id": "g1", "x": 0.0,   "y": 0.0,   "instance_guid": "g1"},
            {"id": "g2", "x": 100.0, "y": 200.0,  "instance_guid": "g2"},
        ],
        "connections": [{"from_id": "g1", "to_id": "g2"}],
        "groups": [],
    }

    def _mock_gh2_plugin(self, command, params, rhino_id=None):
        if command == "gh2_get_canvas_graph":
            return self._GH2_GRAPH
        if command == "gh2_move_component":
            return {"ok": True}
        if command == "gh2_add_group":
            return {"ok": True, "group_id": "gh2-grp"}
        if command == "gh_get_canvas_analysis":
            return {**_PLUGIN_OK_ANALYSIS, "clusters": [{"member_ids": ["g1", "g2"], "label": "C1"}]}
        return {"ok": False, "error": f"Unexpected: {command}"}

    def test_gh2_not_available_returns_error(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH2 not available", "error_code": "GH2_NOT_AVAILABLE"}):
            result = fn(apply=False)
        self.assertFalse(result["ok"])

    def test_preview_makes_no_mutations(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   side_effect=self._mock_gh2_plugin) as mock_pr:
            result = fn(apply=False)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("preview"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh2_move_component"]
        self.assertEqual(len(move_calls), 0)

    def test_apply_calls_gh2_move(self):
        fn = self.tools["gh2_refactor_canvas"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   side_effect=self._mock_gh2_plugin) as mock_pr:
            result = fn(apply=True)
        self.assertTrue(result.get("ok"))
        move_calls = [c for c in mock_pr.call_args_list if c.args[0] == "gh2_move_component"]
        self.assertEqual(len(move_calls), len(self._GH2_GRAPH["components"]))
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGh2RefactorCanvas -v 2>&1 | tail -10
```
Expected: `KeyError` — tool not registered yet.

- [ ] **Step 3: Implement gh2_refactor_canvas in gh_intelligence.py**

Inside `register(mcp)`, after `gh_refactor_canvas`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Refactor GH2 Canvas Layout", destructiveHint=True))
    def gh2_refactor_canvas(
        apply: bool = False,
        group_clusters: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reorganise the active GH2 canvas to reduce wire crossings and add logical groups.
        Requires Rhino 9 — returns GH2_NOT_AVAILABLE on Rhino 8.

        apply: False (default) returns layout plan; True executes all moves + groups.
        group_clusters: Add GH2 groups per detected cluster when apply=True.
        """
        # Read GH2 canvas (GH2 graph already exposes positions + connections)
        graph = _gh_intel("gh2_get_canvas_graph", {"sample_size": 0}, rhino_id=rhino_id)
        if not graph.get("ok"):
            return graph

        # Normalise GH2 graph data to same shape as GH1 graph data
        raw_comps = graph.get("components", [])
        components = [
            {
                "id": c.get("instance_guid") or c.get("id", ""),
                "x":  float(c.get("x", 0)),
                "y":  float(c.get("y", 0)),
                "name": c.get("name", ""),
            }
            for c in raw_comps
        ]
        raw_conns = graph.get("connections", graph.get("wires", []))
        connections = [
            {
                "from_id": w.get("from_instance") or w.get("from_id", ""),
                "to_id":   w.get("to_instance")   or w.get("to_id", ""),
            }
            for w in raw_conns
        ]

        # Get cluster data from GH1 analysis handler (works on GH1 canvas)
        # For GH2 clusters, compute from connections
        id_set = {c["id"] for c in components}
        adj: dict[str, list] = {c["id"]: [] for c in components}
        rev: dict[str, list] = {c["id"]: [] for c in components}
        for conn in connections:
            f, t = conn["from_id"], conn["to_id"]
            if f in id_set and t in id_set:
                adj[f].append(t)
                rev[t].append(f)

        visited: set[str] = set()
        clusters = []
        for comp in components:
            cid = comp["id"]
            if cid in visited:
                continue
            members = []
            queue = deque([cid])
            visited.add(cid)
            while queue:
                node = queue.popleft()
                members.append(node)
                for nb in adj[node] + rev[node]:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            clusters.append({"member_ids": members, "label": f"Cluster {len(clusters) + 1}"})

        crossings_before = sum(
            1 for conn in connections
            if conn["from_id"] in id_set and conn["to_id"] in id_set
            and next((c["x"] for c in components if c["id"] == conn["from_id"]), 0)
            > next((c["x"] for c in components if c["id"] == conn["to_id"]),   0)
        )

        layout = _clamp_positions(_compute_layout(components, connections))

        invalid = [id_ for id_, pos in layout.items()
                   if abs(pos["x"]) > _MAX_COORD or abs(pos["y"]) > _MAX_COORD]
        if invalid:
            return {
                "ok": False, "error": "Layout validation failed",
                "error_code": "LAYOUT_VALIDATION_FAILED", "invalid_ids": invalid,
            }

        pos_by_id = {c["id"]: {"x": c["x"], "y": c["y"]} for c in components}
        moves = [{"component_id": id_, "from": pos_by_id.get(id_, {}), "to": pos}
                 for id_, pos in layout.items()]

        if not apply:
            return {
                "ok":                       True,
                "preview":                  True,
                "moves":                    moves,
                "groups_to_add":            len(clusters) if group_clusters else 0,
                "estimated_crossings_after": max(0, crossings_before - len(moves) // 4),
            }

        moved = 0
        failed = []
        for id_, pos in layout.items():
            r = _gh_intel("gh2_move_component",
                          {"instance_guid": id_, "x": pos["x"], "y": pos["y"]},
                          rhino_id=rhino_id)
            if r.get("ok"):
                moved += 1
            else:
                failed.append({"id": id_, "error": r.get("error", "")})

        if failed:
            return {"ok": False, "moved": moved, "failed": failed}

        groups_added = 0
        if group_clusters:
            for cluster in clusters:
                members = cluster.get("member_ids", [])
                if len(members) >= 2:
                    r = _gh_intel("gh2_add_group",
                                  {"instance_guids": members, "label": cluster.get("label", "")},
                                  rhino_id=rhino_id)
                    if r.get("ok"):
                        groups_added += 1

        after = _gh_intel("gh2_get_canvas_graph", {"sample_size": 0}, rhino_id=rhino_id)
        crossings_after = 0
        if after.get("ok"):
            after_comps = {c.get("instance_guid", c.get("id", "")): c
                           for c in after.get("components", [])}
            after_wires = after.get("connections", after.get("wires", []))
            crossings_after = sum(
                1 for w in after_wires
                if (after_comps.get(w.get("from_instance", w.get("from_id", "")), {}).get("x", 0))
                > (after_comps.get(w.get("to_instance",   w.get("to_id",   "")), {}).get("x", 0))
            )

        return {
            "ok":               True,
            "moved":            moved,
            "groups_added":     groups_added,
            "crossings_before": crossings_before,
            "crossings_after":  crossings_after,
        }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGh2RefactorCanvas -v 2>&1 | tail -10
```
Expected: All 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/gh_intelligence.py tests/test_gh_intelligence.py
git commit -m "feat: gh2_refactor_canvas — GH2 de-spaghettify with preview mode + unit tests"
```

---

## Task 8: Python — gh_migrate_to_gh2

**Files:**
- Modify: `src/rhmcp/tools/gh_intelligence.py`
- Modify: `tests/test_gh_intelligence.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_gh_intelligence.py`:

```python
_EXPORT_DATA = {
    "ok": True,
    "count": 3,
    "components": [
        {
            "instance_guid": "comp-1",
            "type_guid": "57da07bd-ecab-415d-9d86-be1145e9f0eb",
            "nick_name": "Pt",
            "type_name": "GH_Point",
            "x": 0.0, "y": 0.0,
            "inputs": [], "outputs": [{"name": "Pt", "type_name": "Point3d"}],
            "values": {},
            "connections": [{"from_output": "Pt", "to_id": "comp-2", "to_input": "C"}],
        },
        {
            "instance_guid": "comp-2",
            "type_guid": "87f87f55-92ef-4298-ba26-3d7dbde42ad8",
            "nick_name": "Circle",
            "type_name": "GH_Circle",
            "x": 200.0, "y": 0.0,
            "inputs": [{"name": "C", "type_name": "Point3d"}, {"name": "R", "type_name": "Number"}],
            "outputs": [{"name": "C", "type_name": "Circle"}],
            "values": {},
            "connections": [],
        },
        {
            "instance_guid": "comp-3",
            "type_guid": "unknown-guid-not-in-map",
            "nick_name": "LegacyComp",
            "type_name": "GH_SomeLegacyThing",
            "x": 400.0, "y": 0.0,
            "inputs": [], "outputs": [],
            "values": {},
            "connections": [],
        },
    ],
}


class TestGhMigrateToGh2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = _register()

    def test_confirm_false_returns_confirmation_required(self):
        fn = self.tools["gh_migrate_to_gh2"]
        result = fn(confirm=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result.get("error_code"), "CONFIRMATION_REQUIRED")

    def test_confirm_false_never_calls_plugin(self):
        fn = self.tools["gh_migrate_to_gh2"]
        with patch("rhmcp.tools_helpers.backend.plugin_result") as mock_pr:
            fn(confirm=False)
        mock_pr.assert_not_called()

    def test_unmapped_component_in_unmapped_list(self):
        """Components with no GH2 mapping must appear in unmapped, not crash."""
        fn = self.tools["gh_migrate_to_gh2"]

        def mock_plugin(command, params, rhino_id=None):
            if command == "gh1_export_migration_data":
                return _EXPORT_DATA
            if command in ("gh2_start", "gh2_apply_graph"):
                return {"ok": True, "placed": {}, "wired": 0, "errors": []}
            return {"ok": False, "error": f"unexpected: {command}"}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin):
            result = fn(confirm=True)

        self.assertTrue(result.get("ok"))
        self.assertIsInstance(result.get("unmapped"), list)
        unmapped_guids = [u["gh1_guid"] for u in result["unmapped"]]
        self.assertIn("unknown-guid-not-in-map", unmapped_guids)

    def test_export_error_propagated(self):
        fn = self.tools["gh_migrate_to_gh2"]
        with patch("rhmcp.tools_helpers.backend.plugin_result",
                   return_value={"ok": False, "error": "GH not open"}):
            result = fn(confirm=True)
        self.assertFalse(result["ok"])

    def test_unmapped_always_present(self):
        """unmapped key must exist even when all components mapped."""
        fn = self.tools["gh_migrate_to_gh2"]
        export_all_mapped = {
            "ok": True, "count": 1,
            "components": [{
                "instance_guid": "c1",
                "type_guid": "57da07bd-ecab-415d-9d86-be1145e9f0eb",
                "nick_name": "Pt", "type_name": "GH_Point",
                "x": 0.0, "y": 0.0,
                "inputs": [], "outputs": [], "values": {}, "connections": [],
            }],
        }
        def mock_plugin(command, params, rhino_id=None):
            if command == "gh1_export_migration_data":
                return export_all_mapped
            return {"ok": True, "placed": {}, "wired": 0, "errors": []}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=mock_plugin):
            result = fn(confirm=True)

        self.assertIn("unmapped", result)
        self.assertIsInstance(result["unmapped"], list)
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGhMigrateToGh2 -v 2>&1 | tail -10
```
Expected: Failures — tool not registered.

- [ ] **Step 3: Implement gh_migrate_to_gh2 in gh_intelligence.py**

Inside `register(mcp)`, after `gh2_refactor_canvas`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Migrate GH1 Definition to GH2", destructiveHint=True))
    def gh_migrate_to_gh2(
        confirm: bool = False,
        close_gh1: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Migrate the active GH1 definition to a new GH2 canvas.
        Requires Rhino 9 — GH2 is not available in stable Rhino 8.

        confirm: Must be True to execute (safety guard against accidental migration).
        close_gh1: If True, close the GH1 definition after migration (default False —
                   leaves both open for side-by-side comparison).

        Returns {ok, migrated, unmapped[], gh2_errors[], gh1_closed}.
        unmapped[] always present (empty list if all components have GH2 equivalents).
        Components with no GH2 mapping are reported and skipped — migration continues.
        """
        if not confirm:
            return {
                "ok":         False,
                "error":      "Set confirm=True to execute the migration.",
                "error_code": "CONFIRMATION_REQUIRED",
            }

        # Step 1: export GH1 data
        export = _gh_intel("gh1_export_migration_data", {}, rhino_id=rhino_id)
        if not export.get("ok"):
            return export

        components = export.get("components", [])

        # Step 2: map types via YAML
        mapped   = []
        unmapped = []
        for comp in components:
            type_guid = comp.get("type_guid", "").lower()
            gh2_name  = _GH1_TO_GH2_MAP.get(type_guid)
            if gh2_name:
                mapped.append({
                    "key":        comp["instance_guid"],
                    "type_name":  gh2_name,
                    "x":          comp.get("x", 0.0),
                    "y":          comp.get("y", 0.0),
                })
            else:
                unmapped.append({
                    "gh1_guid":  comp.get("type_guid", ""),
                    "nickname":  comp.get("nick_name", ""),
                    "reason":    "No GH2 equivalent in mapping table",
                })

        # Build wires for mapped components only
        mapped_keys = {c["key"] for c in mapped}
        # instance_guid → key (same value here)
        guid_to_key  = {comp["instance_guid"]: comp["instance_guid"] for comp in components}

        wires = []
        for comp in components:
            if comp["instance_guid"] not in mapped_keys:
                continue
            for conn in comp.get("connections", []):
                to_key = guid_to_key.get(conn.get("to_id", ""), "")
                if to_key in mapped_keys:
                    wires.append({
                        "from_key":    comp["instance_guid"],
                        "from_output": conn.get("from_output", "0"),
                        "to_key":      to_key,
                        "to_input":    conn.get("to_input", "0"),
                    })

        # Step 3: ensure GH2 is open
        start = _gh_intel("gh2_start", {}, rhino_id=rhino_id)
        if not start.get("ok"):
            return start

        # Step 4: apply graph
        apply_result = _gh_intel(
            "gh2_apply_graph",
            {"components": mapped, "wires": wires},
            rhino_id=rhino_id,
        )
        gh2_errors = apply_result.get("errors", []) if apply_result.get("ok") else [apply_result.get("error", "")]

        # Step 5: optionally close GH1
        gh1_closed = False
        if close_gh1:
            close_result = _gh_intel("gh_close_document", {}, rhino_id=rhino_id)
            gh1_closed = close_result.get("ok", False)

        return {
            "ok":        True,
            "migrated":  len(mapped),
            "unmapped":  unmapped,
            "gh2_errors": gh2_errors,
            "gh1_closed": gh1_closed,
        }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_gh_intelligence.py::TestGhMigrateToGh2 -v 2>&1 | tail -10
```
Expected: All 5 tests pass.

- [ ] **Step 5: Run all gh_intelligence tests**

```bash
uv run pytest tests/test_gh_intelligence.py -v 2>&1 | tail -15
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/rhmcp/tools/gh_intelligence.py tests/test_gh_intelligence.py
git commit -m "feat: gh_migrate_to_gh2 — GH1→GH2 migration with YAML mapping + unit tests"
```

---

## Task 9: Smoke test update

**Files:**
- Modify: `tests/test_smoke.py`

- [ ] **Step 1: Find and update the tool count assertion**

```bash
grep -n "353\|351\|347\|tool.*count\|total.*tool\|>= [0-9]" tests/test_smoke.py | head -10
```

- [ ] **Step 2: Update the count**

Find the line that asserts minimum tool count (currently `>= 347` or similar) and change it to `>= 353`. Also ensure `gh_intelligence` is listed among the modules that must import and register. The smoke test likely uses a list of module paths — add `"rhmcp.tools.gh_intelligence"` if it auto-discovers modules, this step may be automatic.

Run to confirm:

```bash
uv run pytest tests/test_smoke.py -v 2>&1 | tail -15
```
Expected: All smoke tests pass with the new count.

- [ ] **Step 3: Commit**

```bash
git add tests/test_smoke.py
git commit -m "test(smoke): update expected tool count to 353"
```

---

## Task 10: Integration tests + fixtures

**Files:**
- Create: `tests/test_gh_intelligence_integration.py`
- Create: `tests/fixtures/messy_canvas.gh` (binary — created manually in Rhino)
- Create: `tests/fixtures/simple_migration.gh` (binary — created manually in Rhino)
- Create: `tests/fixtures/messy_gh2_canvas.gh` (binary — created in Rhino 9 only)

- [ ] **Step 1: Create the integration test file**

```python
# tests/test_gh_intelligence_integration.py
"""
Integration tests for GH intelligence tools.
Require: live Rhino 8 with MCPStart running, GH open, fixture files loaded.

Run with:
    uv run pytest tests/test_gh_intelligence_integration.py -m integration -v
"""
from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.mark.integration
class TestGhAnalyzeCanvasIntegration(unittest.TestCase):
    def setUp(self):
        mod = importlib.import_module("rhmcp.tools.gh_intelligence")
        mcp_mod = importlib.import_module("mcp.server.fastmcp")
        mcp = mcp_mod.FastMCP("test-integration")
        mod.register(mcp)
        self.tools = {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}

    def test_analyze_canvas_returns_expected_fields(self):
        """gh_analyze_canvas returns required fields on a live canvas."""
        result = self.tools["gh_analyze_canvas"]()
        self.assertTrue(result.get("ok"), msg=result.get("error"))
        for field in ("component_count", "wire_crossing_estimate", "cluster_count",
                      "complexity_score", "suggestions"):
            self.assertIn(field, result, msg=f"Missing field: {field}")

    def test_analyze_messy_canvas_detects_crossings(self):
        """Open messy_canvas.gh first, then verify crossing count >= 8."""
        # Load fixture
        from rhmcp.tools_helpers import backend as rhino
        open_result = rhino.plugin_result("gh_open_document",
                                          {"path": str(FIXTURES / "messy_canvas.gh")})
        self.assertTrue(open_result.get("ok"), msg=open_result.get("error"))

        result = self.tools["gh_analyze_canvas"]()
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(result["cluster_count"], 3)
        self.assertGreaterEqual(result["wire_crossing_estimate"], 8)

    def test_complexity_score_in_range(self):
        result = self.tools["gh_analyze_canvas"]()
        self.assertTrue(result.get("ok"))
        score = result.get("complexity_score", -1)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


@pytest.mark.integration
class TestGhRefactorCanvasIntegration(unittest.TestCase):
    def setUp(self):
        mod = importlib.import_module("rhmcp.tools.gh_intelligence")
        mcp_mod = importlib.import_module("mcp.server.fastmcp")
        mcp = mcp_mod.FastMCP("test-integration-refactor")
        mod.register(mcp)
        self.tools = {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}

    def test_preview_does_not_move_components(self):
        """apply=False must return plan without changing canvas positions."""
        from rhmcp.tools_helpers import backend as rhino

        # Open fixture
        rhino.plugin_result("gh_open_document",
                            {"path": str(FIXTURES / "messy_canvas.gh")})

        # Record positions before
        before = rhino.plugin_result("gh_get_canvas", {})
        positions_before = {c["instance_guid"]: (c["x"], c["y"])
                            for c in before.get("components", [])}

        result = self.tools["gh_refactor_canvas"](apply=False)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("preview"))

        # Verify positions unchanged
        after = rhino.plugin_result("gh_get_canvas", {})
        positions_after = {c["instance_guid"]: (c["x"], c["y"])
                           for c in after.get("components", [])}
        self.assertEqual(positions_before, positions_after)

    def test_apply_reduces_crossings(self):
        """apply=True must result in fewer wire crossings."""
        from rhmcp.tools_helpers import backend as rhino
        rhino.plugin_result("gh_open_document",
                            {"path": str(FIXTURES / "messy_canvas.gh")})

        before = rhino.plugin_result("gh_get_canvas_analysis", {})
        crossings_before = before.get("wire_crossing_estimate", 0)

        result = self.tools["gh_refactor_canvas"](apply=True)
        self.assertTrue(result.get("ok"), msg=result.get("error"))
        self.assertLess(result["crossings_after"], crossings_before)


@pytest.mark.integration
class TestGhMigrateToGh2Integration(unittest.TestCase):
    def setUp(self):
        mod = importlib.import_module("rhmcp.tools.gh_intelligence")
        mcp_mod = importlib.import_module("mcp.server.fastmcp")
        mcp = mcp_mod.FastMCP("test-integration-migrate")
        mod.register(mcp)
        self.tools = {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}

    @pytest.mark.skipif(
        os.environ.get("RHINO_VERSION", "8") == "8",
        reason="GH2 requires Rhino 9"
    )
    def test_simple_migration_zero_unmapped(self):
        """simple_migration.gh must migrate with zero unmapped components."""
        from rhmcp.tools_helpers import backend as rhino
        rhino.plugin_result("gh_open_document",
                            {"path": str(FIXTURES / "simple_migration.gh")})

        result = self.tools["gh_migrate_to_gh2"](confirm=True)
        self.assertTrue(result.get("ok"), msg=result.get("error"))
        self.assertEqual(result["unmapped"], [])
        self.assertGreater(result["migrated"], 0)
```

- [ ] **Step 2: Create fixture files**

Open Rhino 8, launch Grasshopper. Build `messy_canvas.gh`:
1. Place ~12 components (use Point, Circle, Line, Move, Number, Panel, Slider, Vector, etc.)
2. Wire them in a deliberately tangled way — create wires that cross each other
3. Ensure at least 3 separate clusters (disconnected groups of components)
4. Save as `tests/fixtures/messy_canvas.gh`

Build `simple_migration.gh`:
1. Place only components that exist in `gh1_to_gh2_map.yml` (Point, Circle, Number, Panel, Slider, etc.)
2. Wire a few of them together
3. Save as `tests/fixtures/simple_migration.gh`

For `messy_gh2_canvas.gh` (Rhino 9 only):
1. Open Rhino 9 WIP, run GH2
2. Build a similarly tangled definition
3. Save as `tests/fixtures/messy_gh2_canvas.gh`

- [ ] **Step 3: Run integration tests**

```bash
uv run pytest tests/test_gh_intelligence_integration.py -m integration -v 2>&1 | tail -20
```
Expected: Tests pass (skip GH2 tests on Rhino 8).

- [ ] **Step 4: Commit**

```bash
git add tests/test_gh_intelligence_integration.py \
        tests/fixtures/messy_canvas.gh \
        tests/fixtures/simple_migration.gh
git commit -m "test: GH intelligence integration tests + fixtures (messy_canvas, simple_migration)"
```

---

## Task 11: Version bump + CHANGELOG + full test run

**Files:**
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump version in pyproject.toml**

Change line 7:
```toml
version = "0.11.0"
```
to:
```toml
version = "0.12.0"
```

- [ ] **Step 2: Add CHANGELOG entry**

At the top of `CHANGELOG.md`, after the `# Changelog` header, add:

```markdown
## [0.12.0] — 2026-05-XX

### Added

**GH Intelligence — 6 new tools**

- `gh_analyze_canvas` — analyze GH1 canvas complexity: component count, connection count, wire crossing estimate, cluster detection, complexity score (0–100), suggestions
- `gh_refactor_canvas` — reorganise GH1 canvas to reduce wire crossings; `apply=False` previews plan without touching canvas; `apply=True` applies moves + cluster groups; dry-run validation prevents partial canvas corruption
- `gh2_refactor_canvas` — same as above for GH2 canvases (Rhino 9); reads via `gh2_get_canvas_graph`, writes via new `gh2_move_component` + `gh2_add_group`
- `gh_migrate_to_gh2` — migrate active GH1 definition to GH2 canvas; YAML-driven type mapping; unmapped components reported and skipped; requires `confirm=True`; `close_gh1=False` leaves both open for comparison
- `gh2_move_component` — move a GH2 component to new canvas coordinates (reflection-based)
- `gh2_add_group` — add a group to the GH2 canvas (reflection-based)

Single Python topological-sort layout algorithm shared by both GH1 and GH2 refactor tools (no duplication). GH1→GH2 type mapping in `src/rhmcp/data/gh1_to_gh2_map.yml` — versioned, never user-supplied, schema-validated on load.

**Total: 353 tools** (up from 347)

### Security
- No user input becomes executable code in any new tool — structurally smaller attack surface than script-generation approaches
- All component GUIDs from C# responses re-validated before use in subsequent calls
- Canvas coordinates clamped to ±100,000 canvas units; dry-run validates before first move
- `gh_migrate_to_gh2` requires `confirm=True`; `gh2_clear_canvas` pattern preserved

---
```

- [ ] **Step 3: Run all non-integration tests**

```bash
uv run pytest \
  tests/test_gh_intelligence.py \
  tests/test_smoke.py \
  tests/test_tools_unit.py \
  tests/test_script_syntax.py \
  -v --tb=short -m "not integration" 2>&1 | tail -20
```
Expected: All pass, 0 failures.

- [ ] **Step 4: Run ruff lint**

```bash
uv run ruff check src/rhmcp/tools/gh_intelligence.py \
  --select=E,W,F --ignore=E501,E701,E402,E741
```
Expected: No output (clean).

- [ ] **Step 5: Commit and push**

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): v0.12.0 — GH intelligence, 353 tools"
git push origin main
```

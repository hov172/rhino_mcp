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
                    if (obj is IGH_Component comp)
                    {
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
                    else if (obj is IGH_Param param)
                    {
                        foreach (var r in param.Recipients)
                        {
                            var toGuid = r.Attributes.GetTopLevel.DocObject.InstanceGuid;
                            if (!fwd.ContainsKey(toGuid)) continue;
                            fwd[obj.InstanceGuid].Add(toGuid);
                            rev[toGuid].Add(obj.InstanceGuid);
                            connectionCount++;
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

                var compGuids = new HashSet<Guid>(comps.Select(o => o.InstanceGuid));
                var connections = new List<object>();
                foreach (var obj in comps)
                {
                    if (obj is IGH_Component comp)
                    {
                        foreach (var op in comp.Params.Output)
                            foreach (var r in op.Recipients)
                            {
                                var toGuid = r.Attributes.GetTopLevel.DocObject.InstanceGuid;
                                if (!compGuids.Contains(toGuid)) continue;
                                connections.Add(new
                                {
                                    from_id = obj.InstanceGuid.ToString(),
                                    to_id   = toGuid.ToString()
                                });
                            }
                    }
                    else if (obj is IGH_Param param)
                    {
                        foreach (var r in param.Recipients)
                        {
                            var toGuid = r.Attributes.GetTopLevel.DocObject.InstanceGuid;
                            if (!compGuids.Contains(toGuid)) continue;
                            connections.Add(new
                            {
                                from_id = obj.InstanceGuid.ToString(),
                                to_id   = toGuid.ToString()
                            });
                        }
                    }
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

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Plugin;
using Rhino;
using Rhino.DocObjects;

namespace RhinoMCPPlugin;

/// <summary>
/// Handlers for Grasshopper solution execution: run/expire, bake, enable/disable, state query.
/// </summary>
public static class GHSolutionHandlers
{
    private const int DefaultWaitMs = 10_000;

    // -----------------------------------------------------------------------
    // Read-only
    // -----------------------------------------------------------------------

    public static object GetSolutionState(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetSolutionState did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GHDocumentHandlers.ActiveDoc();
                result = new
                {
                    ok          = true,
                    state       = GHDocumentHandlers.SolutionStateString(doc),
                    duration_ms = doc.SolutionSpan.TotalMilliseconds,
                    error_count = GHDocumentHandlers.CountErrors(doc)
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // Mutating
    // -----------------------------------------------------------------------

    public static object RunSolution(Dictionary<string, JsonElement> p)
    {
        try
        {
            var doc     = GHDocumentHandlers.ActiveDoc();
            var waitMs  = p.Int("wait_ms", DefaultWaitMs);
            var guidStrs = p.StringList("instance_guids");

            using var done = new ManualResetEventSlim(false);
            GH_Document.SolutionEndEventHandler handler = (_, _) => done.Set();
            doc.SolutionEnd += handler;

            try
            {
                RhinoApp.InvokeOnUiThread(new Action(() =>
                {
                    if (guidStrs.Count > 0)
                    {
                        foreach (var gs in guidStrs)
                        {
                            if (Guid.TryParse(gs, out var g))
                            {
                                var obj = doc.FindObject(g, false);
                                obj?.ExpireSolution(false);
                            }
                        }
                    }
                    doc.NewSolution(true);
                }));

                bool completed = done.Wait(waitMs);
                return new
                {
                    ok          = true,
                    state       = GHDocumentHandlers.SolutionStateString(doc),
                    duration_ms = doc.SolutionSpan.TotalMilliseconds,
                    error_count = GHDocumentHandlers.CountErrors(doc),
                    timed_out   = !completed
                };
            }
            finally
            {
                doc.SolutionEnd -= handler;
            }
        }
        catch (InvalidOperationException ex)
        {
            return new { ok = false, error = ex.Message };
        }
        catch (Exception ex)
        {
            return new { ok = false, error = ex.Message };
        }
    }

    public static object BakeComponent(Dictionary<string, JsonElement> p)
    {
        try
        {
            var doc   = GHDocumentHandlers.ActiveDoc();
            var guid  = ParseGuid(p.String("instance_guid"), "instance_guid");
            var layer = p.String("layer");

            var obj = doc.FindObject(guid, false)
                ?? throw new ArgumentException($"Component {guid} not found");

            var errorCount = GHDocumentHandlers.CountErrors(doc);
            string? warning = errorCount > 0
                ? "Solution has errors — baked geometry may be incomplete"
                : null;

            var bakedGuids = new List<string>();
            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                var rhinoDoc = Rhino.RhinoDoc.ActiveDoc;
                int layerIndex = GetOrCreateLayer(rhinoDoc, layer);

                if (obj is IGH_BakeAwareObject bakeable)
                {
                    var attr = new ObjectAttributes { LayerIndex = layerIndex };
                    var ids  = new List<Guid>();
                    bakeable.BakeGeometry(rhinoDoc, attr, ids);
                    bakedGuids.AddRange(ids.Select(g => g.ToString()));
                }
            }));

            var result = new Dictionary<string, object>
            {
                ["ok"]      = true,
                ["objects"] = bakedGuids,
                ["count"]   = bakedGuids.Count
            };
            if (warning != null) result["warning"] = warning;
            return result;
        }
        catch (Exception ex)
        {
            return new { ok = false, error = ex.Message };
        }
    }

    public static object BakeAll(Dictionary<string, JsonElement> p)
    {
        try
        {
            var doc   = GHDocumentHandlers.ActiveDoc();
            var layer = p.String("layer");

            var errorCount = GHDocumentHandlers.CountErrors(doc);
            string? warning = errorCount > 0
                ? "Solution has errors — some geometry may be incomplete"
                : null;

            var bakedGuids = new List<string>();
            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                var rhinoDoc   = Rhino.RhinoDoc.ActiveDoc;
                int layerIndex = GetOrCreateLayer(rhinoDoc, layer);

                foreach (var obj in doc.Objects)
                {
                    if (obj is not IGH_BakeAwareObject bakeable) continue;
                    var attr = new ObjectAttributes { LayerIndex = layerIndex };
                    var ids  = new List<Guid>();
                    bakeable.BakeGeometry(rhinoDoc, attr, ids);
                    bakedGuids.AddRange(ids.Select(g => g.ToString()));
                }
            }));

            var result = new Dictionary<string, object>
            {
                ["ok"]      = true,
                ["objects"] = bakedGuids,
                ["count"]   = bakedGuids.Count
            };
            if (warning != null) result["warning"] = warning;
            return result;
        }
        catch (Exception ex)
        {
            return new { ok = false, error = ex.Message };
        }
    }

    public static object EnableComponent(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "EnableComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc     = GHDocumentHandlers.ActiveDoc();
                var guid    = ParseGuid(p.String("instance_guid"), "instance_guid");
                var enabled = p.Bool("enabled", true);
                var obj     = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not IGH_ActiveObject active)
                    throw new ArgumentException($"Component {guid} is not an active object");

                active.Locked = !enabled; // Locked=true means disabled
                active.ExpireSolution(true);
                result = new { ok = true, enabled = enabled };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    private static Guid ParseGuid(string? s, string paramName)
    {
        if (string.IsNullOrWhiteSpace(s))
            throw new ArgumentException($"{paramName} is required");
        if (!Guid.TryParse(s, out var g))
            throw new ArgumentException($"Invalid {paramName}: {s}");
        return g;
    }

    private static int GetOrCreateLayer(Rhino.RhinoDoc rhinoDoc, string? layerName)
    {
        if (string.IsNullOrWhiteSpace(layerName))
            return rhinoDoc.Layers.CurrentLayerIndex;

        int idx = rhinoDoc.Layers.FindByFullPath(layerName, RhinoMath.UnsetIntIndex);
        if (idx >= 0) return idx;

        var layer = new Layer { Name = layerName };
        return rhinoDoc.Layers.Add(layer);
    }
}

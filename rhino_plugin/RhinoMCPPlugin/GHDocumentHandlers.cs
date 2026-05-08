using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Plugin;
using Rhino;

namespace RhinoMCPPlugin;

/// <summary>
/// Handlers for Grasshopper definition lifecycle (open, new, save, close, info).
/// All mutations run on the UI thread via RhinoApp.InvokeOnUiThread.
/// </summary>
public static class GHDocumentHandlers
{
    // -----------------------------------------------------------------------
    // Internal helpers shared by all GH handler files
    // -----------------------------------------------------------------------

    /// <summary>Returns the active GH_Document or throws with a clear message.</summary>
    internal static GH_Document ActiveDoc()
    {
        // Use reflection to avoid compile-time System.Windows.Forms dependency.
        var canvas = typeof(Instances).GetProperty("ActiveCanvas")?.GetValue(null);
        if (canvas == null)
            throw new InvalidOperationException("Grasshopper is not loaded");
        var doc = canvas.GetType().GetProperty("Document")?.GetValue(canvas) as GH_Document;
        if (doc == null)
            throw new InvalidOperationException("No active Grasshopper definition");
        return doc;
    }

    /// <summary>Maps GH_ProcessStep to a readable string.</summary>
    internal static string SolutionStateString(GH_Document doc)
    {
        return doc.SolutionState switch
        {
            GH_ProcessStep.Process     => "computing",
            GH_ProcessStep.PostProcess => "post_process",
            _                          => "idle"
        };
    }

    /// <summary>Counts runtime errors across all active objects in a document.</summary>
    internal static int CountErrors(GH_Document doc)
    {
        int count = 0;
        foreach (var obj in doc.Objects)
            if (obj is IGH_ActiveObject active &&
                active.RuntimeMessageLevel == GH_RuntimeMessageLevel.Error)
                count++;
        return count;
    }

    // -----------------------------------------------------------------------
    // Command handlers
    // -----------------------------------------------------------------------

    public static object GetDefinitionInfo(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetDefinitionInfo did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = ActiveDoc();
                result = new
                {
                    ok              = true,
                    name            = doc.DisplayName,
                    path            = doc.FilePath ?? "",
                    component_count = doc.ObjectCount,
                    group_count     = doc.Objects.OfType<GH_Group>().Count(),
                    solution_state  = SolutionStateString(doc),
                    error_count     = CountErrors(doc)
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object OpenDocument(Dictionary<string, JsonElement> p)
    {
        var path = p.String("path");
        if (string.IsNullOrWhiteSpace(path))
            return new { ok = false, error = "path is required" };
        if (!File.Exists(path))
            return new { ok = false, error = $"File not found: {path}" };

        object result = new { ok = false, error = "OpenDocument did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var io = new GH_DocumentIO();
                if (!io.Open(path))
                {
                    result = new { ok = false, error = $"Grasshopper failed to open: {path}" };
                    return;
                }
                var doc = io.Document;
                Instances.DocumentServer.AddDocument(doc);
                var canvas2 = typeof(Instances).GetProperty("ActiveCanvas")?.GetValue(null);
                if (canvas2 != null)
                    canvas2.GetType().GetProperty("Document")?.SetValue(canvas2, doc);
                doc.NewSolution(false);
                result = new
                {
                    ok              = true,
                    name            = doc.DisplayName,
                    component_count = doc.ObjectCount,
                    solution_state  = SolutionStateString(doc)
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object NewDocument(Dictionary<string, JsonElement> p)
    {
        var name = p.String("name") ?? "Untitled";

        // Open GH editor if not yet loaded (canvas null until GH is shown)
        var canvasCheck = typeof(Instances).GetProperty("ActiveCanvas")?.GetValue(null);
        if (canvasCheck == null)
            RhinoApp.InvokeOnUiThread(new Action(() => RhinoApp.RunScript("Grasshopper", false)));

        object result = new { ok = false, error = "NewDocument did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = new GH_Document();
                doc.Properties.ProjectFileName = name;
                Instances.DocumentServer.AddDocument(doc);
                // Use reflection to set canvas doc — avoids compile-time WinForms dep
                var canvas = typeof(Instances).GetProperty("ActiveCanvas")?.GetValue(null);
                if (canvas != null)
                    canvas.GetType().GetProperty("Document")?.SetValue(canvas, doc);
                result = new { ok = true, definition_id = doc.DocumentID.ToString() };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SaveDocument(Dictionary<string, JsonElement> p)
    {
        try
        {
            var doc = ActiveDoc();
            var savePath = p.String("path");
            object result = new { ok = false, error = "SaveDocument did not complete" };
            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try
                {
                    var io = new GH_DocumentIO(doc);
                    bool ok;
                    string saved;
                    if (!string.IsNullOrWhiteSpace(savePath))
                    {
                        ok    = io.SaveQuiet(savePath);
                        saved = savePath;
                    }
                    else
                    {
                        ok    = io.Save();
                        saved = doc.FilePath ?? "";
                    }
                    result = ok
                        ? (object)new { ok = true, saved_path = saved }
                        : new { ok = false, error = "Save failed" };
                }
                catch (Exception ex)
                {
                    result = new { ok = false, error = ex.Message };
                }
            }));
            return result;
        }
        catch (InvalidOperationException ex)
        {
            return new { ok = false, error = ex.Message };
        }
    }

    public static object CloseDocument(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "CloseDocument did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var script = new GH_RhinoScriptInterface();
                script.CloseDocument();
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }
}

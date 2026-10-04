using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text.Json;
using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
using Grasshopper.Kernel.Special;
using Rhino;
using Rhino.Geometry;

namespace RhinoMCPPlugin;

/// <summary>
/// Handlers for Grasshopper parameter I/O: sliders, panels, number/point params,
/// output reading, error inspection, and script components.
/// </summary>
public static class GHParamHandlers
{
    // Script component GUIDs (stable across Rhino 7/8)
    private static readonly Guid CSharpScriptGuid  = new Guid("0D6525D3-5B8A-4FE2-A24E-AB076F640835");
    private static readonly Guid PythonScriptGuid  = new Guid("6B17E69B-0F24-41F1-BFC3-FD80C0A049D8");

    // -----------------------------------------------------------------------
    // Read-only
    // -----------------------------------------------------------------------

    public static object GetOutput(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetOutput did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var obj  = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");

                var outputName = p.String("output_name");
                var results    = new List<object>();

                IEnumerable<IGH_Param> targets;
                if (obj is IGH_Component comp)
                    targets = string.IsNullOrWhiteSpace(outputName)
                        ? comp.Params.Output
                        : comp.Params.Output.Where(o =>
                            string.Equals(o.NickName, outputName, StringComparison.OrdinalIgnoreCase));
                else if (obj is IGH_Param param)
                    targets = new[] { param };
                else
                {
                    result = new { ok = false, error = "Object is not a component or param" };
                    return;
                }

                foreach (var outParam in targets)
                {
                    var values = new List<string>();
                    foreach (var path in outParam.VolatileData.Paths)
                        foreach (var item in outParam.VolatileData.get_Branch(path))
                            values.Add(item?.ToString() ?? "null");

                    results.Add(new
                    {
                        name        = outParam.NickName,
                        data_type   = outParam.TypeName,
                        path_count  = outParam.VolatileData.PathCount,
                        value_count = values.Count,
                        values      = values
                    });
                }
                result = new { ok = true, outputs = results };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object GetSolutionErrors(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetSolutionErrors did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc      = GHDocumentHandlers.ActiveDoc();
                var guidStr  = p.String("instance_guid");
                var messages = new List<object>();

                IEnumerable<IGH_DocumentObject> targets = string.IsNullOrWhiteSpace(guidStr)
                    ? doc.Objects
                    : new[] { doc.FindObject(ParseGuid(guidStr, "instance_guid"), false)! }
                        .Where(o => o != null);

                foreach (var obj in targets)
                {
                    if (obj is not IGH_ActiveObject active) continue;
                    foreach (var msg in active.RuntimeMessages(GH_RuntimeMessageLevel.Error))
                        messages.Add(new { component = obj.NickName, message = msg, level = "error" });
                    foreach (var msg in active.RuntimeMessages(GH_RuntimeMessageLevel.Warning))
                        messages.Add(new { component = obj.NickName, message = msg, level = "warning" });
                }
                result = new { ok = true, messages = messages, count = messages.Count };
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

    public static object SetSlider(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "SetSlider did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc    = GHDocumentHandlers.ActiveDoc();
                var guid   = ParseGuid(p.String("instance_guid"), "instance_guid");
                var value  = p.Double("value", double.NaN);
                if (double.IsNaN(value))
                    throw new ArgumentException("value is required");

                var obj = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not GH_NumberSlider slider)
                    throw new ArgumentException($"Component {guid} is not a Number Slider");

                slider.SetSliderValue((decimal)value);
                slider.ExpireSolution(true);
                result = new { ok = true, clamped_value = (double)slider.CurrentValue };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SetPanel(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "SetPanel did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var text = p.String("text") ?? "";
                var obj  = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not GH_Panel panel)
                    throw new ArgumentException($"Component {guid} is not a Panel");

                panel.SetUserText(text);
                panel.ExpireSolution(true);
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SetNumberParam(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "SetNumberParam did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc    = GHDocumentHandlers.ActiveDoc();
                var guid   = ParseGuid(p.String("instance_guid"), "instance_guid");
                var values = p.DoubleArray("values")
                    ?? throw new ArgumentException("values (list of floats) is required");
                if (values.Length == 0)
                    throw new ArgumentException("values must be a non-empty list of floats — an empty list would wipe the parameter");

                var obj = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not GH_PersistentParam<GH_Number> numParam)
                    throw new ArgumentException($"Component {guid} is not a Number parameter");

                var tree = new GH_Structure<GH_Number>();
                var path = new GH_Path(0);
                foreach (var v in values)
                    tree.Append(new GH_Number(v), path);

                numParam.SetPersistentData(tree);
                numParam.ExpireSolution(true);
                result = new { ok = true, count = values.Length };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SetPointParam(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "SetPointParam did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var obj  = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not GH_PersistentParam<GH_Point> ptParam)
                    throw new ArgumentException($"Component {guid} is not a Point parameter");

                // Expect [[x,y,z], [x,y,z], ...] in the "points" array
                var raw = p.DoubleArray("points");
                if (raw == null || raw.Length == 0)
                    throw new ArgumentException("points must be a flat array of [x,y,z,...] or nested (resolved via JSON)");

                var tree = new GH_Structure<GH_Point>();
                var path = new GH_Path(0);

                // Support flat array triplets
                for (int i = 0; i + 2 < raw.Length; i += 3)
                    tree.Append(new GH_Point(new Point3d(raw[i], raw[i + 1], raw[i + 2])), path);

                ptParam.SetPersistentData(tree);
                ptParam.ExpireSolution(true);
                result = new { ok = true, count = tree.DataCount };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object AddScriptComponent(Dictionary<string, JsonElement> p)
    {
        // Rhino 7 guard — script GUIDs are Rhino 8 RhinoCode
        if (RhinoApp.Version.Major < 8)
            return new { ok = false, error = "Script components require Rhino 8" };

        object result = new { ok = false, error = "AddScriptComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc      = GHDocumentHandlers.ActiveDoc();
                var language = (p.String("language") ?? "python").ToLowerInvariant();
                var code     = p.String("code") ?? "";
                var x        = (float)p.Double("x", 0);
                var y        = (float)p.Double("y", 0);
                var inputs   = p.StringList("inputs");
                var outputs  = p.StringList("outputs");

                var scriptGuid = language == "csharp" || language == "cs"
                    ? CSharpScriptGuid
                    : PythonScriptGuid;

                var obj = Instances.ComponentServer.EmitObject(scriptGuid)
                    ?? throw new InvalidOperationException($"Could not create script component for language '{language}'. Ensure Rhino 8 scripting is installed.");
                if (obj is not IGH_Component comp)
                    throw new InvalidOperationException($"Script object for '{language}' is not a GH component");

                obj.CreateAttributes();
                obj.Attributes.Pivot = new PointF(x, y);

                // Configure before AddObject so a failure leaves nothing on the canvas.
                var srcParam = comp.Params.Input.OfType<GH_PersistentParam<GH_String>>().FirstOrDefault();
                if (p.ContainsKey("inputs"))
                    ReshapeVariableParams(comp, GH_ParameterSide.Input, inputs, srcParam);
                if (p.ContainsKey("outputs"))
                    ReshapeVariableParams(comp, GH_ParameterSide.Output, outputs, null);

                if (!string.IsNullOrWhiteSpace(code))
                {
                    if (srcParam == null)
                        throw new InvalidOperationException(
                            "Code could not be injected: the script component exposes no string-typed source input. Use gh_set_script_code after editing the component manually.");
                    var tree = new GH_Structure<GH_String>();
                    tree.Append(new GH_String(code), new GH_Path(0));
                    srcParam.SetPersistentData(tree);
                }

                doc.AddObject(obj, false);
                comp.ExpireSolution(true);

                result = new
                {
                    ok            = true,
                    instance_guid = obj.InstanceGuid.ToString(),
                    inputs        = comp.Params.Input.Select(q => q.NickName).ToList(),
                    outputs       = comp.Params.Output.Select(q => q.NickName).ToList(),
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SetScriptCode(Dictionary<string, JsonElement> p)
    {
        if (RhinoApp.Version.Major < 8)
            return new { ok = false, error = "Script components require Rhino 8" };

        object result = new { ok = false, error = "SetScriptCode did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var code = p.String("code") ?? "";
                var obj  = doc.FindObject(guid, false)
                    ?? throw new ArgumentException($"Component {guid} not found");
                if (obj is not IGH_Component comp)
                    throw new ArgumentException($"Component {guid} is not a GH component");

                var srcParam = comp.Params.Input.OfType<GH_PersistentParam<GH_String>>().FirstOrDefault()
                    ?? throw new ArgumentException($"Component {guid} has no string input for source code");

                var tree = new GH_Structure<GH_String>();
                tree.Append(new GH_String(code), new GH_Path(0));
                srcParam.SetPersistentData(tree);
                comp.ExpireSolution(true);
                result = new { ok = true };
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

    /// <summary>
    /// Renames/adds/removes the removable variable params on one side so their nicknames
    /// match <paramref name="names"/> in order. Params the component refuses to remove
    /// (e.g. the script source input or `out`) are left untouched. Throws when the
    /// component exposes no variable-parameter API.
    /// </summary>
    private static void ReshapeVariableParams(IGH_Component comp, GH_ParameterSide side, List<string> names, IGH_Param? keep)
    {
        var vpc = VariableParams.For(comp)
            ?? throw new InvalidOperationException("Script component does not support variable parameters; inputs/outputs cannot be reshaped");

        IList<IGH_Param> Side() => side == GH_ParameterSide.Input ? comp.Params.Input : comp.Params.Output;
        List<IGH_Param> Variable() => Side()
            .Where(q => !ReferenceEquals(q, keep) && vpc.CanRemove(side, Side().IndexOf(q)))
            .ToList();

        // Rename existing variable params, then add missing ones at the end.
        var existing = Variable();
        for (int i = 0; i < names.Count; i++)
        {
            IGH_Param target;
            if (i < existing.Count)
                target = existing[i];
            else
            {
                int insertAt = Side().Count;
                if (!vpc.CanInsert(side, insertAt))
                    throw new InvalidOperationException($"Script component refused to add {side.ToString().ToLowerInvariant()} '{names[i]}'");
                target = vpc.Create(side, insertAt)
                    ?? throw new InvalidOperationException($"Script component returned no param for {side.ToString().ToLowerInvariant()} '{names[i]}'");
                if (side == GH_ParameterSide.Input) comp.Params.RegisterInputParam(target, insertAt);
                else comp.Params.RegisterOutputParam(target, insertAt);
            }
            target.Name = names[i];
            target.NickName = names[i];
        }

        // Remove surplus variable params (from the end).
        var surplus = Variable().Skip(names.Count).Reverse().ToList();
        foreach (var prm in surplus)
        {
            int idx = Side().IndexOf(prm);
            if (!vpc.Destroy(side, idx))
                throw new InvalidOperationException($"Script component refused to remove {side.ToString().ToLowerInvariant()} '{prm.NickName}'");
            if (side == GH_ParameterSide.Input) comp.Params.UnregisterInputParameter(prm);
            else comp.Params.UnregisterOutputParameter(prm);
        }

        vpc.Maintain();
        comp.Params.OnParametersChanged();
    }

    /// <summary>
    /// IGH_VariableParameterComponent access with reflection fallback for script
    /// component types that expose the same methods without the interface.
    /// </summary>
    private sealed class VariableParams
    {
        private readonly IGH_VariableParameterComponent? _iface;
        private readonly object _target;
        private readonly System.Reflection.MethodInfo? _canInsert, _canRemove, _create, _destroy, _maintain;

        private VariableParams(IGH_Component comp)
        {
            _target = comp;
            _iface  = comp as IGH_VariableParameterComponent;
            if (_iface != null) return;
            var t = comp.GetType();
            var sig = new[] { typeof(GH_ParameterSide), typeof(int) };
            _canInsert = t.GetMethod("CanInsertParameter", sig);
            _canRemove = t.GetMethod("CanRemoveParameter", sig);
            _create    = t.GetMethod("CreateParameter", sig);
            _destroy   = t.GetMethod("DestroyParameter", sig);
            _maintain  = t.GetMethod("VariableParameterMaintenance", Type.EmptyTypes);
        }

        /// <summary>Returns null when neither the interface nor the reflected methods exist.</summary>
        public static VariableParams? For(IGH_Component comp)
        {
            var vp = new VariableParams(comp);
            bool reflected = vp._canInsert != null && vp._canRemove != null && vp._create != null && vp._destroy != null;
            return vp._iface != null || reflected ? vp : null;
        }

        public bool CanInsert(GH_ParameterSide side, int i) =>
            _iface?.CanInsertParameter(side, i) ?? (bool)_canInsert!.Invoke(_target, new object[] { side, i })!;
        public bool CanRemove(GH_ParameterSide side, int i) =>
            _iface?.CanRemoveParameter(side, i) ?? (bool)_canRemove!.Invoke(_target, new object[] { side, i })!;
        public IGH_Param? Create(GH_ParameterSide side, int i) =>
            _iface != null ? _iface.CreateParameter(side, i) : _create!.Invoke(_target, new object[] { side, i }) as IGH_Param;
        public bool Destroy(GH_ParameterSide side, int i) =>
            _iface?.DestroyParameter(side, i) ?? (bool)_destroy!.Invoke(_target, new object[] { side, i })!;
        public void Maintain()
        {
            if (_iface != null) _iface.VariableParameterMaintenance();
            else _maintain?.Invoke(_target, Array.Empty<object>());
        }
    }

    private static Guid ParseGuid(string? s, string paramName)
    {
        if (string.IsNullOrWhiteSpace(s))
            throw new ArgumentException($"{paramName} is required");
        if (!Guid.TryParse(s, out var g))
            throw new ArgumentException($"Invalid {paramName}: {s}");
        return g;
    }
}

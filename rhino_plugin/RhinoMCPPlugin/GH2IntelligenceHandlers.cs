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

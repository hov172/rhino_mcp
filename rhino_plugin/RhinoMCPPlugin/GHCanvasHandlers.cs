using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Text.Json;
using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Rhino;

namespace RhinoMCPPlugin;

/// <summary>
/// Handlers for Grasshopper canvas manipulation: search components, add/remove/move,
/// wire connections, groups, rename, comments.
/// All mutations run on UI thread via RhinoApp.InvokeOnUiThread.
/// </summary>
public static class GHCanvasHandlers
{
    // -----------------------------------------------------------------------
    // Read-only handlers (no UI thread required)
    // -----------------------------------------------------------------------

    public static object SearchComponents(Dictionary<string, JsonElement> p)
    {
        var query = p.String("query") ?? "";
        var limit = p.Int("limit", 20);
        object result = new { ok = false, error = "SearchComponents did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var server = Instances.ComponentServer;
                var results = new List<object>();
                foreach (var proxy in server.ObjectProxies)
                {
                    if (results.Count >= limit) break;
                    var name = proxy.Desc.Name ?? "";
                    var cat  = proxy.Desc.Category ?? "";
                    var sub  = proxy.Desc.SubCategory ?? "";
                    var desc = proxy.Desc.Description ?? "";
                    if (name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0 ||
                        cat.IndexOf(query,  StringComparison.OrdinalIgnoreCase) >= 0 ||
                        desc.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        results.Add(new
                        {
                            name        = name,
                            category    = cat,
                            subcategory = sub,
                            guid        = proxy.Guid.ToString(),
                            description = desc
                        });
                    }
                }
                result = new { ok = true, components = results, count = results.Count };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object ListComponents(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "ListComponents did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GHDocumentHandlers.ActiveDoc();
                var items = doc.Objects.Select(obj => new
                {
                    instance_guid = obj.InstanceGuid.ToString(),
                    name          = obj.Name ?? "",
                    type          = obj.GetType().Name,
                    x             = (int)obj.Attributes.Pivot.X,
                    y             = (int)obj.Attributes.Pivot.Y
                }).ToList();
                result = new { ok = true, components = items, count = items.Count };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object GetCanvas(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetCanvas did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc          = GHDocumentHandlers.ActiveDoc();
                var includeWires = p.Bool("include_wires", true);

                var components = new List<object>();
                var wires      = new List<object>();
                var groups     = new List<object>();

                foreach (var obj in doc.Objects)
                {
                    if (obj is GH_Group grp)
                    {
                        groups.Add(new
                        {
                            id      = grp.InstanceGuid.ToString(),
                            label   = grp.NickName ?? "",
                            members = grp.ObjectIDs.Select(g => g.ToString()).ToList()
                        });
                        continue;
                    }

                    var inputs  = new List<object>();
                    var outputs = new List<object>();

                    if (obj is IGH_Component comp)
                    {
                        foreach (var ip in comp.Params.Input)
                            inputs.Add(new { name = ip.NickName, data_count = ip.VolatileDataCount });
                        foreach (var op in comp.Params.Output)
                        {
                            outputs.Add(new { name = op.NickName, data_count = op.VolatileDataCount });
                            if (includeWires)
                            {
                                foreach (var recipient in op.Recipients)
                                {
                                    wires.Add(new
                                    {
                                        from_guid   = obj.InstanceGuid.ToString(),
                                        from_output = op.NickName,
                                        to_guid     = recipient.Attributes.GetTopLevel.DocObject.InstanceGuid.ToString(),
                                        to_input    = recipient.NickName
                                    });
                                }
                            }
                        }
                    }
                    else if (obj is IGH_Param param)
                    {
                        inputs.Add(new { name = param.NickName, data_count = param.VolatileDataCount });
                    }

                    components.Add(new
                    {
                        instance_guid = obj.InstanceGuid.ToString(),
                        name          = obj.Name ?? "",
                        nick_name     = obj.NickName ?? "",
                        type          = obj.GetType().Name,
                        x             = (int)obj.Attributes.Pivot.X,
                        y             = (int)obj.Attributes.Pivot.Y,
                        locked        = obj is IGH_ActiveObject ao && ao.Locked,
                        inputs        = inputs,
                        outputs       = outputs
                    });
                }

                result = new
                {
                    ok         = true,
                    components = components,
                    wires      = wires,
                    groups     = groups
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object GetComponentInfo(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "GetComponentInfo did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var obj  = doc.FindObject(guid, false);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found" };
                    return;
                }

                var inputs  = new List<object>();
                var outputs = new List<object>();

                if (obj is IGH_Component comp)
                {
                    foreach (var ip in comp.Params.Input)
                        inputs.Add(new { name = ip.NickName, type = ip.TypeName, optional = ip.Optional });
                    foreach (var op in comp.Params.Output)
                        outputs.Add(new { name = op.NickName, type = op.TypeName });
                }
                else if (obj is IGH_Param param)
                {
                    inputs.Add(new { name = param.NickName, type = param.TypeName, optional = false });
                }

                result = new
                {
                    ok            = true,
                    instance_guid = obj.InstanceGuid.ToString(),
                    name          = obj.Name ?? "",
                    nick_name     = obj.NickName ?? "",
                    type          = obj.GetType().Name,
                    x             = (int)obj.Attributes.Pivot.X,
                    y             = (int)obj.Attributes.Pivot.Y,
                    locked        = obj is IGH_ActiveObject ao && ao.Locked,
                    inputs        = inputs,
                    outputs       = outputs
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
    // Mutating handlers (UI thread required)
    // -----------------------------------------------------------------------

    public static object AddComponent(Dictionary<string, JsonElement> p)
    {
        var compGuidStr = p.String("component_guid");
        var typeName    = p.String("type_name") ?? p.String("name");
        if (string.IsNullOrWhiteSpace(compGuidStr) && string.IsNullOrWhiteSpace(typeName))
            return new { ok = false, error = "component_guid or type_name is required" };
        var compGuid = Guid.Empty;
        if (!string.IsNullOrWhiteSpace(compGuidStr) && !Guid.TryParse(compGuidStr, out compGuid))
            return new { ok = false, error = $"Invalid component_guid: {compGuidStr}" };

        var x = (float)p.Double("x", 0);
        var y = (float)p.Double("y", 0);

        object result = new { ok = false, error = "AddComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GHDocumentHandlers.ActiveDoc();
                if (compGuid == Guid.Empty)
                {
                    var proxy = Instances.ComponentServer.FindObjectByName(typeName, true, true);
                    if (proxy == null)
                    {
                        result = new { ok = false, error = $"No component named '{typeName}'. Use gh_search_components to find the name or GUID." };
                        return;
                    }
                    compGuid = proxy.Guid;
                }
                var obj = Instances.ComponentServer.EmitObject(compGuid);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Unknown component GUID: {compGuid}" };
                    return;
                }
                obj.CreateAttributes();
                obj.Attributes.Pivot = new PointF(x, y);
                doc.AddObject(obj, false);

                var inputs  = new List<string>();
                var outputs = new List<string>();
                if (obj is IGH_Component comp)
                {
                    inputs.AddRange(comp.Params.Input.Select(i  => i.NickName));
                    outputs.AddRange(comp.Params.Output.Select(o => o.NickName));
                }

                result = new
                {
                    ok            = true,
                    instance_guid = obj.InstanceGuid.ToString(),
                    name          = obj.Name ?? "",
                    inputs        = inputs,
                    outputs       = outputs
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object RemoveComponent(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "RemoveComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var obj  = doc.FindObject(guid, false);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found" };
                    return;
                }
                doc.RemoveObject(obj, false);
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object MoveComponent(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "MoveComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc  = GHDocumentHandlers.ActiveDoc();
                var guid = ParseGuid(p.String("instance_guid"), "instance_guid");
                var obj  = doc.FindObject(guid, false);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found" };
                    return;
                }
                obj.Attributes.Pivot = new PointF((float)p.Double("x", 0), (float)p.Double("y", 0));
                obj.Attributes.ExpireLayout();
                doc.ExpirePreview(false);
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object RenameComponent(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "RenameComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc     = GHDocumentHandlers.ActiveDoc();
                var guid    = ParseGuid(p.String("instance_guid"), "instance_guid");
                var newName = p.String("new_name") ?? throw new ArgumentException("new_name is required");
                var obj     = doc.FindObject(guid, false);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found" };
                    return;
                }
                obj.NickName = newName;
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object SetComponentComment(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "SetComponentComment did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc     = GHDocumentHandlers.ActiveDoc();
                var guid    = ParseGuid(p.String("instance_guid"), "instance_guid");
                var comment = p.String("comment") ?? "";
                var obj     = doc.FindObject(guid, false);
                if (obj == null)
                {
                    result = new { ok = false, error = $"Component {guid} not found" };
                    return;
                }
                obj.Description = comment;
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object ConnectWire(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "ConnectWire did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc       = GHDocumentHandlers.ActiveDoc();
                var fromGuid  = ParseGuid(p.String("from_guid"),  "from_guid");
                var toGuid    = ParseGuid(p.String("to_guid"),    "to_guid");
                var fromEl    = RequirePort(p, "from_output");
                var toEl      = RequirePort(p, "to_input");

                var fromObj = doc.FindObject(fromGuid, false)
                    ?? throw new ArgumentException($"Source object {fromGuid} not found");
                var toObj   = doc.FindObject(toGuid, false)
                    ?? throw new ArgumentException($"Target object {toGuid} not found");

                var outParam = ResolveOutput(fromObj, fromEl, fromGuid);
                var inParam  = ResolveInput(toObj, toEl, toGuid);

                inParam.AddSource(outParam);
                inParam.ExpireSolution(false);
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object DisconnectWire(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "DisconnectWire did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc      = GHDocumentHandlers.ActiveDoc();
                var fromGuid = ParseGuid(p.String("from_guid"), "from_guid");
                var toGuid   = ParseGuid(p.String("to_guid"),   "to_guid");
                var fromEl   = RequirePort(p, "from_output");
                var toEl     = RequirePort(p, "to_input");

                var fromObj = doc.FindObject(fromGuid, false)
                    ?? throw new ArgumentException($"Source object {fromGuid} not found");
                var toObj   = doc.FindObject(toGuid, false)
                    ?? throw new ArgumentException($"Target object {toGuid} not found");
                var outParam = ResolveOutput(fromObj, fromEl, fromGuid);
                var inParam  = ResolveInput(toObj, toEl, toGuid);

                var src = inParam.Sources.FirstOrDefault(s => s.InstanceGuid == outParam.InstanceGuid);
                if (src == null)
                {
                    result = new { ok = false, error = $"Wire from '{fromEl}' on {fromGuid} to '{toEl}' on {toGuid} not found" };
                    return;
                }
                inParam.RemoveSource(src);
                inParam.ExpireSolution(false);
                result = new { ok = true };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    public static object AddGroup(Dictionary<string, JsonElement> p)
    {
        object result = new { ok = false, error = "AddGroup did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc   = GHDocumentHandlers.ActiveDoc();
                var guids = p.StringList("instance_guids")
                    .Select(s => Guid.Parse(s)).ToList();
                var label = p.String("label") ?? "";
                var colorArr = p.DoubleArray("color");

                var grp = new GH_Group();
                grp.NickName = label;
                if (colorArr != null && colorArr.Length >= 3)
                    grp.Colour = Color.FromArgb(
                        (int)colorArr[0], (int)colorArr[1], (int)colorArr[2]);

                foreach (var g in guids)
                    grp.AddObject(g);

                doc.AddObject(grp, false);
                result = new { ok = true, group_id = grp.InstanceGuid.ToString() };
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

    private static JsonElement RequirePort(Dictionary<string, JsonElement> p, string key)
    {
        if (!p.TryGetValue(key, out var el) || el.ValueKind == JsonValueKind.Null)
            throw new ArgumentException($"{key} is required");
        return el;
    }

    /// <summary>
    /// Port reference: JSON number = 0-based index, string = nickname or name (case-insensitive),
    /// numeric string = index. Same contract as the GH2 handlers.
    /// </summary>
    private static IGH_Param FindPort(IList<IGH_Param> ports, JsonElement el, string kind, Guid owner)
    {
        if (el.ValueKind == JsonValueKind.Number && el.TryGetInt32(out var idx))
            return idx >= 0 && idx < ports.Count
                ? ports[idx]
                : throw new ArgumentException($"{kind} index {idx} is out of range on {owner} ({ports.Count} ports)");

        var text = el.ValueKind == JsonValueKind.String ? el.GetString() ?? "" : el.ToString();
        var byName = ports.FirstOrDefault(prm =>
            string.Equals(prm.NickName, text, StringComparison.OrdinalIgnoreCase)
            || string.Equals(prm.Name, text, StringComparison.OrdinalIgnoreCase));
        if (byName != null) return byName;
        if (int.TryParse(text, out var strIdx) && strIdx >= 0 && strIdx < ports.Count)
            return ports[strIdx];
        throw new ArgumentException($"{kind} '{text}' not found on {owner}");
    }

    // Standalone params (panels, sliders, Param_Number, ...) are valid wire
    // endpoints too — they act as their own output/input.
    private static IGH_Param ResolveOutput(IGH_DocumentObject obj, JsonElement port, Guid owner) => obj switch
    {
        IGH_Component c => FindPort(c.Params.Output, port, "Output", owner),
        IGH_Param prm   => prm,
        _ => throw new ArgumentException($"Source {owner} is not a component or parameter"),
    };

    private static IGH_Param ResolveInput(IGH_DocumentObject obj, JsonElement port, Guid owner) => obj switch
    {
        IGH_Component c => FindPort(c.Params.Input, port, "Input", owner),
        IGH_Param prm   => prm,
        _ => throw new ArgumentException($"Target {owner} is not a component or parameter"),
    };

    private static Guid ParseGuid(string? s, string paramName)
    {
        if (string.IsNullOrWhiteSpace(s))
            throw new ArgumentException($"{paramName} is required");
        if (!Guid.TryParse(s, out var g))
            throw new ArgumentException($"Invalid {paramName}: {s}");
        return g;
    }
}

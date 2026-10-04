using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Reflection;
using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

/// <summary>
/// Handlers for Grasshopper 2 commands. All GH2 types are accessed via runtime
/// reflection to avoid compile-time dependencies on Grasshopper2.dll, which may
/// not be present in all Rhino installations.
///
/// If GH2 is absent entirely, every handler returns {"ok":false,"error":"Grasshopper 2 is not available…"}.
/// If GH2 is present but a specific API is missing (build variation), each handler
/// returns a targeted "not available in this build" message.
/// </summary>
public static class GH2Handlers
{
    // NOTE: All public handlers in this class are invoked from the UI thread
    // (via RhinoMcpServer.InvokeOnRhinoThread → CommandDispatcher.Dispatch).
    // The inner RhinoApp.InvokeOnUiThread calls below are therefore synchronous
    // re-entrant dispatches, not async fire-and-forget. This matches the
    // pattern used by GHDocumentHandlers and GHCanvasHandlers.

    // -----------------------------------------------------------------------
    // Assembly discovery
    // -----------------------------------------------------------------------

    private static Assembly? _gh2Asm;

    private static Assembly? GetGH2Assembly()
    {
        if (_gh2Asm != null) return _gh2Asm;
        _gh2Asm = AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name == "Grasshopper2");
        return _gh2Asm;
    }

    private static bool Gh2Available() => GetGH2Assembly() != null;

    private static object NotAvailable() =>
        new { ok = false, error = "Grasshopper 2 is not available in this Rhino installation." };

    private static object ApiNotAvailable(string detail) =>
        new { ok = false, error = $"GH2 component API not available in this build: {detail}" };

    // -----------------------------------------------------------------------
    // Reflection helpers
    // -----------------------------------------------------------------------

    /// <summary>
    /// Tries to find and return the active GH2 document object via reflection.
    /// Returns null if not found.
    /// </summary>
    private static object? GetActiveGH2Doc()
    {
        var asm = GetGH2Assembly();
        if (asm == null) return null;

        // Try common type paths for GH2 document server / active doc
        foreach (var typeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.Instances", "GH_Instances" })
        {
            var instType = asm.GetType(typeName);
            if (instType == null) continue;

            // Try ActiveDocument property
            foreach (var propName in new[] { "ActiveDocument", "ActiveDoc", "Document" })
            {
                var prop = instType.GetProperty(propName, BindingFlags.Static | BindingFlags.Public);
                if (prop != null)
                    return prop.GetValue(null);
            }
        }

        // Try via canvas
        foreach (var typeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.Instances" })
        {
            var instType = asm.GetType(typeName);
            if (instType == null) continue;
            var canvasProp = instType.GetProperty("ActiveCanvas", BindingFlags.Static | BindingFlags.Public);
            if (canvasProp == null) continue;
            var canvas = canvasProp.GetValue(null);
            if (canvas == null) continue;
            var docProp = canvas.GetType().GetProperty("Document");
            if (docProp != null)
                return docProp.GetValue(canvas);
        }

        return null;
    }

    /// <summary>Gets enumerable objects from GH2 document, or empty list.</summary>
    private static List<object> GetDocObjects(object doc)
    {
        // Try Objects property
        var objsProp = doc.GetType().GetProperty("Objects");
        if (objsProp != null)
        {
            var objs = objsProp.GetValue(doc);
            if (objs is System.Collections.IEnumerable en)
                return en.Cast<object>().ToList();
        }
        return new List<object>();
    }

    private static Guid ParseGuid(string? s, string paramName)
    {
        if (string.IsNullOrWhiteSpace(s))
            throw new ArgumentException($"{paramName} is required");
        if (!Guid.TryParse(s, out var g))
            throw new ArgumentException($"Invalid {paramName}: {s}");
        return g;
    }

    // -----------------------------------------------------------------------
    // Command handlers
    // -----------------------------------------------------------------------

    /// <summary>gh2_start — launch Grasshopper 2 via RunScript.</summary>
    public static object Start(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "Start did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                RhinoApp.RunScript("_Grasshopper2", false);
                result = new { ok = true };
            }
            catch (Exception ex) { result = new { ok = false, error = ex.Message }; }
        }));
        return result;
    }

    /// <summary>gh2_get_canvas_graph — list components and wires from active GH2 document.</summary>
    public static object GetCanvasGraph(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "GetCanvasGraph did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                {
                    // GH2 loaded but doc not accessible — graceful degradation
                    result = new
                    {
                        ok = true,
                        components = Array.Empty<object>(),
                        wires = Array.Empty<object>(),
                        note = "GH2 canvas inspection not available in this build"
                    };
                    return;
                }

                var objects  = GetDocObjects(doc);
                var components = new List<object>();
                var wires      = new List<object>();

                foreach (var obj in objects)
                {
                    var objType     = obj.GetType();
                    var instanceId  = objType.GetProperty("InstanceGuid")?.GetValue(obj)?.ToString() ?? Guid.NewGuid().ToString();
                    var name        = objType.GetProperty("Name")?.GetValue(obj)?.ToString() ?? "";
                    var nickName    = objType.GetProperty("NickName")?.GetValue(obj)?.ToString() ?? "";
                    var typeName    = objType.Name;

                    // Attempt to get pivot position
                    int x = 0, y = 0;
                    var attrs = objType.GetProperty("Attributes")?.GetValue(obj);
                    if (attrs != null)
                    {
                        var pivot = attrs.GetType().GetProperty("Pivot")?.GetValue(attrs);
                        if (pivot != null)
                        {
                            x = (int)(pivot.GetType().GetProperty("X")?.GetValue(pivot) ?? 0.0f);
                            y = (int)(pivot.GetType().GetProperty("Y")?.GetValue(pivot) ?? 0.0f);
                        }
                    }

                    // Attempt to enumerate outputs and collect wires
                    var paramsProp = objType.GetProperty("Params");
                    if (paramsProp != null)
                    {
                        var paramsObj = paramsProp.GetValue(obj);
                        if (paramsObj != null)
                        {
                            var outputsProp = paramsObj.GetType().GetProperty("Output");
                            if (outputsProp != null)
                            {
                                var outputs = outputsProp.GetValue(paramsObj) as System.Collections.IEnumerable;
                                if (outputs != null)
                                {
                                    foreach (var op in outputs)
                                    {
                                        var opType = op.GetType();
                                        var opName = opType.GetProperty("NickName")?.GetValue(op)?.ToString() ?? "";
                                        var recipients = opType.GetProperty("Recipients")?.GetValue(op) as System.Collections.IEnumerable;
                                        if (recipients != null)
                                        {
                                            foreach (var rec in recipients)
                                            {
                                                try
                                                {
                                                    var recType  = rec.GetType();
                                                    var recAttrs = recType.GetProperty("Attributes")?.GetValue(rec);
                                                    var topLevel = recAttrs?.GetType().GetProperty("GetTopLevel")?.GetValue(recAttrs);
                                                    var toDoc    = topLevel?.GetType().GetProperty("DocObject")?.GetValue(topLevel);
                                                    var toGuid   = toDoc?.GetType().GetProperty("InstanceGuid")?.GetValue(toDoc)?.ToString() ?? "";
                                                    var toName   = recType.GetProperty("NickName")?.GetValue(rec)?.ToString() ?? "";
                                                    if (!string.IsNullOrEmpty(toGuid))
                                                        wires.Add(new
                                                        {
                                                            from_guid   = instanceId,
                                                            from_output = opName,
                                                            to_guid     = toGuid,
                                                            to_input    = toName
                                                        });
                                                }
                                                catch { /* skip unresolvable wire */ }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    components.Add(new { instance_guid = instanceId, name, nick_name = nickName, type = typeName, x, y });
                }

                result = new { ok = true, components, wires };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>
    /// gh2_apply_graph — place components + sliders + wires in one call.
    /// components: [{key, type_name|name|component_guid, x, y} | {key, type:"slider", min, max, value, decimals, x, y}]
    /// wires: [{from_key|from_guid, from_output, to_key|to_guid, to_input}] — ports are nickname or index.
    /// Returns {ok, placed: {key: instance_guid}, wired, errors}.
    /// </summary>
    public static object ApplyGraph(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "ApplyGraph did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                var placedMap = new Dictionary<string, string>();
                var errors    = new List<string>();

                // Place components
                if (p.TryGetValue("components", out var compsEl) && compsEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var compEl in compsEl.EnumerateArray())
                    {
                        try
                        {
                            var compDict = compEl.EnumerateObject()
                                .ToDictionary(kv => kv.Name, kv => kv.Value);
                            string compKey = compDict.TryGetValue("key", out var keyEl) ? keyEl.GetString() ?? "" : "";
                            bool isSlider = compDict.TryGetValue("type", out var typeEl)
                                && typeEl.ValueKind == JsonValueKind.String
                                && string.Equals(typeEl.GetString(), "slider", StringComparison.OrdinalIgnoreCase);
                            var placed = isSlider ? PlaceSliderInternal(doc, compDict) : PlaceComponentInternal(doc, compDict);
                            if (placed is string guid && !guid.StartsWith("ERROR:", StringComparison.Ordinal))
                                placedMap[compKey] = guid;
                            else
                                errors.Add($"{compKey}: {placed?.ToString() ?? "unknown error placing component"}");
                        }
                        catch (Exception ex) { errors.Add(ex.Message); }
                    }
                }

                // Legacy: separate top-level sliders array (inline {type:"slider"} items are preferred)
                if (p.TryGetValue("sliders", out var slidersEl) && slidersEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var sliderEl in slidersEl.EnumerateArray())
                    {
                        try
                        {
                            var sliderDict = sliderEl.EnumerateObject()
                                .ToDictionary(kv => kv.Name, kv => kv.Value);
                            string sliderKey = sliderDict.TryGetValue("key", out var keyEl) ? keyEl.GetString() ?? "" : "";
                            var placed = PlaceSliderInternal(doc, sliderDict);
                            if (placed is string guid && !guid.StartsWith("ERROR:", StringComparison.Ordinal))
                                placedMap[sliderKey] = guid;
                            else
                                errors.Add($"{sliderKey}: {placed?.ToString() ?? "unknown error placing slider"}");
                        }
                        catch (Exception ex) { errors.Add(ex.Message); }
                    }
                }

                // Connect wires
                int wiredCount = 0;
                var wireErrors = new List<string>();
                if (p.TryGetValue("wires", out var wiresEl) && wiresEl.ValueKind == JsonValueKind.Array)
                {
                    foreach (var wireEl in wiresEl.EnumerateArray())
                    {
                        try
                        {
                            var wireDict = wireEl.EnumerateObject()
                                .ToDictionary(kv => kv.Name, kv => kv.Value);
                            int prevErrorCount = wireErrors.Count;
                            ConnectInternal(doc, wireDict, wireErrors, placedMap);
                            if (wireErrors.Count == prevErrorCount)
                                wiredCount++;
                        }
                        catch (Exception ex) { wireErrors.Add(ex.Message); }
                    }
                }

                errors.AddRange(wireErrors);
                result = new { ok = errors.Count == 0, placed = placedMap, wired = wiredCount, errors };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_place_component — place a component by GUID or name, return instance GUID.</summary>
    public static object PlaceComponent(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "PlaceComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                var placed = PlaceComponentInternal(doc, p);
                if (placed is string guid && !guid.StartsWith("ERROR:", StringComparison.Ordinal))
                    result = new { ok = true, instance_guid = guid };
                else
                    result = new { ok = false, error = placed?.ToString() ?? "Failed to place component" };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_place_slider — place a Number Slider with min/max/value/decimals.</summary>
    public static object PlaceSlider(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "PlaceSlider did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                var placed = PlaceSliderInternal(doc, p);
                if (placed is string guid && !guid.StartsWith("ERROR:", StringComparison.Ordinal))
                    result = new { ok = true, instance_guid = guid };
                else
                    result = new { ok = false, error = placed?.ToString() ?? "Failed to place slider" };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_connect — wire single output→input.</summary>
    public static object Connect(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "Connect did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                var errors = new List<string>();
                ConnectInternal(doc, p, errors);
                result = errors.Count == 0
                    ? (object)new { ok = true }
                    : new { ok = false, error = string.Join("; ", errors) };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_connect_many — batch wiring, collect errors per wire.</summary>
    public static object ConnectMany(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "ConnectMany did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                if (!p.TryGetValue("wires", out var wiresEl) || wiresEl.ValueKind != JsonValueKind.Array)
                {
                    result = new { ok = false, error = "wires array is required" };
                    return;
                }

                var errors    = new List<object>();
                int connected = 0;

                foreach (var wireEl in wiresEl.EnumerateArray())
                {
                    var wireErrors = new List<string>();
                    try
                    {
                        var wireDict = wireEl.EnumerateObject()
                            .ToDictionary(kv => kv.Name, kv => kv.Value);
                        ConnectInternal(doc, wireDict, wireErrors);
                        if (wireErrors.Count == 0)
                            connected++;
                        else
                            errors.Add(new { wire = wireEl.ToString(), errors = wireErrors });
                    }
                    catch (Exception ex)
                    {
                        errors.Add(new { wire = wireEl.ToString(), errors = new[] { ex.Message } });
                    }
                }

                result = new { ok = errors.Count == 0, connected, errors };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_describe_component — return metadata (inputs/outputs) for a component type.</summary>
    public static object DescribeComponent(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        var asm = GetGH2Assembly()!;
        object result = new { ok = false, error = "DescribeComponent did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                // Placed instance: describe the live object (name, nickname, current params)
                var instanceStr = p.String("instance_guid");
                if (!string.IsNullOrWhiteSpace(instanceStr))
                {
                    if (!Guid.TryParse(instanceStr, out var instanceGuid))
                    {
                        result = new { ok = false, error = $"Invalid instance_guid: {instanceStr}" };
                        return;
                    }
                    var doc = GetActiveGH2Doc();
                    if (doc == null)
                        throw new InvalidOperationException("No active GH2 document");
                    var obj = FindDocObject(doc, instanceGuid);
                    if (obj == null)
                    {
                        result = new { ok = false, error = $"Component {instanceGuid} not found on the active GH2 canvas" };
                        return;
                    }
                    var objType = obj.GetType();
                    result = new
                    {
                        ok            = true,
                        instance_guid = instanceGuid.ToString(),
                        name          = objType.GetProperty("Name")?.GetValue(obj)?.ToString() ?? "",
                        nick_name     = objType.GetProperty("NickName")?.GetValue(obj)?.ToString() ?? "",
                        type          = objType.Name,
                        description   = objType.GetProperty("Description")?.GetValue(obj)?.ToString() ?? "",
                        inputs        = DescribeParams(GetParams(obj, "Input")),
                        outputs       = DescribeParams(GetParams(obj, "Output"))
                    };
                    return;
                }

                // Try to find a component server or proxy for describing by GUID/name
                var guidStr = p.String("component_guid");
                var name    = p.String("name");

                // Look for a component proxy via a server-like type
                object? proxy = null;

                foreach (var serverTypeName in new[] { "Grasshopper2.GH_ComponentServer", "Grasshopper2.GH_Instances" })
                {
                    var serverType = asm.GetType(serverTypeName);
                    if (serverType == null) continue;

                    var serverProp = serverType.GetProperty("ComponentServer", BindingFlags.Static | BindingFlags.Public)
                                 ?? serverType.GetProperty("Server", BindingFlags.Static | BindingFlags.Public);
                    if (serverProp == null) continue;
                    var server = serverProp.GetValue(null);
                    if (server == null) continue;

                    if (guidStr != null && Guid.TryParse(guidStr, out var compGuid))
                    {
                        var findMethod = server.GetType().GetMethod("FindObject",
                            new[] { typeof(Guid), typeof(bool) })
                            ?? server.GetType().GetMethod("EmitObject", new[] { typeof(Guid) });
                        if (findMethod != null)
                        {
                            proxy = findMethod.Invoke(server, new object[] { compGuid, false });
                            if (proxy != null) break;
                        }
                    }
                }

                if (proxy == null)
                {
                    // Graceful: return what we know
                    result = new
                    {
                        ok   = true,
                        name = name ?? guidStr ?? "unknown",
                        note = "GH2 component description API not available in this build",
                        inputs  = Array.Empty<object>(),
                        outputs = Array.Empty<object>()
                    };
                    return;
                }

                // Describe from proxy
                var proxyType = proxy.GetType();
                var descProp  = proxyType.GetProperty("Desc") ?? proxyType.GetProperty("Description");
                var compName  = descProp?.GetValue(proxy)?.GetType()?.GetProperty("Name")?.GetValue(descProp.GetValue(proxy))?.ToString() ?? "";
                var compCat   = descProp?.GetValue(proxy)?.GetType()?.GetProperty("Category")?.GetValue(descProp.GetValue(proxy))?.ToString() ?? "";
                var compSub   = descProp?.GetValue(proxy)?.GetType()?.GetProperty("SubCategory")?.GetValue(descProp.GetValue(proxy))?.ToString() ?? "";
                var compDesc  = descProp?.GetValue(proxy)?.GetType()?.GetProperty("Description")?.GetValue(descProp.GetValue(proxy))?.ToString() ?? "";

                result = new
                {
                    ok          = true,
                    name        = compName,
                    category    = compCat,
                    subcategory = compSub,
                    description = compDesc,
                    inputs      = Array.Empty<object>(),
                    outputs     = Array.Empty<object>()
                };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_search_components — search GH2 component library by name or category.</summary>
    public static object SearchComponents(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        var asm   = GetGH2Assembly()!;
        var query = p.String("query") ?? "";
        var limit = p.Int("limit", 20);

        object result = new { ok = false, error = "SearchComponents did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var components = new List<object>();

                // Try to access a GH2 component server
                object? server = null;
                foreach (var typeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.GH_ComponentServer" })
                {
                    var t = asm.GetType(typeName);
                    if (t == null) continue;
                    foreach (var propName in new[] { "ComponentServer", "ObjectServer", "Server" })
                    {
                        var prop = t.GetProperty(propName, BindingFlags.Static | BindingFlags.Public);
                        if (prop != null) { server = prop.GetValue(null); break; }
                    }
                    if (server != null) break;
                }

                if (server == null)
                {
                    result = new
                    {
                        ok         = true,
                        components,
                        count      = 0,
                        note       = "GH2 component search API not available in this build"
                    };
                    return;
                }

                // Try ObjectProxies property
                var proxiesProp = server.GetType().GetProperty("ObjectProxies")
                               ?? server.GetType().GetProperty("Proxies");
                if (proxiesProp == null)
                {
                    result = new { ok = true, components, count = 0, note = "GH2 proxy enumeration not available in this build" };
                    return;
                }

                var proxies = proxiesProp.GetValue(server) as System.Collections.IEnumerable;
                if (proxies == null)
                {
                    result = new { ok = true, components, count = 0 };
                    return;
                }

                foreach (var proxy in proxies)
                {
                    if (components.Count >= limit) break;
                    var pType    = proxy.GetType();
                    var descProp = pType.GetProperty("Desc") ?? pType.GetProperty("Description");
                    var desc     = descProp?.GetValue(proxy);
                    if (desc == null) continue;

                    var dType   = desc.GetType();
                    var pName   = dType.GetProperty("Name")?.GetValue(desc)?.ToString() ?? "";
                    var pCat    = dType.GetProperty("Category")?.GetValue(desc)?.ToString() ?? "";
                    var pSub    = dType.GetProperty("SubCategory")?.GetValue(desc)?.ToString() ?? "";
                    var pDesc   = dType.GetProperty("Description")?.GetValue(desc)?.ToString() ?? "";
                    var guidObj = pType.GetProperty("Guid")?.GetValue(proxy);
                    var pGuid   = guidObj?.ToString() ?? "";

                    if (string.IsNullOrEmpty(query) ||
                        pName.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0 ||
                        pCat.IndexOf(query,  StringComparison.OrdinalIgnoreCase) >= 0 ||
                        pDesc.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        components.Add(new
                        {
                            name        = pName,
                            category    = pCat,
                            subcategory = pSub,
                            guid        = pGuid,
                            description = pDesc
                        });
                    }
                }

                result = new { ok = true, components, count = components.Count };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_solve_graph — expire and re-solve, return errors.</summary>
    public static object SolveGraph(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();

        object result = new { ok = false, error = "SolveGraph did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                // Try NewSolution or equivalent
                var docType = doc.GetType();
                var newSolutionMethod = docType.GetMethod("NewSolution", new[] { typeof(bool) })
                                     ?? docType.GetMethod("Solve")
                                     ?? docType.GetMethod("ExpireSolution");

                if (newSolutionMethod == null)
                {
                    result = new { ok = false, error = "GH2 solve API not available in this build" };
                    return;
                }

                try { newSolutionMethod.Invoke(doc, new object[] { false }); }
                catch { try { newSolutionMethod.Invoke(doc, Array.Empty<object>()); } catch { } }

                // Collect errors
                var errors = new List<string>();
                var objectsProp = docType.GetProperty("Objects");
                if (objectsProp != null)
                {
                    var objs = objectsProp.GetValue(doc) as System.Collections.IEnumerable;
                    if (objs != null)
                    {
                        foreach (var obj in objs)
                        {
                            var objType   = obj.GetType();
                            var levelProp = objType.GetProperty("RuntimeMessageLevel");
                            if (levelProp == null) continue;
                            var level = levelProp.GetValue(obj);
                            if (level?.ToString()?.Contains("Error") == true)
                            {
                                var nameProp = objType.GetProperty("Name");
                                var name     = nameProp?.GetValue(obj)?.ToString() ?? "unknown";

                                // Try to get actual error message text via reflection
                                bool addedMessages = false;
                                try
                                {
                                    var messages = objType.GetProperty("RuntimeMessages")?.GetValue(obj)
                                                ?? objType.GetProperty("Messages")?.GetValue(obj);
                                    if (messages is System.Collections.IEnumerable msgList)
                                    {
                                        foreach (var msg in msgList)
                                        {
                                            var msgText = msg?.GetType().GetProperty("Message")?.GetValue(msg)?.ToString()
                                                       ?? msg?.ToString();
                                            if (!string.IsNullOrEmpty(msgText))
                                            {
                                                errors.Add($"{name}: {msgText}");
                                                addedMessages = true;
                                            }
                                        }
                                    }
                                }
                                catch { /* reflection failed — fall through to generic message */ }

                                if (!addedMessages)
                                    errors.Add($"Component '{name}' has runtime errors");
                            }
                        }
                    }
                }

                result = new { ok = true, error_count = errors.Count, errors };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    /// <summary>gh2_clear_canvas — removes all objects from the active GH2 document. Requires confirm:true.</summary>
    public static object ClearCanvas(Dictionary<string, JsonElement> p)
    {
        if (!Gh2Available()) return NotAvailable();
        if (!p.Bool("confirm"))
            return new { ok = false, error = "confirm:true is required to clear the canvas" };

        object result = new { ok = false, error = "ClearCanvas did not complete" };
        RhinoApp.InvokeOnUiThread(new Action(() =>
        {
            try
            {
                var doc = GetActiveGH2Doc();
                if (doc == null)
                    throw new InvalidOperationException("No active GH2 document");

                var docType = doc.GetType();

                // Try Clear method first
                var clearMethod = docType.GetMethod("Clear") ?? docType.GetMethod("ClearAll");
                if (clearMethod != null)
                {
                    clearMethod.Invoke(doc, Array.Empty<object>());
                    result = new { ok = true };
                    return;
                }

                // Fallback: remove objects one by one
                var objectsProp = docType.GetProperty("Objects");
                if (objectsProp == null)
                {
                    result = new { ok = false, error = "GH2 canvas clear API not available in this build" };
                    return;
                }

                var objs = (objectsProp.GetValue(doc) as System.Collections.IEnumerable)
                    ?.Cast<object>().ToList() ?? new List<object>();
                var removeMethod = docType.GetMethod("RemoveObject",
                    new[] { typeof(object), typeof(bool) })
                    ?? docType.GetMethod("RemoveObject");

                if (removeMethod == null)
                {
                    result = new { ok = false, error = "GH2 remove object API not available in this build" };
                    return;
                }

                foreach (var obj in objs)
                {
                    try { removeMethod.Invoke(doc, new object[] { obj, false }); }
                    catch { /* skip */ }
                }

                result = new { ok = true, removed = objs.Count };
            }
            catch (Exception ex)
            {
                result = new { ok = false, error = ex.Message };
            }
        }));
        return result;
    }

    // -----------------------------------------------------------------------
    // Internal shared helpers
    // -----------------------------------------------------------------------

    /// <summary>
    /// Places a single component in the GH2 doc. Returns instance GUID string on success,
    /// or an error string prefixed with "ERROR:" on failure.
    /// </summary>
    private static object PlaceComponentInternal(object doc, IDictionary<string, JsonElement> cp)
    {
        try
        {
            var asm = GetGH2Assembly()!;
            var x   = cp.TryGetValue("x", out var xEl) && xEl.TryGetDouble(out var xd) ? (float)xd : 0f;
            var y   = cp.TryGetValue("y", out var yEl) && yEl.TryGetDouble(out var yd) ? (float)yd : 0f;

            var guidStr = cp.TryGetValue("component_guid", out var cgEl) ? cgEl.GetString() : null;
            var name    = cp.TryGetValue("name",           out var cnEl) ? cnEl.GetString() : null;
            if (string.IsNullOrEmpty(name) && cp.TryGetValue("type_name", out var tnEl))
                name = tnEl.GetString();

            object? compObj = null;

            // If no GUID but a name was supplied, resolve the GUID via proxy search
            if (string.IsNullOrEmpty(guidStr) && !string.IsNullOrEmpty(name))
            {
                object? resolvedServer = null;
                foreach (var serverTypeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.GH_ComponentServer" })
                {
                    var serverType = asm.GetType(serverTypeName);
                    if (serverType == null) continue;
                    foreach (var propName in new[] { "ComponentServer", "ObjectServer", "Server" })
                    {
                        var prop = serverType.GetProperty(propName, BindingFlags.Static | BindingFlags.Public);
                        if (prop == null) continue;
                        resolvedServer = prop.GetValue(null);
                        if (resolvedServer != null) break;
                    }
                    if (resolvedServer != null) break;
                }

                if (resolvedServer != null)
                {
                    var proxiesProp = resolvedServer.GetType().GetProperty("ObjectProxies")
                                  ?? resolvedServer.GetType().GetProperty("Proxies");
                    var proxies = proxiesProp?.GetValue(resolvedServer) as System.Collections.IEnumerable;
                    if (proxies != null)
                    {
                        var exactMatches  = new List<(string guid, string pName)>();
                        var prefixMatches = new List<(string guid, string pName)>();
                        foreach (var proxy in proxies)
                        {
                            var pType    = proxy.GetType();
                            var descProp = pType.GetProperty("Desc") ?? pType.GetProperty("Description");
                            var desc     = descProp?.GetValue(proxy);
                            if (desc == null) continue;
                            var pName  = desc.GetType().GetProperty("Name")?.GetValue(desc)?.ToString() ?? "";
                            var guidObj = pType.GetProperty("Guid")?.GetValue(proxy);
                            var pGuid  = guidObj?.ToString() ?? "";
                            if (string.IsNullOrEmpty(pGuid)) continue;

                            if (string.Equals(pName, name, StringComparison.OrdinalIgnoreCase))
                                exactMatches.Add((pGuid, pName));
                            else if (pName.StartsWith(name, StringComparison.OrdinalIgnoreCase))
                                prefixMatches.Add((pGuid, pName));
                        }

                        var matches = exactMatches.Count > 0 ? exactMatches : prefixMatches;
                        if (matches.Count == 0)
                            return $"ERROR: Component '{name}' not found.";
                        if (matches.Count > 1)
                            return $"ERROR: Ambiguous component name '{name}': {matches.Count} matches found. Provide component_guid instead.";
                        guidStr = matches[0].guid;
                    }
                }
            }

            // Try to find a GH2 component server and emit the object
            foreach (var serverTypeName in new[] { "Grasshopper2.GH_Instances", "Grasshopper2.GH_ComponentServer" })
            {
                var serverType = asm.GetType(serverTypeName);
                if (serverType == null) continue;
                foreach (var propName in new[] { "ComponentServer", "ObjectServer", "Server" })
                {
                    var prop = serverType.GetProperty(propName, BindingFlags.Static | BindingFlags.Public);
                    if (prop == null) continue;
                    var server = prop.GetValue(null);
                    if (server == null) continue;

                    if (guidStr != null && Guid.TryParse(guidStr, out var cGuid))
                    {
                        var emitMethod = server.GetType().GetMethod("EmitObject", new[] { typeof(Guid) });
                        if (emitMethod != null)
                        {
                            compObj = emitMethod.Invoke(server, new object[] { cGuid });
                            if (compObj != null) break;
                        }
                    }
                    if (compObj == null) break;
                }
                if (compObj != null) break;
            }

            if (compObj == null)
            {
                if (string.IsNullOrEmpty(guidStr))
                    return name != null
                        ? $"ERROR: Component '{name}' not found."
                        : "ERROR: component_guid or name is required";
                return "ERROR: GH2 component placement API not available in this build";
            }

            // CreateAttributes and set position
            var compType = compObj.GetType();
            compType.GetMethod("CreateAttributes")?.Invoke(compObj, Array.Empty<object>());

            var attrs = compType.GetProperty("Attributes")?.GetValue(compObj);
            if (attrs != null)
            {
                var pivotProp = attrs.GetType().GetProperty("Pivot");
                if (pivotProp != null)
                {
                    // PointF is a value type; construct it
                    var pf = new PointF(x, y);
                    pivotProp.SetValue(attrs, pf);
                }
            }

            // AddObject to doc
            var addMethod = doc.GetType().GetMethod("AddObject",
                new[] { compType.GetInterfaces().FirstOrDefault() ?? compType, typeof(bool) })
                ?? doc.GetType().GetMethod("AddObject");
            if (addMethod != null)
            {
                try { addMethod.Invoke(doc, new object[] { compObj, false }); }
                catch { try { addMethod.Invoke(doc, new object[] { compObj }); } catch { } }
            }

            var instanceGuid = compType.GetProperty("InstanceGuid")?.GetValue(compObj)?.ToString();
            if (instanceGuid == null || !Guid.TryParse(instanceGuid, out var placedGuid) || FindDocObject(doc, placedGuid) == null)
                return "ERROR: GH2 doc.AddObject did not add the component";
            return instanceGuid;
        }
        catch (Exception ex)
        {
            return $"ERROR: {ex.Message}";
        }
    }

    /// <summary>
    /// Places a slider in the GH2 doc. Returns instance GUID string on success,
    /// or an error string prefixed with "ERROR:" on failure.
    /// </summary>
    private static object PlaceSliderInternal(object doc, IDictionary<string, JsonElement> sp)
    {
        try
        {
            var asm = GetGH2Assembly()!;
            var x       = sp.TryGetValue("x",        out var xEl)  && xEl.TryGetDouble(out var xd)  ? (float)xd  : 0f;
            var y       = sp.TryGetValue("y",        out var yEl)  && yEl.TryGetDouble(out var yd)  ? (float)yd  : 0f;
            var min     = sp.TryGetValue("min",      out var mnEl) && mnEl.TryGetDouble(out var mn) ? mn : 0.0;
            var max     = sp.TryGetValue("max",      out var mxEl) && mxEl.TryGetDouble(out var mx) ? mx : 1.0;
            var val     = sp.TryGetValue("value",    out var vEl)  && vEl.TryGetDouble(out var v)   ? v  : 0.0;
            var decimals = sp.TryGetValue("decimals", out var dEl)  && dEl.TryGetInt32(out var di)   ? di : 2;
            var nickName = sp.TryGetValue("nick_name", out var nnEl) ? nnEl.GetString() ?? "Slider" : "Slider";

            // Try to find a GH2 slider type
            object? slider = null;
            foreach (var sliderTypeName in new[]
            {
                "Grasshopper2.Kernel.Special.GH_NumberSlider",
                "Grasshopper2.Special.GH_NumberSlider",
                "Grasshopper2.GH_NumberSlider"
            })
            {
                var sliderType = asm.GetType(sliderTypeName);
                if (sliderType == null) continue;
                slider = Activator.CreateInstance(sliderType);
                if (slider != null) break;
            }

            if (slider == null)
                return "ERROR: GH2 slider type not available in this build";

            var sliderType2 = slider.GetType();
            sliderType2.GetMethod("CreateAttributes")?.Invoke(slider, Array.Empty<object>());

            // Set slider properties via reflection
            foreach (var (propPath, value) in new (string, object)[]
            {
                ("NickName", nickName),
                ("Slider.Minimum", min),
                ("Slider.Maximum", max),
                ("Slider.Value",   val),
                ("Slider.DecimalPlaces", decimals)
            })
            {
                try
                {
                    if (propPath.Contains('.'))
                    {
                        var parts  = propPath.Split('.');
                        var parent = sliderType2.GetProperty(parts[0])?.GetValue(slider);
                        if (parent != null)
                            parent.GetType().GetProperty(parts[1])?.SetValue(parent, Convert.ChangeType(value, parent.GetType().GetProperty(parts[1])!.PropertyType));
                    }
                    else
                    {
                        sliderType2.GetProperty(propPath)?.SetValue(slider, value);
                    }
                }
                catch { /* skip unsupported property */ }
            }

            // Position
            var attrs = sliderType2.GetProperty("Attributes")?.GetValue(slider);
            if (attrs != null)
            {
                var pivotProp = attrs.GetType().GetProperty("Pivot");
                if (pivotProp != null)
                    pivotProp.SetValue(attrs, new PointF(x, y));
            }

            // AddObject to doc
            var addMethod = doc.GetType().GetMethod("AddObject");
            if (addMethod != null)
            {
                try { addMethod.Invoke(doc, new object[] { slider, false }); }
                catch { try { addMethod.Invoke(doc, new object[] { slider }); } catch { } }
            }

            var instanceGuid = sliderType2.GetProperty("InstanceGuid")?.GetValue(slider)?.ToString();
            if (instanceGuid == null || !Guid.TryParse(instanceGuid, out var placedGuid) || FindDocObject(doc, placedGuid) == null)
                return "ERROR: GH2 doc.AddObject did not add the slider";
            return instanceGuid;
        }
        catch (Exception ex)
        {
            return $"ERROR: {ex.Message}";
        }
    }

    /// <summary>Finds a placed object in the GH2 doc by instance GUID via FindObject, or null.</summary>
    private static object? FindDocObject(object doc, Guid guid)
    {
        var docType = doc.GetType();
        var findMethod = docType.GetMethod("FindObject", new[] { typeof(Guid), typeof(bool) })
                      ?? docType.GetMethod("FindObject", new[] { typeof(Guid) });
        if (findMethod == null)
            throw new InvalidOperationException("GH2 FindObject API not available in this build");
        return findMethod.GetParameters().Length == 2
            ? findMethod.Invoke(doc, new object[] { guid, false })
            : findMethod.Invoke(doc, new object[] { guid });
    }

    /// <summary>Returns obj.Params.{Input|Output} as a list, or an empty list.</summary>
    private static List<object> GetParams(object obj, string side)
    {
        var paramsObj = obj.GetType().GetProperty("Params")?.GetValue(obj);
        var list = paramsObj?.GetType().GetProperty(side)?.GetValue(paramsObj) as System.Collections.IEnumerable;
        return list?.Cast<object>().ToList() ?? new List<object>();
    }

    private static List<object> DescribeParams(List<object> parameters) =>
        parameters.Select((prm, i) =>
        {
            var t = prm.GetType();
            return (object)new
            {
                index     = i,
                name      = t.GetProperty("Name")?.GetValue(prm)?.ToString() ?? "",
                nick_name = t.GetProperty("NickName")?.GetValue(prm)?.ToString() ?? "",
                type      = t.GetProperty("TypeName")?.GetValue(prm)?.ToString() ?? t.Name
            };
        }).ToList();

    /// <summary>
    /// Resolves a wire endpoint to a GUID string: {prefix}_guid, {prefix}_instance, or
    /// {prefix}_key looked up in placedMap. Returns null (with an error) when unresolvable.
    /// </summary>
    private static string? ResolveEndpointGuid(IDictionary<string, JsonElement> wp, string prefix,
        IReadOnlyDictionary<string, string>? placedMap, List<string> errors)
    {
        foreach (var suffix in new[] { "_guid", "_instance" })
        {
            if (wp.TryGetValue(prefix + suffix, out var el) && el.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(el.GetString()))
                return el.GetString();
        }
        if (wp.TryGetValue(prefix + "_key", out var keyEl) && keyEl.ValueKind == JsonValueKind.String)
        {
            var key = keyEl.GetString() ?? "";
            if (placedMap != null && placedMap.TryGetValue(key, out var guid))
                return guid;
            errors.Add(placedMap == null
                ? $"{prefix}_key is only valid inside gh2_apply_graph; use {prefix}_guid"
                : $"{prefix}_key '{key}' was not placed in this call");
            return null;
        }
        errors.Add($"{prefix}_guid is required");
        return null;
    }

    /// <summary>
    /// Resolves a port reference (JSON number = 0-based index, string = nickname, or a
    /// numeric string = index) against a param list. Returns null if not found.
    /// </summary>
    private static object? ResolvePort(List<object> parameters, JsonElement portEl, out string label)
    {
        label = portEl.ToString();
        if (portEl.ValueKind == JsonValueKind.Number && portEl.TryGetInt32(out var idx))
            return idx >= 0 && idx < parameters.Count ? parameters[idx] : null;
        if (portEl.ValueKind != JsonValueKind.String) return null;

        var text = portEl.GetString() ?? "";
        label = text;
        var byName = parameters.FirstOrDefault(prm =>
            string.Equals(prm.GetType().GetProperty("NickName")?.GetValue(prm)?.ToString(), text, StringComparison.OrdinalIgnoreCase)
            || string.Equals(prm.GetType().GetProperty("Name")?.GetValue(prm)?.ToString(), text, StringComparison.OrdinalIgnoreCase));
        if (byName != null) return byName;
        if (int.TryParse(text, out var strIdx) && strIdx >= 0 && strIdx < parameters.Count)
            return parameters[strIdx];
        return null;
    }

    /// <summary>
    /// Wires output→input in the GH2 doc. Appends error messages to errors list.
    /// Endpoints: from_guid|from_instance|from_key and to_guid|to_instance|to_key
    /// (keys resolve against placedMap). Ports: nickname string or 0-based index.
    /// </summary>
    private static void ConnectInternal(object doc, IDictionary<string, JsonElement> wp, List<string> errors,
        IReadOnlyDictionary<string, string>? placedMap = null)
    {
        var fromGuidStr = ResolveEndpointGuid(wp, "from", placedMap, errors);
        if (fromGuidStr == null) return;
        var toGuidStr = ResolveEndpointGuid(wp, "to", placedMap, errors);
        if (toGuidStr == null) return;

        if (!wp.TryGetValue("from_output", out var fromOutputEl) || fromOutputEl.ValueKind == JsonValueKind.Null)
        { errors.Add("from_output is required"); return; }
        if (!wp.TryGetValue("to_input", out var toInputEl) || toInputEl.ValueKind == JsonValueKind.Null)
        { errors.Add("to_input is required"); return; }

        if (!Guid.TryParse(fromGuidStr, out var fromGuid)) { errors.Add($"Invalid from_guid: {fromGuidStr}"); return; }
        if (!Guid.TryParse(toGuidStr,   out var toGuid))   { errors.Add($"Invalid to_guid: {toGuidStr}");    return; }

        object? fromObj, toObj;
        try
        {
            fromObj = FindDocObject(doc, fromGuid);
            toObj   = FindDocObject(doc, toGuid);
        }
        catch (Exception ex)
        {
            errors.Add(ex.Message);
            return;
        }

        if (fromObj == null) { errors.Add($"Source component {fromGuid} not found"); return; }
        if (toObj   == null) { errors.Add($"Target component {toGuid} not found");   return; }

        try
        {
            var outParam = ResolvePort(GetParams(fromObj, "Output"), fromOutputEl, out var outLabel);
            if (outParam == null) { errors.Add($"Output '{outLabel}' not found on {fromGuid}"); return; }

            var inParam = ResolvePort(GetParams(toObj, "Input"), toInputEl, out var inLabel);
            if (inParam == null) { errors.Add($"Input '{inLabel}' not found on {toGuid}"); return; }

            // Connect: inParam.AddSource(outParam)
            var addSourceMethod = inParam.GetType().GetMethod("AddSource");
            if (addSourceMethod == null) { errors.Add("GH2 AddSource API not available in this build"); return; }
            addSourceMethod.Invoke(inParam, new object[] { outParam });

            // Expire solution
            inParam.GetType().GetMethod("ExpireSolution", new[] { typeof(bool) })
                ?.Invoke(inParam, new object[] { false });
        }
        catch (Exception ex)
        {
            errors.Add(ex.Message);
        }
    }
}

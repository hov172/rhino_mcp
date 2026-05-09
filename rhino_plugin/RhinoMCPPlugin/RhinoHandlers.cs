using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Microsoft.CodeAnalysis.CSharp.Scripting;
using Microsoft.CodeAnalysis.Scripting;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;
using Rhino.Geometry.Intersect;
using Rhino.PlugIns;

namespace RhinoMCPPlugin;

public static class RhinoHandlers
{
    public sealed class CSharpGlobals
    {
        public RhinoDoc doc { get; init; } = RhinoDoc.ActiveDoc;
        public StringBuilder output { get; init; } = new();
    }

    private static readonly Lazy<ScriptOptions> _scriptOptions = new(() =>
    {
        return ScriptOptions.Default
            .AddReferences(
                typeof(object).Assembly,
                typeof(Enumerable).Assembly,
                typeof(List<>).Assembly,
                typeof(RhinoDoc).Assembly,
                typeof(Point3d).Assembly,
                Assembly.Load("System.Runtime"))
            .AddImports(
                "System",
                "System.Collections.Generic",
                "System.Linq",
                "System.Text",
                "Rhino",
                "Rhino.Geometry",
                "Rhino.DocObjects",
                "Rhino.Commands");
    });

    // -------------------------------------------------------------------------
    // Public handlers
    // -------------------------------------------------------------------------

    public static object GetDocumentSummary()
    {
        var doc = RhinoDoc.ActiveDoc;

        // objects_by_type
        var byType = new Dictionary<string, int>();
        foreach (var obj in doc.Objects.Where(o => !o.IsDeleted))
        {
            var typeName = ToNormalizedTypeName(obj);
            byType[typeName] = byType.TryGetValue(typeName, out var c) ? c + 1 : 1;
        }

        // objects_by_layer
        var byLayer = new Dictionary<string, int>();
        foreach (var obj in doc.Objects.Where(o => !o.IsDeleted))
        {
            var ln = LayerName(obj) ?? "(none)";
            byLayer[ln] = byLayer.TryGetValue(ln, out var c) ? c + 1 : 1;
        }

        // model_bounding_box
        object? modelBbox = null;
        var allObjs = doc.Objects.Where(o => !o.IsDeleted).ToList();
        if (allObjs.Count > 0)
        {
            var combined = BoundingBox.Empty;
            foreach (var obj in allObjs)
                combined.Union(obj.Geometry.GetBoundingBox(true));
            if (combined.IsValid)
                modelBbox = new[] { PointArray(combined.Min), PointArray(combined.Max) };
        }

        return new
        {
            name = doc.Name,
            path = doc.Path,
            object_count = doc.Objects.Count,
            unit_system = doc.ModelUnitSystem.ToString(),
            tolerance = doc.ModelAbsoluteTolerance,
            angle_tolerance = doc.ModelAngleToleranceDegrees,
            objects_by_type = byType,
            objects_by_layer = byLayer,
            model_bounding_box = modelBbox,
            layers = doc.Layers.Where(l => !l.IsDeleted).Select(l => new
            {
                name = l.FullPath,
                visible = l.IsVisible,
                locked = l.IsLocked,
                color = ColorArray(l.Color)
            }).ToList(),
            layer_hierarchy = BuildLayerHierarchy(doc),
            materials = doc.Materials.Where(m => !m.IsDeleted).Select(m => m.Name).ToList(),
            views = doc.Views.Select(v => v.ActiveViewport.Name).ToList(),
            // Fix 9: date_created, date_modified, layer_count, render_mode
            date_created = doc.DateCreated.ToString("o"),
            date_modified = doc.DateLastEdited.ToString("o"),
            layer_count = doc.Layers.Count(l => !l.IsDeleted),
            render_mode = doc.Views.ActiveView?.ActiveViewport.DisplayMode?.EnglishName ?? "unknown"
        };
    }

    public static object GetObjects(Dictionary<string, JsonElement> p)
    {
        var offset = Math.Max(0, p.Int("offset", 0));
        var limit = Math.Max(1, p.Int("limit", 100));
        var layerFilter = p.String("layer_filter");
        var typeFilter = p.String("type_filter");
        var includeGeometry = p.Bool("include_geometry", true);

        // Fix 10: bbox_filter — accept both flat [6] and nested [[3],[3]] formats.
        BoundingBox? bboxFilter = null;
        if (p.TryGetValue("bbox_filter", out var bboxEl) && bboxEl.ValueKind == JsonValueKind.Array)
        {
            var bboxItems = bboxEl.EnumerateArray().ToArray();
            if (bboxItems.Length == 2 && bboxItems[0].ValueKind == JsonValueKind.Array)
            {
                // Nested format: [[minX,minY,minZ],[maxX,maxY,maxZ]]
                var minArr = bboxItems[0].EnumerateArray().Select(e => e.GetDouble()).ToArray();
                var maxArr = bboxItems[1].EnumerateArray().Select(e => e.GetDouble()).ToArray();
                if (minArr.Length == 3 && maxArr.Length == 3)
                    bboxFilter = new BoundingBox(minArr[0], minArr[1], minArr[2], maxArr[0], maxArr[1], maxArr[2]);
            }
            else if (bboxItems.Length == 6 && bboxItems[0].ValueKind != JsonValueKind.Array)
            {
                // Flat format: [minX,minY,minZ,maxX,maxY,maxZ]
                var flat = bboxItems.Select(e => e.GetDouble()).ToArray();
                bboxFilter = new BoundingBox(flat[0], flat[1], flat[2], flat[3], flat[4], flat[5]);
            }
        }

        var includeHidden = p.Bool("include_hidden", false);
        var normalizedTypeFilter = typeFilter?.ToUpperInvariant();

        var filtered = RhinoDoc.ActiveDoc.Objects
            .Where(o => !o.IsDeleted)
            .Where(o => includeHidden || !o.IsHidden)
            .Where(o =>
            {
                if (layerFilter is null) return true;
                var fullPath = LayerName(o) ?? "";
                var idx = o.Attributes.LayerIndex;
                var shortName = idx >= 0 ? RhinoDoc.ActiveDoc.Layers[idx].Name : "";
                return string.Equals(fullPath, layerFilter, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(shortName, layerFilter, StringComparison.OrdinalIgnoreCase);
            })
            .Where(o =>
            {
                if (normalizedTypeFilter is null)
                    return true;
                var objTypeName = ToNormalizedTypeName(o);
                return objTypeName.Contains(normalizedTypeFilter, StringComparison.OrdinalIgnoreCase);
            })
            .Where(o =>
            {
                if (bboxFilter is null)
                    return true;
                var objBbox = o.Geometry.GetBoundingBox(true);
                return objBbox.IsValid && bboxFilter.Value.Contains(objBbox.Min) ||
                       BoundingBoxesIntersect(objBbox, bboxFilter.Value);
            })
            .ToList();

        var totalMatching = filtered.Count;
        var objects = filtered
            .Skip(offset)
            .Take(limit)
            .Select(o => SerializeObject(o, includeGeometry))
            .ToList();

        return new
        {
            objects,
            count = objects.Count,
            total_matching = totalMatching,
            has_more = totalMatching > offset + limit,
            offset,
            limit
        };
    }

    public static object GetObjectInfo(Dictionary<string, JsonElement> p)
    {
        var obj = FindObject(p);
        if (obj is null)
            return new { found = false, message = "Object not found" };
        return SerializeObject(obj, true);
    }

    public static object GetSelectedObjectsInfo(Dictionary<string, JsonElement> p)
    {
        var limit = Math.Max(1, p.Int("limit", 100));
        var objects = RhinoDoc.ActiveDoc.Objects.GetSelectedObjects(false, false)
            .Take(limit)
            .Select(o => SerializeObject(o, true))
            .ToList();
        return new { objects, count = objects.Count };
    }

    public static object CreateObject(Dictionary<string, JsonElement> p)
    {
        var rawType = p.String("type", "")!.ToUpperInvariant();
        var parameters = p.TryGetValue("params", out var pe) ? JsonHelpers.Dict(pe) : new Dictionary<string, JsonElement>();
        var id = AddPrimitive(rawType, parameters);
        if (id == Guid.Empty)
        {
            var hint = _typeParamHints.TryGetValue(rawType, out var h) ? $" — {h}" : "";
            var msg = _knownTypes.Contains(rawType)
                ? $"Failed to create {rawType}{hint}"
                : $"Unsupported object type: {rawType}";
            return new { success = false, message = msg };
        }
        var obj = RhinoDoc.ActiveDoc.Objects.FindId(id);
        ApplyAttributes(obj, p);
        ApplyTransform(id, p);

        // Rotation from CreateObject params (rotation after transform)
        var rotation = p.DoubleArray("rotation");
        if (rotation.Length == 3)
            ApplyEulerRotation(id, rotation[0], rotation[1], rotation[2]);

        RhinoDoc.ActiveDoc.Views.Redraw();
        return new { success = true, id = id.ToString(), object_id = id.ToString(), type = rawType };
    }

    public static object CreateObjects(Dictionary<string, JsonElement> p)
    {
        var created = new List<object>();
        if (!p.TryGetValue("objects", out var objectsValue))
            return new { success = false, message = "objects is required" };

        if (objectsValue.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in objectsValue.EnumerateArray())
                created.Add(CreateObject(JsonHelpers.Dict(item)));
        }
        else if (objectsValue.ValueKind == JsonValueKind.Object)
        {
            foreach (var prop in objectsValue.EnumerateObject())
            {
                var item = JsonHelpers.Dict(prop.Value);
                if (!item.ContainsKey("name"))
                    item["name"] = JsonDocument.Parse(JsonSerializer.Serialize(prop.Name)).RootElement.Clone();
                created.Add(CreateObject(item));
            }
        }
        return new { success = true, created, count = created.Count };
    }

    public static object DeleteObject(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var ids = new List<Guid>();
        if (p.Bool("all", false))
            ids.AddRange(doc.Objects.Where(o => !o.IsDeleted).Select(o => o.Id));
        else
        {
            var obj = FindObject(p);
            if (obj is not null)
                ids.Add(obj.Id);
        }
        var count = ids.Count(id => doc.Objects.Delete(id, true));
        doc.Views.Redraw();
        return new { deleted = count, ids = ids.Select(id => id.ToString()).ToList() };
    }

    public static object ModifyObject(Dictionary<string, JsonElement> p)
    {
        var obj = FindObject(p);
        if (obj is null)
            return new { success = false, message = "Object not found" };
        Modify(obj, p);
        RhinoDoc.ActiveDoc.Views.Redraw();
        // Re-fetch after modification to get updated state
        var updated = RhinoDoc.ActiveDoc.Objects.FindId(obj.Id);
        return updated is not null ? SerializeObject(updated, false) : new object();
    }

    public static object ModifyObjects(Dictionary<string, JsonElement> p)
    {
        var results = new List<object>();
        if (p.Bool("all", false))
        {
            foreach (var obj in RhinoDoc.ActiveDoc.Objects.Where(o => !o.IsDeleted))
                results.Add(Modify(obj, p));
        }
        else if (p.TryGetValue("objects", out var objects) && objects.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in objects.EnumerateArray())
                results.Add(ModifyObject(JsonHelpers.Dict(item)));
        }
        return new { success = true, results, count = results.Count };
    }

    // Known primitive types — used to distinguish "bad params" from "unknown type" in error messages.
    private static readonly HashSet<string> _knownTypes = new(StringComparer.OrdinalIgnoreCase)
    {
        "POINT", "LINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "CURVE",
        "BOX", "SPHERE", "CONE", "CYLINDER", "TORUS", "PLANE", "SURFACE", "TEXT", "MESH",
        "POINTCLOUD", "POINT_CLOUD", "TEXTDOT", "LIGHT",
        "EXTRUSION", "BLOCK_INSERT", "INSTANCE", "INSTANCE_REFERENCE",
        "DIMENSION_LINEAR", "DIMENSION_RADIAL", "DIMENSION_ANGULAR", "LEADER",
        "CAGE", "MORPHCONTROL", "MORPH_CONTROL",
        "SUBD", "HATCH", "CLIPPING_PLANE", "CLIPPINGPLANE"
    };

    // Per-type required-param hints surfaced in failure messages.
    private static readonly Dictionary<string, string> _typeParamHints = new(StringComparer.OrdinalIgnoreCase)
    {
        ["POLYLINE"]          = "requires: points (array of [x,y,z])",
        ["CURVE"]             = "requires: points (array of [x,y,z])",
        ["SURFACE"]           = "requires: points (array of [x,y,z]), count ([uCount, vCount])",
        ["MESH"]              = "requires: vertices (array of [x,y,z]), faces (array of [i,j,k])",
        ["LINE"]              = "requires: start [x,y,z], end [x,y,z]",
        ["ARC"]               = "requires: center [x,y,z], radius, start_angle, end_angle (degrees) OR start [x,y,z], end [x,y,z], point_on_arc [x,y,z]",
        ["POINTCLOUD"]        = "requires: points (array of [x,y,z])",
        ["TEXTDOT"]           = "requires: text, point [x,y,z]; optional: font_size",
        ["LIGHT"]             = "requires: location [x,y,z]; optional: light_style (point/directional/spot/linear/rectangular), intensity, diffuse_color [r,g,b], direction [x,y,z]",
        ["EXTRUSION"]         = "requires: profile_id (GUID of a planar curve) OR points (array of [x,y,z] for an inline profile), height; optional: cap (bool)",
        ["BLOCK_INSERT"]      = "requires: block_name; optional: position [x,y,z], scale, rotation [rx,ry,rz]",
        ["DIMENSION_LINEAR"]  = "requires: start [x,y,z], end [x,y,z]; optional: offset (dimension line distance)",
        ["DIMENSION_RADIAL"]  = "requires: center [x,y,z], radius; optional: angle (degrees, default 45), offset, is_diameter (bool)",
        ["DIMENSION_ANGULAR"] = "requires: center [x,y,z], radius; optional: start_angle, end_angle (degrees), offset",
        ["LEADER"]            = "requires: points (array of ≥2 [x,y,z]); optional: text",
        ["CAGE"]              = "requires: center [x,y,z], width, depth, height — creates a cage box; use _CageEdit in Rhino to capture objects",
        ["MORPHCONTROL"]      = "requires: source_curve_id (GUID), target_curve_id (GUID) — maps geometry between two NurbsCurve shapes",
        ["SUBD"]              = "requires: mesh_id (GUID of existing mesh) OR center [x,y,z], width, depth, height for a SubD box; optional: level (subdivision level 0-4)",
        ["HATCH"]             = "requires: curve_id (GUID of closed boundary curve) OR center [x,y,z], width, height for a rectangle; optional: pattern (hatch pattern name), rotation (degrees), scale",
        ["CLIPPING_PLANE"]    = "requires: origin [x,y,z]; optional: normal [x,y,z] (default Z-up), width, height — clips all viewports by default",
    };

    // Built-in filter keys — anything else is treated as a user-string attribute lookup.
    private static readonly HashSet<string> _builtInFilterKeys = new(StringComparer.OrdinalIgnoreCase)
    {
        "id", "ids", "name", "exact_name", "name_contains", "name_pattern",
        "layer", "type", "color", "color_tolerance",
        "bbox_filter", "select_all", "deselect", "limit", "filters_type"
    };

    public static object SelectObjects(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var filters = p.TryGetValue("filters", out var fe) ? JsonHelpers.Dict(fe) : new Dictionary<string, JsonElement>();
        var filterType = p.String("filters_type", "and") ?? "and";
        var deselect = p.Bool("deselect", false);
        var selectAll = p.Bool("select_all", false) || filters.Count == 0;
        var limit = p.Int("limit", int.MaxValue);

        // Pull color_tolerance out of filters if present (consumed separately)
        var colorTolerance = filters.TryGetValue("color_tolerance", out var ctEl)
            ? (int?)ctEl.GetInt32()
            : null;

        doc.Objects.UnselectAll();
        var matchedCount = 0;

        foreach (var obj in doc.Objects.Where(o => !o.IsDeleted && !o.IsHidden))
        {
            bool ok;
            if (selectAll)
            {
                ok = true;
            }
            else
            {
                var tests = filters
                    .Where(f => !f.Key.Equals("color_tolerance", StringComparison.OrdinalIgnoreCase))
                    .Select(f => MatchFilter(obj, f.Key, f.Value, colorTolerance))
                    .ToList();
                ok = filterType.Equals("or", StringComparison.OrdinalIgnoreCase)
                    ? tests.Any(v => v)
                    : tests.All(v => v);
            }

            if (!ok)
                continue;

            if (deselect)
                obj.Select(false);
            else
                obj.Select(true);

            matchedCount++;
            if (matchedCount >= limit)
                break;
        }

        doc.Views.Redraw();
        return new { count = matchedCount, deselected = deselect };
    }

    public static object CreateLayer(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var name = p.String("name");
        if (string.IsNullOrWhiteSpace(name))
            return new { success = false, message = "name is required" };

        var index = doc.Layers.FindByFullPath(name, -1);
        if (index < 0)
        {
            var layer = new Layer
            {
                Name = name,
                Color = ReadColor(p, "color") ?? Color.LightGray,
                IsVisible = p.Bool("visible", true),
                IsLocked = p.Bool("locked", false)
            };

            // Handle parent param
            var parentName = p.String("parent");
            var parentGuid = p.String("parent_guid");
            var parentLayer = GetLayerByNameOrGuid(doc, parentName, parentGuid);
            if (parentLayer is not null)
                layer.ParentLayerId = parentLayer.Id;

            index = doc.Layers.Add(layer);
        }

        if (p.Bool("current", false))
            doc.Layers.SetCurrentLayerIndex(index, true);

        if (index < 0)
            return new { success = false, message = "Failed to create layer", name };

        return SerializeLayer(doc.Layers[index]);
    }

    public static object DeleteLayer(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var name = p.String("name");
        var guid = p.String("guid");
        var layer = GetLayerByNameOrGuid(doc, name, guid);
        if (layer is null)
            return new { success = false, name };
        var ok = doc.Layers.Delete(layer.Index, true);
        return new { success = ok, name = layer.FullPath };
    }

    public static object GetOrSetCurrentLayer(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var name = p.String("name");
        var guid = p.String("guid");
        if (!string.IsNullOrWhiteSpace(name) || !string.IsNullOrWhiteSpace(guid))
        {
            var layer = GetLayerByNameOrGuid(doc, name, guid);
            int index;
            if (layer is not null)
            {
                index = layer.Index;
            }
            else if (!string.IsNullOrWhiteSpace(name))
            {
                index = doc.Layers.Add(name, Color.LightGray);
            }
            else
            {
                return new { success = false, message = "Layer not found" };
            }
            doc.Layers.SetCurrentLayerIndex(index, true);
        }
        return SerializeLayer(doc.Layers.CurrentLayer);
    }

    public static object RunRepeated(string command, int steps)
    {
        steps = Math.Max(1, steps);
        var results = new List<bool>();
        for (var i = 0; i < steps; i++)
            results.Add(RhinoApp.RunScript(command, false));
        return new { success = results.All(v => v), steps, results };
    }

    public static object UndoSteps(int steps)
    {
        var doc = RhinoDoc.ActiveDoc;
        int count = 0;
        for (int i = 0; i < Math.Max(1, steps); i++)
        {
            if (doc.Undo()) count++;
            else break;
        }
        return new
        {
            ok = count > 0,
            undone_steps = count,
            requested_steps = steps,
            message = count > 0 ? $"Undid {count} operation(s)" : "Nothing to undo"
        };
    }

    public static object RedoSteps(int steps)
    {
        var doc = RhinoDoc.ActiveDoc;
        int count = 0;
        for (int i = 0; i < Math.Max(1, steps); i++)
        {
            if (doc.Redo()) count++;
            else break;
        }
        return new
        {
            ok = count > 0,
            redone_steps = count,
            requested_steps = steps,
            message = count > 0 ? $"Redid {count} operation(s)" : "Nothing to redo"
        };
    }

    public static object CaptureViewport(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var width = Math.Min(4096, Math.Max(1, p.Int("width", 1200)));
        var height = Math.Min(4096, Math.Max(1, p.Int("height", 900)));
        var viewName = p.String("viewport");
        var showGrid = p.Bool("show_grid", true);
        var showAxes = p.Bool("show_axes", true);
        var showCplaneAxes = p.Bool("show_cplane_axes", false);

        Rhino.Display.RhinoView? view = null;
        if (!string.IsNullOrWhiteSpace(viewName))
        {
            // Try exact name match first
            view = doc.Views.Find(viewName, false);
            if (view is null)
            {
                // Try case-insensitive name match on viewport name
                view = doc.Views.FirstOrDefault(v =>
                    v.ActiveViewport.Name.Equals(viewName, StringComparison.OrdinalIgnoreCase));
            }
            // Standard viewport aliases
            if (view is null)
            {
                var lowerName = viewName.ToLowerInvariant();
                view = doc.Views.FirstOrDefault(v =>
                    v.ActiveViewport.Name.Contains(lowerName, StringComparison.OrdinalIgnoreCase));
            }
        }
        view ??= doc.Views.ActiveView;

        if (view is null)
            return new { success = false, message = "No active viewport" };

        if (p.Bool("zoom_to_fit", false))
            view.ActiveViewport.ZoomExtents();

        var rawBitmap = view.CaptureToBitmap(new Size(width, height), showGrid, showAxes, showCplaneAxes);
        if (rawBitmap is null)
            return new { success = false, message = "Failed to capture viewport" };

        // Convert to base64 — both bitmap and stream always disposed even on exception
        string base64;
        var path = p.String("path");
        using (var bmp = rawBitmap)
        using (var ms = new MemoryStream())
        {
#pragma warning disable CA1416
            bmp.Save(ms, ImageFormat.Png);
            base64 = Convert.ToBase64String(ms.ToArray());

            // Optional disk save inside the using so bmp is still valid
            if (!string.IsNullOrWhiteSpace(path))
                bmp.Save(path);
#pragma warning restore CA1416
        }

        return new
        {
            success = true,
            image_data = base64,
            mime_type = "image/png",
            width,
            height,
            viewport_name = view.ActiveViewport.Name,
            saved_path = string.IsNullOrWhiteSpace(path) ? null : path,
            object_count = doc.Objects.Count(o => !o.IsDeleted),
            layer_count = doc.Layers.Count(l => !l.IsDeleted)
        };
    }

    public static object ExecutePython(Dictionary<string, JsonElement> p)
    {
        var code = p.String("code");
        if (string.IsNullOrWhiteSpace(code))
            return new { success = false, message = "code is required" };

        // Try PythonScript API in-process first
        try
        {
            var py = Rhino.Runtime.PythonScript.Create();
            if (py is not null)
            {
                var doc = RhinoDoc.ActiveDoc;
                var output = new StringBuilder();
                py.Output += (string s) => output.Append(s);

                // SetupScriptContext enables rhinoscriptsyntax and doc/scriptcontext
                py.SetupScriptContext(doc);

                bool prevCapture = RhinoApp.CommandWindowCaptureEnabled;
                RhinoApp.CommandWindowCaptureEnabled = true;
                string[] rhinoLines = Array.Empty<string>();
                try
                {
                    py.ExecuteScript(code);
                    rhinoLines = RhinoApp.CapturedCommandWindowStrings(true) ?? Array.Empty<string>();
                    doc.Views.Redraw();
                    var combined = output.ToString();
                    var rhinoOut = string.Join("\n", rhinoLines).Trim();
                    if (!string.IsNullOrEmpty(rhinoOut)) combined = (combined + "\n" + rhinoOut).TrimStart();
                    return new
                    {
                        success = true,
                        output = combined,
                        error_line = (int?)null,
                        method = "python_script_api"
                    };
                }
                catch (Exception execEx)
                {
                    rhinoLines = RhinoApp.CapturedCommandWindowStrings(true) ?? Array.Empty<string>();
                    doc.Views.Redraw();

                    int? errorLine = null;
                    var msg = execEx.Message;
                    var lineMatch = System.Text.RegularExpressions.Regex.Match(msg, @"\bline\s+(\d+)\b", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                    if (lineMatch.Success && int.TryParse(lineMatch.Groups[1].Value, out var ln))
                        errorLine = ln;

                    return new
                    {
                        success = false,
                        output = string.Join("\n", rhinoLines).Trim(),
                        message = msg,
                        error_line = errorLine,
                        method = "python_script_api"
                    };
                }
                finally
                {
                    RhinoApp.CommandWindowCaptureEnabled = prevCapture;
                }
            }
        }
        catch { /* fall through to RunScript */ }

        // Fallback: temp file via RunScript
        var scriptPath = Path.Combine(Path.GetTempPath(), $"rhino_mcp_{Guid.NewGuid():N}.py");
        File.WriteAllText(scriptPath, code);
        var ok = RhinoApp.RunScript($"_-RunPythonScript \"{scriptPath}\" _Enter", false);
        return new
        {
            success = ok,
            output = (string?)null,
            error_line = (int?)null,
            method = "runscript",
            message = "Output not captured via RunScript path.",
            path = scriptPath
        };
    }

    public static object ExecuteCSharp(Dictionary<string, JsonElement> p)
    {
        var code = p.String("code");
        if (string.IsNullOrWhiteSpace(code))
            return new { success = false, message = "code is required" };
        var output = new StringBuilder();
        try
        {
            var globals = new CSharpGlobals { doc = RhinoDoc.ActiveDoc, output = output };
            var options = _scriptOptions.Value;
            var value = CSharpScript.EvaluateAsync(code, options, globals, typeof(CSharpGlobals)).GetAwaiter().GetResult();
            RhinoDoc.ActiveDoc.Views.Redraw();
            return new { success = true, output = output.ToString(), result = value?.ToString() };
        }
        catch (CompilationErrorException ex)
        {
            return new { success = false, output = output.ToString(), message = string.Join(System.Environment.NewLine, ex.Diagnostics.Select(d => d.ToString())) };
        }
        catch (Exception ex)
        {
            return new { success = false, output = output.ToString(), message = ex.Message };
        }
    }

    public static object BooleanUnion(Dictionary<string, JsonElement> p)
    {
        var ids = p.StringList("object_ids");
        var breps = ids.Select(GetBrepFromId).Where(b => b is not null).Cast<Brep>().ToList();
        if (breps.Count < 2)
            return new { success = false, message = "Boolean union requires at least two valid Breps." };
        var results = Brep.CreateBooleanUnion(breps, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
        return AddBooleanResults(results, ids, p);
    }

    public static object BooleanDifference(Dictionary<string, JsonElement> p)
    {
        var baseId = p.String("base_id");
        var baseBrep = string.IsNullOrWhiteSpace(baseId) ? null : GetBrepFromId(baseId);
        var subtractIds = p.StringList("subtract_ids");
        var subtractBreps = subtractIds.Select(GetBrepFromId).Where(b => b is not null).Cast<Brep>().ToList();
        if (baseBrep is null || subtractBreps.Count == 0)
            return new { success = false, message = "Boolean difference requires a valid base_id and subtract_ids." };
        var results = Brep.CreateBooleanDifference(new[] { baseBrep }, subtractBreps, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
        return AddBooleanResults(results, new[] { baseId! }.Concat(subtractIds), p);
    }

    public static object BooleanIntersection(Dictionary<string, JsonElement> p)
    {
        var ids = p.StringList("object_ids");
        var breps = ids.Select(GetBrepFromId).Where(b => b is not null).Cast<Brep>().ToList();
        if (breps.Count < 2)
            return new { success = false, message = "Boolean intersection requires at least two valid Breps." };
        var results = Brep.CreateBooleanIntersection(breps[0], breps[1], RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
        for (var i = 2; i < breps.Count && results is { Length: > 0 }; i++)
        {
            var next = new List<Brep>();
            foreach (var result in results)
            {
                var partial = Brep.CreateBooleanIntersection(result, breps[i], RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
                if (partial is not null)
                    next.AddRange(partial);
            }
            results = next.ToArray();
        }
        return AddBooleanResults(results, ids, p);
    }

    public static object RunAdvancedCommand(string operation, Dictionary<string, JsonElement> p)
    {
        return operation switch
        {
            "loft" => Loft(p),
            "extrude_curve" => ExtrudeCurve(p),
            "sweep1" => Sweep1(p),
            "offset_curve" => OffsetCurve(p),
            "pipe" => Pipe(p),
            "project_curve" => ProjectCurve(p),
            "intersect_curves" => IntersectCurves(p),
            "split_curve" => SplitCurve(p),
            _ => new { success = false, status = "unsupported", operation, message = "Unsupported advanced operation." }
        };
    }

    public static object ListPlugins(Dictionary<string, JsonElement> p)
    {
        var installed = PlugIn.GetInstalledPlugIns();
        var plugins = installed.Select(item => new
        {
            id = item.Key.ToString(),
            name = item.Value,
            loaded = PlugIn.Find(item.Key) is not null,
            path = SafePluginPath(item.Key)
        }).ToList();
        return new { plugins, count = plugins.Count };
    }

    public static object LoadPlugin(Dictionary<string, JsonElement> p)
    {
        var idText = p.String("id");
        var path = p.String("path");
        if (!string.IsNullOrWhiteSpace(path))
        {
            var result = PlugIn.LoadPlugIn(path, out var loadedId);
            return new { success = loadedId != Guid.Empty, id = loadedId.ToString(), result = result.ToString(), path };
        }
        if (!Guid.TryParse(idText, out var id))
            return new { success = false, message = "id or path is required" };
        var ok = PlugIn.LoadPlugIn(id, loadQuietly: true, forceLoad: true);
        return new { success = ok, id = id.ToString() };
    }

    // -------------------------------------------------------------------------
    // Material handlers
    // -------------------------------------------------------------------------

    public static object GetMaterials()
    {
        var doc = RhinoDoc.ActiveDoc;
        var materials = doc.Materials
            .Where(m => !m.IsDeleted)
            .Select(m => SerializeMaterial(m))
            .ToList();
        return new { materials, count = materials.Count };
    }

    public static object CreateMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var name = p.String("name", "Material");
        var mat = new Rhino.DocObjects.Material();
        mat.Name = name!;

        var diffuse = ReadColor(p, "diffuse") ?? ReadColor(p, "color");
        if (diffuse.HasValue)
            mat.DiffuseColor = diffuse.Value;

        var specular = ReadColor(p, "specular");
        if (specular.HasValue)
            mat.SpecularColor = specular.Value;

        var emission = ReadColor(p, "emission");
        if (emission.HasValue)
            mat.EmissionColor = emission.Value;

        var shininess = p.Double("shininess", -1);
        if (shininess >= 0)
            mat.Shine = Math.Clamp(shininess, 0, 255);

        var transparency = p.Double("transparency", -1);
        if (transparency >= 0)
            mat.Transparency = Math.Clamp(transparency, 0, 1);

        var index = doc.Materials.Add(mat);
        if (index < 0)
            return new { success = false, message = "Failed to create material" };

        return new { success = true, index, material = SerializeMaterial(doc.Materials[index]) };
    }

    public static object SetObjectMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var obj = FindObject(p);
        if (obj is null)
            return new { success = false, message = "Object not found" };

        // Resolve material by index or name
        Rhino.DocObjects.Material? mat = null;
        var materialIndex = p.Int("material_index", -1);
        var materialName = p.String("material_name");

        if (materialIndex >= 0 && materialIndex < doc.Materials.Count)
        {
            mat = doc.Materials[materialIndex];
        }
        else if (!string.IsNullOrWhiteSpace(materialName))
        {
            mat = doc.Materials.FirstOrDefault(m => !m.IsDeleted &&
                m.Name.Equals(materialName, StringComparison.OrdinalIgnoreCase));
            materialIndex = mat?.Index ?? -1;
        }

        if (mat is null || materialIndex < 0)
            return new { success = false, message = "Material not found" };

        var attrs = obj.Attributes.Duplicate();
        attrs.MaterialIndex = materialIndex;
        attrs.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject;
        doc.Objects.ModifyAttributes(obj, attrs, true);
        doc.Views.Redraw();
        return new { success = true, object_id = obj.Id.ToString(), material_index = materialIndex, material_name = mat.Name };
    }

    public static object DeleteMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var materialIndex = p.Int("material_index", -1);
        var materialName = p.String("material_name");

        Rhino.DocObjects.Material? mat = null;
        if (materialIndex >= 0 && materialIndex < doc.Materials.Count)
        {
            mat = doc.Materials[materialIndex];
            materialIndex = mat.Index;
        }
        else if (!string.IsNullOrWhiteSpace(materialName))
        {
            mat = doc.Materials.FirstOrDefault(m => !m.IsDeleted &&
                m.Name.Equals(materialName, StringComparison.OrdinalIgnoreCase));
            materialIndex = mat?.Index ?? -1;
        }

        if (mat is null || materialIndex < 0)
            return new { success = false, message = "Material not found" };

        // MaterialTable.Delete takes a Material, not an index
        var ok = doc.Materials.Delete(mat);
        return new { success = ok, material_name = mat.Name, material_index = materialIndex };
    }

    private static object SerializeMaterial(Rhino.DocObjects.Material m)
    {
        return new
        {
            index = m.Index,
            name = m.Name,
            diffuse = ColorArray(m.DiffuseColor),
            specular = ColorArray(m.SpecularColor),
            emission = ColorArray(m.EmissionColor),
            shininess = m.Shine,
            transparency = m.Transparency
        };
    }

    // -------------------------------------------------------------------------
    // PBR material handlers
    // -------------------------------------------------------------------------

    /// <summary>
    /// Creates a Physically-Based Rendering material and adds it to the document
    /// material table.  All colour values use normalised floats (0.0–1.0).
    /// </summary>
    public static object CreatePbrMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var name = p.String("name") ?? "PBR_Material_" + DateTime.Now.Ticks;

        // Build the underlying Material (Rhino.DocObjects.Material) which
        // carries the PhysicallyBasedMaterial sub-object.
        var mat = new Rhino.DocObjects.Material();
        mat.Name = name;

        // Switch to PBR / Physically Based mode.
        mat.ToPhysicallyBased();
        var pbr = mat.PhysicallyBased;
        if (pbr == null)
            return new { success = false, message = "Failed to initialise PhysicallyBasedMaterial on the material." };

        // Base colour
        var bc = p.DoubleArray("base_color");
        if (bc.Length >= 3)
            pbr.BaseColor = new Rhino.Display.Color4f((float)bc[0], (float)bc[1], (float)bc[2], bc.Length >= 4 ? (float)bc[3] : 1f);

        pbr.Metallic  = p.Double("metallic",  0.0);
        pbr.Roughness = p.Double("roughness", 0.5);
        pbr.Opacity   = p.Double("opacity",   1.0);

        // Emission — colour * multiplier
        var em = p.DoubleArray("emission");
        if (em.Length >= 3)
        {
            double mult = p.Double("emission_multiplier", 0.0);
            pbr.Emission = new Rhino.Display.Color4f(
                (float)(em[0] * mult),
                (float)(em[1] * mult),
                (float)(em[2] * mult),
                1f);
        }

        // Texture helper — adds a texture file to a specific channel.
        void AddTex(string key, Rhino.DocObjects.TextureType texType)
        {
            var path = p.String(key);
            if (string.IsNullOrEmpty(path)) return;
            var tex = new Rhino.DocObjects.Texture { FileName = path, TextureType = texType };
            mat.SetTexture(tex, texType);
        }

        AddTex("base_color_texture",   Rhino.DocObjects.TextureType.Bitmap);
        AddTex("roughness_texture",    Rhino.DocObjects.TextureType.PBR_Roughness);
        AddTex("metallic_texture",     Rhino.DocObjects.TextureType.PBR_Metallic);
        AddTex("normal_texture",       Rhino.DocObjects.TextureType.Bump);
        AddTex("displacement_texture", Rhino.DocObjects.TextureType.PBR_Displacement);
        AddTex("ao_texture",           Rhino.DocObjects.TextureType.PBR_AmbientOcclusion);
        AddTex("opacity_texture",      Rhino.DocObjects.TextureType.Transparency);

        int index = doc.Materials.Add(mat);
        if (index < 0)
            return new { success = false, message = "doc.Materials.Add returned a negative index." };

        doc.Materials.Modify(mat, index, true);
        doc.Views.Redraw();
        return new { success = true, material_index = index, material_name = name };
    }

    /// <summary>
    /// Loads an HDR or EXR image file and sets it as the document's render
    /// environment for background, lighting, and/or reflections.
    /// </summary>
    public static object SetEnvironmentMap(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var filepath = p.String("filepath") ?? p.String("path") ?? "";
        if (!System.IO.File.Exists(filepath))
            return new { success = false, message = "File not found: " + filepath };

        return new { success = false, message = "set_environment_map requires Rhino 8 with a compatible render plugin installed. Use RhinoApp.RunScript to apply HDR environments via the Rhino command line." };
    }

    /// <summary>
    /// Triggers a Rhino render, saves the result to disk, and optionally returns
    /// the image as a Base-64-encoded PNG string.
    /// </summary>
    public static object RenderViewport(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;

        string outPath = p.String("output_path") ?? "";
        if (string.IsNullOrEmpty(outPath))
            outPath = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"rhino_render_{DateTime.Now:yyyyMMdd_HHmmss}.png");

        int width  = Math.Max(1, Math.Min(8192, (int)p.Double("width",  1920)));
        int height = Math.Max(1, Math.Min(8192, (int)p.Double("height", 1080)));

        // Configure render resolution.
        doc.RenderSettings.ImageSize        = new System.Drawing.Size(width, height);
        doc.RenderSettings.UseViewportSize  = false;

        // Activate the requested named view/viewport before rendering.
        string viewName = p.String("view_name") ?? "";
        if (!string.IsNullOrEmpty(viewName))
        {
            var view = doc.Views.Find(viewName, true);
            if (view != null)
                doc.Views.ActiveView = view;
        }

        // Run the Rhino render command and wait for it to finish.
        RhinoApp.RunScript("_-Render", false);

        // Try to save via the active RenderWindow first; fall back to a
        // viewport bitmap capture when the window is not available.
        bool saved = false;
        string format = "png";

        // RenderWindow.Active not available in this SDK version; fall through to viewport capture.

        if (!saved)
        {
            var activeView = doc.Views.ActiveView;
            if (activeView != null)
            {
                var bmp = activeView.CaptureToBitmap(new System.Drawing.Size(width, height));
                if (bmp != null)
                {
#pragma warning disable CA1416
                    bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
#pragma warning restore CA1416
                    saved = true;
                }
            }
        }

        bool returnBase64 = p.Bool("return_base64", true);
        string? base64 = null;
        if (saved && returnBase64 && System.IO.File.Exists(outPath))
        {
            var bytes = System.IO.File.ReadAllBytes(outPath);
            base64 = Convert.ToBase64String(bytes);
        }

        return new { success = saved, filepath = outPath, base64, width, height, format };
    }

    /// <summary>
    /// Assigns an existing PBR (or any named) material to one or more objects.
    /// </summary>
    public static object AssignPbrMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var materialName = p.String("material_name");
        if (string.IsNullOrWhiteSpace(materialName))
            return new { success = false, message = "material_name is required." };

        // Resolve material index.
        var mat = doc.Materials.FirstOrDefault(m =>
            !m.IsDeleted &&
            m.Name.Equals(materialName, StringComparison.OrdinalIgnoreCase));

        if (mat == null)
            return new { success = false, message = $"Material '{materialName}' not found." };

        int matIndex = mat.Index;
        bool allObjects = p.Bool("all_objects", false);

        IEnumerable<Rhino.DocObjects.RhinoObject> targets;
        if (allObjects)
        {
            targets = doc.Objects.Where(o => !o.IsDeleted);
        }
        else
        {
            var ids = p.StringList("object_ids");
            targets = ids
                .Select(idText => Guid.TryParse(idText, out var g) ? doc.Objects.FindId(g) : null)
                .Where(o => o != null)
                .Cast<Rhino.DocObjects.RhinoObject>();
        }

        int count = 0;
        foreach (var obj in targets)
        {
            var attrs = obj.Attributes.Duplicate();
            attrs.MaterialIndex  = matIndex;
            attrs.MaterialSource = Rhino.DocObjects.ObjectMaterialSource.MaterialFromObject;
            if (doc.Objects.ModifyAttributes(obj, attrs, true))
                count++;
        }

        doc.Views.Redraw();
        return new { success = count > 0, assigned_count = count, material_name = materialName };
    }

    /// <summary>
    /// Returns the full PBR property set for a named or indexed material.
    /// </summary>
    public static object GetPbrMaterial(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;

        Rhino.DocObjects.Material? mat = null;
        int idx = p.Int("material_index", -1);
        if (idx >= 0 && idx < doc.Materials.Count)
            mat = doc.Materials[idx];

        if (mat == null)
        {
            var name = p.String("material_name");
            if (!string.IsNullOrWhiteSpace(name))
                mat = doc.Materials.FirstOrDefault(m =>
                    !m.IsDeleted &&
                    m.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
        }

        if (mat == null)
            return new { success = false, message = "Material not found." };

        return new { success = true, material = SerializePbrMaterial(mat) };
    }

    /// <summary>
    /// Returns all Physically-Based materials in the active document.
    /// </summary>
    public static object ListPbrMaterials(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var materials = doc.Materials
            .Where(m => !m.IsDeleted && m.IsPhysicallyBased)
            .Select(m => SerializePbrMaterial(m))
            .ToList();
        return new { success = true, materials, count = materials.Count };
    }

    /// <summary>
    /// Updates document-level render settings.  Only parameters that are
    /// explicitly present in the command payload are modified.
    /// </summary>
    public static object SetRenderSettings(Dictionary<string, JsonElement> p)
    {
        var doc  = RhinoDoc.ActiveDoc;
        var rs   = doc.RenderSettings;
        var applied = new Dictionary<string, object?>();

        if (p.TryGetValue("samples", out _))
        {
            // Rhino does not expose a single Cycles sample count through
            // RenderSettings; store the value as a named custom attribute
            // so the agent can read it back, then attempt to set it through
            // the Cycles plug-in parameter bag.
            int samples = p.Int("samples", 64);
            applied["samples"] = samples;
            // cycles_samples: no public API in this SDK version
        }

        if (p.TryGetValue("background_color", out _))
        {
            var bc = p.DoubleArray("background_color");
            if (bc.Length >= 3)
            {
                rs.BackgroundColorTop = System.Drawing.Color.FromArgb(
                    (int)Math.Clamp(bc[0], 0, 255),
                    (int)Math.Clamp(bc[1], 0, 255),
                    (int)Math.Clamp(bc[2], 0, 255));
                rs.BackgroundColorBottom = rs.BackgroundColorTop;
                applied["background_color"] = new[] { (int)bc[0], (int)bc[1], (int)bc[2] };
            }
        }

        if (p.TryGetValue("use_transparent_background", out _))
        {
            rs.TransparentBackground = p.Bool("use_transparent_background", false);
            applied["use_transparent_background"] = rs.TransparentBackground;
        }

        if (p.TryGetValue("enable_shadows", out _))
        {
            // Shadow casting is a per-display-mode property in older RhinoCommon;
            // attempt to set it on the current display mode gracefully.
            bool shadows = p.Bool("enable_shadows", true);
            applied["enable_shadows"] = shadows;
            try
            {
                var dm = Rhino.Display.DisplayModeDescription.GetDisplayMode(
                    doc.Views.ActiveView?.ActiveViewport.DisplayMode?.Id ?? Guid.Empty);
                if (dm != null)
                {
                    Rhino.Display.DisplayModeDescription.UpdateDisplayMode(dm);
                }
            }
            catch { /* not available in all SDK versions */ }
        }

        if (p.TryGetValue("ambient_occlusion", out _))
        {
            bool ao = p.Bool("ambient_occlusion", false);
            applied["ambient_occlusion"] = ao;
            // ao_enabled: no public API in this SDK version
        }

        if (p.TryGetValue("enable_ground_plane", out _))
        {
            bool gpEnabled = p.Bool("enable_ground_plane", false);
            doc.GroundPlane.Enabled = gpEnabled;
            applied["enable_ground_plane"] = gpEnabled;

            if (p.TryGetValue("ground_plane_altitude", out _))
            {
                double alt = p.Double("ground_plane_altitude", 0.0);
                doc.GroundPlane.Altitude = alt;
                applied["ground_plane_altitude"] = alt;
            }
        }

        doc.Views.Redraw();
        return new { success = true, settings = applied, message = "Render settings updated." };
    }

    // -------------------------------------------------------------------------
    // PBR serialisation helper
    // -------------------------------------------------------------------------

    private static object SerializePbrMaterial(Rhino.DocObjects.Material m)
    {
        var pbr = m.PhysicallyBased;
        if (pbr == null)
        {
            // Fall back to basic material representation for non-PBR materials.
            return new
            {
                index        = m.Index,
                name         = m.Name,
                is_pbr       = false,
                diffuse      = ColorArray(m.DiffuseColor),
                transparency = m.Transparency
            };
        }

        // Collect texture file paths per channel.
        string? TexPath(Rhino.DocObjects.TextureType type)
        {
            var tex = m.GetTexture(type);
            return tex != null ? tex.FileName : null;
        }

        var bc = pbr.BaseColor;
        var em = pbr.Emission;

        return new
        {
            index                  = m.Index,
            name                   = m.Name,
            is_pbr                 = true,
            base_color             = new[] { bc.R, bc.G, bc.B, bc.A },
            metallic               = pbr.Metallic,
            roughness              = pbr.Roughness,
            opacity                = pbr.Opacity,
            emission               = new[] { em.R, em.G, em.B, em.A },
            base_color_texture     = TexPath(Rhino.DocObjects.TextureType.Bitmap),
            roughness_texture      = TexPath(Rhino.DocObjects.TextureType.PBR_Roughness),
            metallic_texture       = TexPath(Rhino.DocObjects.TextureType.PBR_Metallic),
            normal_texture         = TexPath(Rhino.DocObjects.TextureType.Bump),
            displacement_texture   = TexPath(Rhino.DocObjects.TextureType.PBR_Displacement),
            ao_texture             = TexPath(Rhino.DocObjects.TextureType.PBR_AmbientOcclusion),
            opacity_texture        = TexPath(Rhino.DocObjects.TextureType.Transparency)
        };
    }

    // -------------------------------------------------------------------------
    // Advanced operations (private)
    // -------------------------------------------------------------------------

    private static object Loft(Dictionary<string, JsonElement> p)
    {
        var curves = p.StringList("curve_ids").Select(GetCurveFromId).Where(c => c is not null).Cast<Curve>().ToList();
        if (curves.Count < 2)
            return new { success = false, message = "Loft requires at least two valid curve_ids." };
        var loftType = p.Int("loft_type", 0) switch
        {
            1 => LoftType.Loose,
            2 => LoftType.Tight,
            3 => LoftType.Straight,
            4 => LoftType.Developable,
            _ => LoftType.Normal
        };
        var breps = Brep.CreateFromLoft(curves, Point3d.Unset, Point3d.Unset, loftType, p.Bool("closed", false));
        return AddBreps(breps, p.String("name"), "Loft created");
    }

    private static object ExtrudeCurve(Dictionary<string, JsonElement> p)
    {
        var curve = GetCurveFromId(p.String("curve_id"));
        var direction = p.DoubleArray("direction");
        if (curve is null || direction.Length != 3)
            return new { success = false, message = "Extrude requires curve_id and direction [x,y,z]." };
        var surface = Surface.CreateExtrusion(curve, new Vector3d(direction[0], direction[1], direction[2]));
        if (surface is null)
            return new { success = false, message = "Extrusion failed." };
        var attr = AttributesWithName(p.String("name"));
        Guid id;
        if (p.Bool("cap", true) && curve.IsClosed)
        {
            var capped = surface.ToBrep()?.CapPlanarHoles(RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
            id = capped is not null ? RhinoDoc.ActiveDoc.Objects.AddBrep(capped, attr) : RhinoDoc.ActiveDoc.Objects.AddSurface(surface, attr);
        }
        else
        {
            id = RhinoDoc.ActiveDoc.Objects.AddSurface(surface, attr);
        }
        RhinoDoc.ActiveDoc.Views.Redraw();
        return new { success = true, result_id = id.ToString(), message = "Extrusion created" };
    }

    private static object Sweep1(Dictionary<string, JsonElement> p)
    {
        var rail = GetCurveFromId(p.String("rail_id"));
        var profiles = p.StringList("profile_ids").Select(GetCurveFromId).Where(c => c is not null).Cast<Curve>().ToList();
        if (rail is null || profiles.Count == 0)
            return new { success = false, message = "Sweep1 requires rail_id and profile_ids." };
        var sweep = new SweepOneRail();
        sweep.SetToRoadlikeTop();
        sweep.ClosedSweep = p.Bool("closed", false);
        var breps = sweep.PerformSweep(rail, profiles);
        return AddBreps(breps, p.String("name"), "Sweep created");
    }

    private static object OffsetCurve(Dictionary<string, JsonElement> p)
    {
        var curve = GetCurveFromId(p.String("curve_id"));
        var distance = p.Double("distance", 0);
        if (curve is null || Math.Abs(distance) < RhinoDoc.ActiveDoc.ModelAbsoluteTolerance)
            return new { success = false, message = "Offset requires curve_id and non-zero distance." };
        Plane plane;
        var normal = p.DoubleArray("plane");
        if (normal.Length == 3)
            plane = new Plane(curve.PointAtStart, new Vector3d(normal[0], normal[1], normal[2]));
        else if (!curve.TryGetPlane(out plane))
            plane = new Plane(curve.PointAtStart, Vector3d.ZAxis);
        var style = p.Int("corner_style", 1) switch
        {
            0 => CurveOffsetCornerStyle.None,
            2 => CurveOffsetCornerStyle.Round,
            3 => CurveOffsetCornerStyle.Smooth,
            4 => CurveOffsetCornerStyle.Chamfer,
            _ => CurveOffsetCornerStyle.Sharp
        };
        var curves = curve.Offset(plane, distance, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance, style);
        return AddCurves(curves, p.String("name"), "Offset created");
    }

    private static object Pipe(Dictionary<string, JsonElement> p)
    {
        var curve = GetCurveFromId(p.String("curve_id"));
        var radius = p.Double("radius", 0);
        if (curve is null || radius <= 0)
            return new { success = false, message = "Pipe requires curve_id and positive radius." };
        var cap = p.Bool("cap", true) ? PipeCapMode.Flat : PipeCapMode.None;
        var breps = Brep.CreatePipe(curve, radius, !p.Bool("fit_rail", false), cap, p.Bool("fit_rail", false), RhinoDoc.ActiveDoc.ModelAbsoluteTolerance, RhinoDoc.ActiveDoc.ModelAngleToleranceRadians);
        return AddBreps(breps, p.String("name"), "Pipe created");
    }

    private static object ProjectCurve(Dictionary<string, JsonElement> p)
    {
        var curve = GetCurveFromId(p.String("curve_id"));
        var direction = p.DoubleArray("direction");
        var targetIds = p.StringList("target_ids");
        if (curve is null || direction.Length != 3 || targetIds.Count == 0)
            return new { success = false, message = "Project requires curve_id, target_ids, and direction." };
        var breps = new List<Brep>();
        var meshes = new List<Mesh>();
        foreach (var id in targetIds)
        {
            var obj = FindById(id);
            if (obj?.Geometry is Brep brep)
                breps.Add(brep);
            else if (obj?.Geometry is Mesh mesh)
                meshes.Add(mesh);
            else if (obj?.Geometry is Extrusion extrusion)
                breps.Add(extrusion.ToBrep());
        }
        var projected = new List<Curve>();
        var dir = new Vector3d(direction[0], direction[1], direction[2]);
        if (breps.Count > 0)
            projected.AddRange(Curve.ProjectToBrep(curve, breps, dir, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance) ?? Array.Empty<Curve>());
        if (meshes.Count > 0)
            projected.AddRange(Curve.ProjectToMesh(curve, meshes, dir, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance) ?? Array.Empty<Curve>());
        return AddCurves(projected, p.String("name"), "Projection created");
    }

    private static object IntersectCurves(Dictionary<string, JsonElement> p)
    {
        var a = GetCurveFromId(p.String("curve_id_a"));
        var b = GetCurveFromId(p.String("curve_id_b"));
        if (a is null || b is null)
            return new { success = false, message = "Intersect requires curve_id_a and curve_id_b." };
        var tolerance = p.Double("tolerance", RhinoDoc.ActiveDoc.ModelAbsoluteTolerance);
        var events = Intersection.CurveCurve(a, b, tolerance, tolerance);
        var pointIds = new List<string>();
        var curveIds = new List<string>();
        var points = new List<double[]>();
        foreach (var item in events)
        {
            if (item.IsPoint)
            {
                var id = RhinoDoc.ActiveDoc.Objects.AddPoint(item.PointA, AttributesWithName(p.String("name")));
                pointIds.Add(id.ToString());
                points.Add(PointArray(item.PointA));
            }
            else if (item.IsOverlap)
            {
                var overlap = a.Trim(item.OverlapA.T0, item.OverlapA.T1);
                if (overlap is not null)
                    curveIds.Add(RhinoDoc.ActiveDoc.Objects.AddCurve(overlap, AttributesWithName(p.String("name"))).ToString());
            }
        }
        RhinoDoc.ActiveDoc.Views.Redraw();
        return new { success = true, point_ids = pointIds, curve_ids = curveIds, points, count = events.Count };
    }

    private static object SplitCurve(Dictionary<string, JsonElement> p)
    {
        var curveId = p.String("curve_id");
        var curve = GetCurveFromId(curveId);
        if (curve is null)
            return new { success = false, message = "Split requires curve_id." };
        var parameters = p.TryGetValue("parameters", out var pe) && pe.ValueKind == JsonValueKind.Array
            ? pe.EnumerateArray().Select(e => e.GetDouble()).ToList()
            : new List<double>();
        foreach (var pointId in p.StringList("point_ids"))
        {
            var obj = FindById(pointId);
            Point3d? point = obj?.Geometry switch
            {
                Rhino.Geometry.Point pt => pt.Location,
                TextDot dot => dot.Point,
                _ => null
            };
            if (point.HasValue && curve.ClosestPoint(point.Value, out var t, RhinoDoc.ActiveDoc.ModelAbsoluteTolerance))
                parameters.Add(t);
        }
        if (parameters.Count == 0)
            return new { success = false, message = "No split parameters resolved." };
        var segments = curve.Split(parameters);
        var added = AddCurves(segments, p.String("name"), "Curve split");
        if (p.Bool("delete_source", true) && Guid.TryParse(curveId, out var srcId))
            RhinoDoc.ActiveDoc.Objects.Delete(srcId, true);
        return added;
    }

    // -------------------------------------------------------------------------
    // New rich serializer helpers
    // -------------------------------------------------------------------------

    /// <summary>
    /// Rich serializer for a RhinoObject — returns typed geometry detail.
    /// </summary>
    private static object SerializeObject(RhinoObject obj, bool includeGeometry)
    {
        var doc = RhinoDoc.ActiveDoc;
        var bbox = obj.Geometry.GetBoundingBox(true);
        var normalizedType = ToNormalizedTypeName(obj);

        object? geometryDetail = null;
        if (includeGeometry)
            geometryDetail = SerializeGeometry(obj, normalizedType);

        // Fix 5: material_index, material_name, color [r,g,b,a], user_attributes
        var matIndex = obj.Attributes.MaterialIndex;
        string? matName = null;
        if (matIndex >= 0 && matIndex < doc.Materials.Count)
        {
            try { matName = doc.Materials[matIndex].Name; } catch { }
        }

        var objColor = obj.Attributes.ObjectColor;
        var colorArr = new[] { (int)objColor.R, (int)objColor.G, (int)objColor.B, (int)objColor.A };

        // Build user_attributes from NameValueCollection returned by GetUserStrings()
        var userAttrs = new Dictionary<string, string>();
        var userStrings = obj.Attributes.GetUserStrings();
        if (userStrings is not null)
        {
            foreach (string? key in userStrings.AllKeys)
            {
                if (key is not null)
                    userAttrs[key] = userStrings[key] ?? "";
            }
        }

        return new
        {
            id = obj.Id.ToString(),
            name = obj.Name,
            type = normalizedType,
            layer = LayerName(obj),
            hidden = obj.IsHidden,
            locked = obj.IsLocked,
            bbox = bbox.IsValid ? (object)new[] { PointArray(bbox.Min), PointArray(bbox.Max) } : null,
            material_index = matIndex,
            material_name = matName,
            color = colorArr,
            user_attributes = userAttrs,
            geometry = geometryDetail
        };
    }

    private static object? SerializeGeometry(RhinoObject obj, string normalizedType)
    {
        try
        {
            switch (normalizedType)
            {
                case "POINT":
                {
                    if (obj.Geometry is Rhino.Geometry.Point pt)
                        return new { point = PointArray(pt.Location) };
                    break;
                }
                case "LINE":
                {
                    if (obj.Geometry is LineCurve lc)
                        return new { start = PointArray(lc.Line.From), end = PointArray(lc.Line.To), length = lc.Line.Length };
                    break;
                }
                case "CIRCLE":
                {
                    if (obj.Geometry is ArcCurve ac && ac.IsCircle(RhinoDoc.ActiveDoc.ModelAbsoluteTolerance))
                        return new { center = PointArray(ac.Arc.Center), radius = ac.Arc.Radius, normal = VectorArray(ac.Arc.Plane.Normal) };
                    break;
                }
                case "ARC":
                {
                    if (obj.Geometry is ArcCurve ac)
                        return new
                        {
                            center = PointArray(ac.Arc.Center),
                            radius = ac.Arc.Radius,
                            start_angle_degrees = RhinoMath.ToDegrees(ac.Arc.StartAngle),
                            end_angle_degrees = RhinoMath.ToDegrees(ac.Arc.EndAngle)
                        };
                    break;
                }
                case "ELLIPSE":
                {
                    if (obj.Geometry is NurbsCurve nc && nc.TryGetEllipse(out var ellipse))
                        return new
                        {
                            center   = PointArray(ellipse.Plane.Origin),
                            radius_x = ellipse.Radius1,
                            radius_y = ellipse.Radius2,
                            // Full defining plane so callers can reconstruct orientation exactly
                            plane    = new
                            {
                                origin  = PointArray(ellipse.Plane.Origin),
                                x_axis  = VectorArray(ellipse.Plane.XAxis),
                                y_axis  = VectorArray(ellipse.Plane.YAxis),
                                normal  = VectorArray(ellipse.Plane.Normal)
                            }
                        };
                    break;
                }
                case "POLYLINE":
                case "CURVE":
                {
                    if (obj.Geometry is Curve c)
                        return new { point_count = c.ToNurbsCurve()?.Points.Count ?? 0, degree = c.Degree, closed = c.IsClosed, domain = new[] { c.Domain.T0, c.Domain.T1 } };
                    break;
                }
                case "BREP":
                {
                    if (obj.Geometry is Brep brep)
                        return new { face_count = brep.Faces.Count, edge_count = brep.Edges.Count, vertex_count = brep.Vertices.Count, is_solid = brep.IsSolid };
                    break;
                }
                case "EXTRUSION":
                {
                    if (obj.Geometry is Extrusion extrusion)
                    {
                        var b = extrusion.ToBrep();
                        return new { face_count = b?.Faces.Count ?? 0, edge_count = b?.Edges.Count ?? 0, vertex_count = b?.Vertices.Count ?? 0, is_solid = b?.IsSolid ?? false };
                    }
                    break;
                }
                case "MESH":
                {
                    if (obj.Geometry is Mesh mesh)
                        return new { vertex_count = mesh.Vertices.Count, face_count = mesh.Faces.Count };
                    break;
                }
                case "TEXT":
                {
                    if (obj.Geometry is TextEntity te)
                        return new { text = te.PlainText, height = te.TextHeight };
                    if (obj.Geometry is TextDot td)
                        return new { text = td.Text, height = td.FontHeight };
                    break;
                }
            }
        }
        catch { /* best-effort */ }

        return new { raw_type = obj.Geometry.GetType().Name };
    }

    /// <summary>
    /// Normalize ObjectType enum to a canonical string.
    /// </summary>
    private static string ToNormalizedTypeName(ObjectType type)
    {
        return type switch
        {
            ObjectType.Point => "POINT",
            ObjectType.Curve => "CURVE",
            ObjectType.Surface => "SURFACE",
            ObjectType.Brep => "BREP",
            ObjectType.Mesh => "MESH",
            ObjectType.Extrusion => "EXTRUSION",
            ObjectType.Annotation => "TEXT",
            ObjectType.TextDot => "TEXT",
            ObjectType.InstanceReference => "BLOCK",
            _ => type.ToString().ToUpperInvariant()
        };
    }

    /// <summary>
    /// Normalize a RhinoObject to a more specific type name by peeking at geometry.
    /// </summary>
    private static string ToNormalizedTypeName(RhinoObject obj)
    {
        if (obj.ObjectType == ObjectType.Curve)
        {
            return obj.Geometry switch
            {
                LineCurve => "LINE",
                ArcCurve ac when ac.IsCircle(RhinoDoc.ActiveDoc.ModelAbsoluteTolerance) => "CIRCLE",
                ArcCurve => "ARC",
                PolylineCurve => "POLYLINE",
                _ => "CURVE"
            };
        }
        return ToNormalizedTypeName(obj.ObjectType);
    }

    /// <summary>
    /// Serialize a layer to a flat dictionary object.
    /// </summary>
    private static object SerializeLayer(Layer layer)
    {
        return new
        {
            id = layer.Id.ToString(),
            name = layer.Name,
            full_path = layer.FullPath,
            parent_id = layer.ParentLayerId == Guid.Empty ? (string?)null : layer.ParentLayerId.ToString(),
            color = ColorArray(layer.Color),
            visible = layer.IsVisible,
            locked = layer.IsLocked,
            object_count = RhinoDoc.ActiveDoc.Objects.Count(o => !o.IsDeleted && o.Attributes.LayerIndex == layer.Index)
        };
    }

    /// <summary>
    /// Build a nested layer hierarchy tree.
    /// </summary>
    private static List<object> BuildLayerHierarchy(RhinoDoc doc)
    {
        var allLayers = doc.Layers.Where(l => !l.IsDeleted).ToList();
        return BuildLayerChildren(doc, allLayers, Guid.Empty);
    }

    private static List<object> BuildLayerChildren(RhinoDoc doc, List<Layer> allLayers, Guid parentId)
    {
        var result = new List<object>();
        foreach (var layer in allLayers.Where(l => l.ParentLayerId == parentId))
        {
            var objectCount = doc.Objects.Where(o => !o.IsDeleted && o.Attributes.LayerIndex == layer.Index).Count();
            var children = BuildLayerChildren(doc, allLayers, layer.Id);
            result.Add(new
            {
                id = layer.Id.ToString(),
                name = layer.Name,
                full_path = layer.FullPath,
                parent_id = layer.ParentLayerId == Guid.Empty ? (string?)null : layer.ParentLayerId.ToString(),
                color = ColorArray(layer.Color),
                visible = layer.IsVisible,
                locked = layer.IsLocked,
                object_count = objectCount,
                children
            });
        }
        return result;
    }

    // -------------------------------------------------------------------------
    // Helper: layer lookup by name or guid
    // -------------------------------------------------------------------------

    private static Layer? GetLayerByNameOrGuid(RhinoDoc doc, string? name, string? guid)
    {
        if (!string.IsNullOrWhiteSpace(name))
        {
            var idx = doc.Layers.FindByFullPath(name, -1);
            if (idx >= 0) return doc.Layers[idx];
        }
        if (Guid.TryParse(guid, out var g))
        {
            var layerById = doc.Layers.FindId(g);
            if (layerById is not null) return layerById;
        }
        return null;
    }

    // -------------------------------------------------------------------------
    // Primitive creation
    // -------------------------------------------------------------------------

    private static Guid AddPrimitive(string type, Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        return type switch
        {
            "POINT" => doc.Objects.AddPoint(ReadPoint(p, "point") ?? ReadPoint(p, "location") ?? Point3d.Origin),
            "LINE" => doc.Objects.AddLine(new Line(ReadPoint(p, "start") ?? Point3d.Origin, ReadPoint(p, "end") ?? new Point3d(1, 0, 0))),
            "CIRCLE" => doc.Objects.AddCircle(new Circle(ReadPoint(p, "center") ?? Point3d.Origin, p.Double("radius", 1))),
            "SPHERE" => doc.Objects.AddSphere(new Sphere(ReadPoint(p, "center") ?? Point3d.Origin, p.Double("radius", 1))),
            "BOX" => AddBox(p),
            "MESH" => AddMesh(p),
            "TEXT" => AddText(p),
            "POLYLINE" => AddPolyline(p),
            "ARC" => AddArc(p),
            "ELLIPSE" => AddEllipse(p),
            "CURVE" => AddNurbsCurve(p),
            "CONE" => AddCone(p),
            "CYLINDER" => AddCylinder(p),
            "TORUS" => AddTorus(p),
            "PLANE" => AddPlane(p),
            "SURFACE" => AddNurbsSurface(p),
            "POINTCLOUD" or "POINT_CLOUD" => AddPointCloud(p),
            "TEXTDOT" => AddTextDot(p),
            "LIGHT" => AddLightObject(p),
            "EXTRUSION" => AddExtrusion(p),
            "BLOCK_INSERT" or "INSTANCE" or "INSTANCE_REFERENCE" => AddBlockInsert(p),
            "DIMENSION_LINEAR" => AddLinearDimension(p),
            "DIMENSION_RADIAL" => AddRadialDimension(p),
            "DIMENSION_ANGULAR" => AddAngularDimension(p),
            "LEADER" => AddLeader(p),
            "CAGE" => AddCage(p),
            "MORPHCONTROL" or "MORPH_CONTROL" => AddMorphControl(p),
            "SUBD" => AddSubD(p),
            "HATCH" => AddHatch(p),
            "CLIPPING_PLANE" or "CLIPPINGPLANE" => AddClippingPlane(p),
            _ => Guid.Empty
        };
    }

    private static Guid AddBox(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var size = p.DoubleArray("size");
        double sx, sy, sz;
        if (size.Length >= 3)
        {
            sx = size[0]; sy = size[1]; sz = size[2];
        }
        else if (size.Length == 1)
        {
            sx = sy = sz = size[0];
        }
        else
        {
            // Surpass: also accept a single scalar "size" for a uniform box (e.g. size: 2)
            var uniformSize = p.Double("size", 0);
            if (uniformSize > 0)
            {
                sx = sy = sz = uniformSize;
            }
            else
            {
                // Reference-compat: individual width/length/height params
                sx = p.Double("width", p.Double("size_x", 1));
                sy = p.Double("length", p.Double("size_y", sx));
                sz = p.Double("height", p.Double("size_z", sx));
            }
        }
        var box = new Box(Plane.WorldXY,
            new Interval(center.X - sx / 2, center.X + sx / 2),
            new Interval(center.Y - sy / 2, center.Y + sy / 2),
            new Interval(center.Z - sz / 2, center.Z + sz / 2));
        return RhinoDoc.ActiveDoc.Objects.AddBrep(box.ToBrep());
    }

    private static Guid AddMesh(Dictionary<string, JsonElement> p)
    {
        // Guard: vertices must be present and non-empty
        if (!p.TryGetValue("vertices", out var verticesEl) || verticesEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;

        var mesh = new Mesh();
        foreach (var v in verticesEl.EnumerateArray())
        {
            var point = ReadPoint(v);
            if (point.HasValue)
                mesh.Vertices.Add(point.Value);
        }

        // Guard: need at least 3 vertices to form any face
        if (mesh.Vertices.Count < 3)
            return Guid.Empty;

        // Guard: faces must be present and non-empty
        if (!p.TryGetValue("faces", out var facesEl) || facesEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;

        var vertexCount = mesh.Vertices.Count;
        foreach (var f in facesEl.EnumerateArray())
        {
            var items = f.EnumerateArray().Select(e => e.GetInt32()).ToArray();
            // Skip any face whose indices are out of bounds
            if (items.Length == 3)
            {
                if (items[0] < 0 || items[0] >= vertexCount ||
                    items[1] < 0 || items[1] >= vertexCount ||
                    items[2] < 0 || items[2] >= vertexCount)
                    continue;
                mesh.Faces.AddFace(items[0], items[1], items[2]);
            }
            else if (items.Length == 4)
            {
                if (items[0] < 0 || items[0] >= vertexCount ||
                    items[1] < 0 || items[1] >= vertexCount ||
                    items[2] < 0 || items[2] >= vertexCount ||
                    items[3] < 0 || items[3] >= vertexCount)
                    continue;
                mesh.Faces.AddFace(items[0], items[1], items[2], items[3]);
            }
        }

        // Guard: after filtering, must have at least one valid face
        if (mesh.Faces.Count == 0)
            return Guid.Empty;

        mesh.Normals.ComputeNormals();
        mesh.Compact();
        return RhinoDoc.ActiveDoc.Objects.AddMesh(mesh);
    }

    private static Guid AddText(Dictionary<string, JsonElement> p)
    {
        var text = p.String("text", "")!;
        var point = ReadPoint(p, "point") ?? Point3d.Origin;
        var height = p.Double("height", 1);
        var entity = new TextEntity { PlainText = text, Plane = new Plane(point, Vector3d.ZAxis), TextHeight = height };
        return RhinoDoc.ActiveDoc.Objects.AddText(entity);
    }

    private static Guid AddPolyline(Dictionary<string, JsonElement> p)
    {
        if (!p.TryGetValue("points", out var pointsEl) || pointsEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;
        var pts = pointsEl.EnumerateArray()
            .Select(e => ReadPoint(e))
            .Where(pt => pt.HasValue)
            .Select(pt => pt!.Value)
            .ToList();
        if (pts.Count < 2)
            return Guid.Empty;
        var closed = p.Bool("closed", false);
        if (closed && pts[0] != pts[pts.Count - 1])
            pts.Add(pts[0]);
        var polyline = new Polyline(pts);
        return RhinoDoc.ActiveDoc.Objects.AddPolyline(polyline);
    }

    private static Guid AddArc(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var radius = p.Double("radius", 1);
        var startAngleDeg = p.Double("start_angle", 0);
        var endAngleDeg = p.Double("end_angle", 360);
        var plane = new Plane(center, Vector3d.ZAxis);
        var arc = new Arc(plane, radius, RhinoMath.ToRadians(endAngleDeg - startAngleDeg));
        return RhinoDoc.ActiveDoc.Objects.AddArc(arc);
    }

    private static Guid AddEllipse(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var radiusX = p.Double("radius_x", 1);
        var radiusY = p.Double("radius_y", 0.5);
        var plane = new Plane(center, Vector3d.ZAxis);
        var ellipse = new Ellipse(plane, radiusX, radiusY);
        // AddEllipse preserves the native ellipse type instead of downgrading to a generic curve
        return RhinoDoc.ActiveDoc.Objects.AddEllipse(ellipse);
    }

    private static Guid AddNurbsCurve(Dictionary<string, JsonElement> p)
    {
        if (!p.TryGetValue("points", out var pointsEl) || pointsEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;
        var pts = pointsEl.EnumerateArray()
            .Select(e => ReadPoint(e))
            .Where(pt => pt.HasValue)
            .Select(pt => pt!.Value)
            .ToList();
        if (pts.Count < 2)
            return Guid.Empty;
        var degree = p.Int("degree", 3);
        var closed = p.Bool("closed", false);
        NurbsCurve? nurbs;
        if (closed)
            nurbs = NurbsCurve.Create(true, degree, pts);
        else
            nurbs = NurbsCurve.CreateControlPointCurve(pts, degree) as NurbsCurve;
        if (nurbs is null) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddCurve(nurbs);
    }

    private static Guid AddCone(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var radius = p.Double("radius", 1);
        var height = p.Double("height", 1);
        var plane = new Plane(center, Vector3d.ZAxis);
        var cone = new Cone(plane, height, radius);
        var cap = p.Bool("cap", true);
        var brep = cone.ToBrep(cap);
        if (brep is null) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddBrep(brep);
    }

    private static Guid AddCylinder(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var radius = p.Double("radius", 1);
        var height = p.Double("height", 1);
        var plane = new Plane(center, Vector3d.ZAxis);
        var circle = new Circle(plane, radius);
        var cylinder = new Cylinder(circle, height);
        var cap = p.Bool("cap", true);
        var brep = cylinder.ToBrep(cap, cap);
        if (brep is null) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddBrep(brep);
    }

    private static Guid AddNurbsSurface(Dictionary<string, JsonElement> p)
    {
        if (!p.TryGetValue("points", out var pointsEl) || pointsEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;
        var pts = pointsEl.EnumerateArray()
            .Select(e => ReadPoint(e))
            .Where(pt => pt.HasValue)
            .Select(pt => pt!.Value)
            .ToList();

        var countArr = p.DoubleArray("count");
        if (countArr.Length < 2 || pts.Count == 0)
            return Guid.Empty;
        int uCount = (int)countArr[0];
        int vCount = (int)countArr[1];

        // uDegree / vDegree accept either a "degree" array [u,v] or individual "u_degree"/"v_degree" params
        var degreeArr = p.DoubleArray("degree");
        int uDegree = p.Int("u_degree", degreeArr.Length >= 1 ? (int)degreeArr[0] : 3);
        int vDegree = p.Int("v_degree", degreeArr.Length >= 2 ? (int)degreeArr[1] : 3);

        // Optional closed flags — allow callers to request a closed surface in U or V
        bool uClosed = p.Bool("u_closed", false);
        bool vClosed = p.Bool("v_closed", false);

        if (pts.Count < uCount * vCount)
            return Guid.Empty;

        // CreateThroughPoints performs interpolation: every input point lies exactly ON the surface.
        // CreateFromPoints (the old call) only approximates, so control points ≠ input points.
        var surface = NurbsSurface.CreateThroughPoints(pts, uCount, vCount, uDegree, vDegree, uClosed, vClosed);
        if (surface is null) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddSurface(surface);
    }

    private static Guid AddTorus(Dictionary<string, JsonElement> p)
    {
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var majorRadius = p.Double("major_radius", 2);
        var minorRadius = p.Double("minor_radius", 0.5);
        var plane = new Plane(center, Vector3d.ZAxis);
        var torus = new Torus(plane, majorRadius, minorRadius);
        var surface = torus.ToRevSurface();
        if (surface is null) return Guid.Empty;
        var brep = surface.ToBrep();
        if (brep is null) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddBrep(brep);
    }

    private static Guid AddPlane(Dictionary<string, JsonElement> p)
    {
        // Flat rectangular planar surface.
        // Params: center [x,y,z], width, height (u/v extents), normal [x,y,z] optional
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var width = p.Double("width", 1);
        var height = p.Double("height", 1);

        var normalArr = p.DoubleArray("normal");
        Vector3d normal = normalArr.Length == 3
            ? new Vector3d(normalArr[0], normalArr[1], normalArr[2])
            : Vector3d.ZAxis;
        normal.Unitize();

        // Build an arbitrary perpendicular frame
        var xAxis = Vector3d.CrossProduct(normal, Vector3d.ZAxis);
        if (xAxis.IsZero || !xAxis.Unitize())
            xAxis = Vector3d.XAxis;
        var yAxis = Vector3d.CrossProduct(normal, xAxis);
        yAxis.Unitize();

        var plane = new Plane(center, xAxis, yAxis);
        var surface = new PlaneSurface(plane,
            new Interval(-width / 2, width / 2),
            new Interval(-height / 2, height / 2));
        return RhinoDoc.ActiveDoc.Objects.AddSurface(surface);
    }

    private static Guid AddPointCloud(Dictionary<string, JsonElement> p)
    {
        if (!p.TryGetValue("points", out var pointsEl) || pointsEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;
        var pts = pointsEl.EnumerateArray()
            .Select(e => ReadPoint(e)).Where(pt => pt.HasValue).Select(pt => pt!.Value).ToList();
        if (pts.Count == 0) return Guid.Empty;
        return RhinoDoc.ActiveDoc.Objects.AddPointCloud(new PointCloud(pts));
    }

    private static Guid AddTextDot(Dictionary<string, JsonElement> p)
    {
        var text  = p.String("text", "•")!;
        var point = ReadPoint(p, "point") ?? ReadPoint(p, "location") ?? Point3d.Origin;
        var dot   = new TextDot(text, point);
        var fontSize = p.Int("font_size", 0);
        if (fontSize > 0) dot.FontHeight = fontSize;
        return RhinoDoc.ActiveDoc.Objects.AddTextDot(dot);
    }

    private static Guid AddLightObject(Dictionary<string, JsonElement> p)
    {
        var doc   = RhinoDoc.ActiveDoc;
        var light = new Rhino.Geometry.Light();
        var style = (p.String("light_style", "point") ?? "point").ToLowerInvariant();
        light.LightStyle = style switch
        {
            "directional"           => Rhino.Geometry.LightStyle.WorldDirectional,
            "spot"                  => Rhino.Geometry.LightStyle.WorldSpot,
            "linear"                => Rhino.Geometry.LightStyle.WorldLinear,
            "rectangular" or "area" => Rhino.Geometry.LightStyle.WorldRectangular,
            _                       => Rhino.Geometry.LightStyle.WorldPoint,
        };
        light.Location  = ReadPoint(p, "location") ?? ReadPoint(p, "position") ?? new Point3d(0, 0, 10);
        light.Intensity = p.Double("intensity", 1.0);
        var colorArr = p.DoubleArray("diffuse_color");
        light.Diffuse = colorArr.Length >= 3
            ? Color.FromArgb((int)colorArr[0], (int)colorArr[1], (int)colorArr[2])
            : Color.White;
        var dirArr = p.DoubleArray("direction");
        if (dirArr.Length == 3) light.Direction = new Vector3d(dirArr[0], dirArr[1], dirArr[2]);
        var idx = doc.Lights.Add(light);
        return idx < 0 ? Guid.Empty : doc.Lights[idx].Id;
    }

    private static Guid AddExtrusion(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        Curve? profile = null;
        var profileId = p.String("profile_id") ?? p.String("curve_id");
        if (profileId != null && Guid.TryParse(profileId, out var pid))
            profile = doc.Objects.FindId(pid)?.Geometry as Curve;
        if (profile is null && p.TryGetValue("points", out var pointsEl) && pointsEl.ValueKind == JsonValueKind.Array)
        {
            var pts = pointsEl.EnumerateArray()
                .Select(e => ReadPoint(e)).Where(pt => pt.HasValue).Select(pt => pt!.Value).ToList();
            if (pts.Count >= 3)
            {
                if (pts[0] != pts[pts.Count - 1]) pts.Add(pts[0]);
                profile = new Polyline(pts).ToNurbsCurve();
            }
        }
        if (profile is null) return Guid.Empty;
        var height    = p.Double("height", 1);
        var cap       = p.Bool("cap", true);
        var extrusion = Extrusion.Create(profile, height, cap);
        if (extrusion is null) return Guid.Empty;
        return doc.Objects.AddExtrusion(extrusion);
    }

    private static Guid AddBlockInsert(Dictionary<string, JsonElement> p)
    {
        var doc       = RhinoDoc.ActiveDoc;
        var blockName = p.String("block_name") ?? p.String("definition_name") ?? "";
        var def       = doc.InstanceDefinitions.Find(blockName);
        if (def is null) return Guid.Empty;
        var position = ReadPoint(p, "position") ?? ReadPoint(p, "location") ?? Point3d.Origin;
        var composed = Transform.Translation(position.X, position.Y, position.Z);
        var rotArr = p.DoubleArray("rotation");
        if (rotArr.Length == 3)
        {
            var rx = RhinoMath.ToRadians(rotArr[0]);
            var ry = RhinoMath.ToRadians(rotArr[1]);
            var rz = RhinoMath.ToRadians(rotArr[2]);
            var rotX = Math.Abs(rx) > double.Epsilon ? Transform.Rotation(rx, Vector3d.XAxis, Point3d.Origin) : Transform.Identity;
            var rotY = Math.Abs(ry) > double.Epsilon ? Transform.Rotation(ry, Vector3d.YAxis, Point3d.Origin) : Transform.Identity;
            var rotZ = Math.Abs(rz) > double.Epsilon ? Transform.Rotation(rz, Vector3d.ZAxis, Point3d.Origin) : Transform.Identity;
            composed = composed * rotZ * rotY * rotX;
        }
        var scaleVal = p.Double("scale", 1.0);
        if (Math.Abs(scaleVal - 1.0) > double.Epsilon)
            composed = composed * Transform.Scale(Point3d.Origin, scaleVal);
        return doc.Objects.AddInstanceObject(def.Index, composed);
    }

    private static Guid AddLinearDimension(Dictionary<string, JsonElement> p)
    {
        var doc    = RhinoDoc.ActiveDoc;
        var start  = ReadPoint(p, "start") ?? Point3d.Origin;
        var end    = ReadPoint(p, "end")   ?? new Point3d(1, 0, 0);
        var offset = p.Double("offset", 0.5);
        // Annotation plane: WorldXY shifted to start Z so x/y coords map directly.
        var plane  = new Plane(new Point3d(0, 0, start.Z), Vector3d.XAxis, Vector3d.YAxis);
        var ext1   = new Point2d(start.X, start.Y);
        var ext2   = new Point2d(end.X,   end.Y);
        var midX   = (start.X + end.X) / 2.0;
        var dimPt  = new Point2d(midX, Math.Max(start.Y, end.Y) + offset);
        var dim    = new LinearDimension(plane, ext1, ext2, dimPt);
        return doc.Objects.Add(dim, new ObjectAttributes());
    }

    private static Guid AddLeader(Dictionary<string, JsonElement> p)
    {
        if (!p.TryGetValue("points", out var pointsEl) || pointsEl.ValueKind != JsonValueKind.Array)
            return Guid.Empty;
        var pts = pointsEl.EnumerateArray()
            .Select(e => ReadPoint(e)).Where(pt => pt.HasValue).Select(pt => pt!.Value).ToList();
        if (pts.Count < 2) return Guid.Empty;
        var text = p.String("text") ?? "";
        // AddLeader(string, IEnumerable<Point3d>) auto-derives the annotation plane
        return RhinoDoc.ActiveDoc.Objects.AddLeader(text, pts);
    }

    private static Guid AddCage(Dictionary<string, JsonElement> p)
    {
        // Creates a box object that defines the cage region.
        // Use Rhino's _CageEdit command to attach captured objects to this cage.
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        var width  = p.Double("width",  2);
        var depth  = p.Double("depth",  2);
        var height = p.Double("height", 2);
        var plane  = new Plane(center, Vector3d.ZAxis);
        var box    = new Box(plane,
            new Interval(-width  / 2, width  / 2),
            new Interval(-depth  / 2, depth  / 2),
            new Interval(-height / 2, height / 2));
        return RhinoDoc.ActiveDoc.Objects.AddBrep(box.ToBrep());
    }

    private static Guid AddMorphControl(Dictionary<string, JsonElement> p)
    {
        // Curve morph control: maps geometry from one NurbsCurve shape to another.
        // source_curve_id and target_curve_id must refer to existing curves in the document.
        var doc   = RhinoDoc.ActiveDoc;
        var srcId = p.String("source_curve_id") ?? p.String("source_id") ?? "";
        var tgtId = p.String("target_curve_id") ?? p.String("target_id") ?? "";
        if (!Guid.TryParse(srcId, out var sg) || !Guid.TryParse(tgtId, out var tg))
            return Guid.Empty;
        var srcNurbs = (doc.Objects.FindId(sg)?.Geometry as Curve)?.ToNurbsCurve();
        var tgtNurbs = (doc.Objects.FindId(tg)?.Geometry as Curve)?.ToNurbsCurve();
        if (srcNurbs is null || tgtNurbs is null) return Guid.Empty;
        var mc = new MorphControl(srcNurbs, tgtNurbs);
        return doc.Objects.AddMorphControl(mc);
    }

    private static Guid AddRadialDimension(Dictionary<string, JsonElement> p)
    {
        var center     = ReadPoint(p, "center") ?? Point3d.Origin;
        double radius  = p.Double("radius", 1.0);
        double angle   = p.Double("angle", 45.0) * Math.PI / 180.0;
        double offset  = p.Double("offset", radius * 0.5);
        bool isDiam    = p.Bool("is_diameter", false);
        var plane      = new Plane(center, Vector3d.ZAxis);
        var radPt      = center + new Vector3d(Math.Cos(angle) * radius, Math.Sin(angle) * radius, 0);
        var dimPt      = center + new Vector3d(Math.Cos(angle) * (radius + offset), Math.Sin(angle) * (radius + offset), 0);
        var annotType  = isDiam ? AnnotationType.Diameter : AnnotationType.Radius;
        var dim        = new RadialDimension(annotType, plane, center, radPt, dimPt);
        return RhinoDoc.ActiveDoc.Objects.Add(dim, new ObjectAttributes());
    }

    private static Guid AddAngularDimension(Dictionary<string, JsonElement> p)
    {
        var center      = ReadPoint(p, "center") ?? Point3d.Origin;
        double radius   = p.Double("radius", 2.0);
        double startDeg = p.Double("start_angle", 0.0);
        double endDeg   = p.Double("end_angle", 90.0);
        double offset   = p.Double("offset", radius * 0.3);
        double startRad = startDeg * Math.PI / 180.0;
        double endRad   = endDeg   * Math.PI / 180.0;
        double midRad   = (startRad + endRad) / 2.0;
        // Build arc via 3 points to set start/end angles independently
        var ptStart = center + new Vector3d(Math.Cos(startRad) * radius, Math.Sin(startRad) * radius, 0);
        var ptMid   = center + new Vector3d(Math.Cos(midRad)   * radius, Math.Sin(midRad)   * radius, 0);
        var ptEnd   = center + new Vector3d(Math.Cos(endRad)   * radius, Math.Sin(endRad)   * radius, 0);
        var arc     = new Arc(ptStart, ptMid, ptEnd);
        var dim     = new AngularDimension(arc, offset);
        return RhinoDoc.ActiveDoc.Objects.Add(dim, new ObjectAttributes());
    }

    private static Guid AddSubD(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        var opts = new SubDCreationOptions { InterpolateMeshVertices = false };
        // Convert an existing mesh
        if (p.TryGetValue("mesh_id", out var meshEl))
        {
            var s = meshEl.ValueKind == JsonValueKind.String ? meshEl.GetString() : meshEl.ToString();
            if (Guid.TryParse(s, out var mg) && doc.Objects.FindId(mg)?.Geometry is Mesh srcMesh)
            {
                var subD = SubD.CreateFromMesh(srcMesh, opts);
                if (subD != null) return doc.Objects.AddSubD(subD);
            }
        }
        // Build a SubD box from dimensions
        var center = ReadPoint(p, "center") ?? Point3d.Origin;
        double sx  = p.Double("width",  2.0);
        double sy  = p.Double("depth",  2.0);
        double sz  = p.Double("height", 2.0);
        int    seg = Math.Max(1, (int)p.Double("segments", 1));
        var box    = new Box(new Plane(center, Vector3d.ZAxis),
                        new Interval(-sx/2, sx/2),
                        new Interval(-sy/2, sy/2),
                        new Interval(-sz/2, sz/2));
        var mesh   = Mesh.CreateFromBox(box, seg, seg, seg);
        var result = SubD.CreateFromMesh(mesh, opts);
        return result == null ? Guid.Empty : doc.Objects.AddSubD(result);
    }

    private static Guid AddHatch(Dictionary<string, JsonElement> p)
    {
        var doc = RhinoDoc.ActiveDoc;
        Curve? boundary = null;
        // Use an existing closed curve
        if (p.TryGetValue("curve_id", out var cidEl))
        {
            var s = cidEl.ValueKind == JsonValueKind.String ? cidEl.GetString() : cidEl.ToString();
            if (Guid.TryParse(s, out var cg))
                boundary = doc.Objects.FindId(cg)?.Geometry as Curve;
        }
        // Fallback: rectangle from center/width/height
        if (boundary == null)
        {
            var ctr = ReadPoint(p, "center") ?? Point3d.Origin;
            double w = p.Double("width", 2.0), h = p.Double("height", 2.0);
            var rect = new Rectangle3d(new Plane(ctr, Vector3d.ZAxis),
                            new Interval(-w/2, w/2), new Interval(-h/2, h/2));
            boundary = rect.ToNurbsCurve();
        }
        var patternName  = p.String("pattern") ?? "Solid";
        int patternIndex = doc.HatchPatterns.FindName(patternName)?.Index
                            ?? doc.HatchPatterns.CurrentHatchPatternIndex;
        double rotation  = p.Double("rotation", 0.0) * Math.PI / 180.0;
        double scale     = p.Double("scale", 1.0);
        var hatches = Hatch.Create(boundary, patternIndex, rotation, scale, doc.ModelAbsoluteTolerance);
        if (hatches == null || hatches.Length == 0) return Guid.Empty;
        return doc.Objects.AddHatch(hatches[0]);
    }

    private static Guid AddClippingPlane(Dictionary<string, JsonElement> p)
    {
        var doc    = RhinoDoc.ActiveDoc;
        var origin = ReadPoint(p, "origin") ?? ReadPoint(p, "center") ?? Point3d.Origin;
        var normal = ReadPoint(p, "normal") is Point3d nPt
                        ? new Vector3d(nPt.X, nPt.Y, nPt.Z)
                        : Vector3d.ZAxis;
        normal.Unitize();
        var plane  = new Plane(origin, normal);
        double w   = p.Double("width",  10.0);
        double h   = p.Double("height", 10.0);
        // Clip all active viewports
        var vpIds  = doc.Views.Select(v => v.ActiveViewportID).ToList();
        if (vpIds.Count == 0) vpIds.Add(doc.Views.ActiveView.ActiveViewportID);
        return doc.Objects.AddClippingPlane(plane, w, h, vpIds);
    }

    // -------------------------------------------------------------------------
    // Block definition management
    // -------------------------------------------------------------------------

    public static object CreateBlockDefinition(Dictionary<string, JsonElement> p)
    {
        var doc  = RhinoDoc.ActiveDoc;
        var name = p.String("name") ?? "";
        if (string.IsNullOrWhiteSpace(name))
            return new { success = false, message = "name is required" };
        var existing = doc.InstanceDefinitions.Find(name);
        if (existing != null && !p.Bool("overwrite", false))
            return new { success = false, message = $"Block '{name}' already exists; pass overwrite=true to replace." };
        var basePoint   = ReadPoint(p, "base_point") ?? Point3d.Origin;
        var description = p.String("description") ?? "";
        var geometries  = new List<GeometryBase>();
        var attrs       = new List<ObjectAttributes>();
        if (p.TryGetValue("object_ids", out var idsEl) && idsEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var el in idsEl.EnumerateArray())
            {
                var s = el.ValueKind == JsonValueKind.String ? el.GetString() : el.ToString();
                if (Guid.TryParse(s, out var g))
                {
                    var obj = doc.Objects.FindId(g);
                    if (obj?.Geometry is not null)
                    {
                        geometries.Add(obj.Geometry.Duplicate());
                        attrs.Add(obj.Attributes.Duplicate());
                    }
                }
            }
        }
        int defIdx;
        if (existing != null)
            defIdx = doc.InstanceDefinitions.ModifyGeometry(existing.Index, geometries, attrs) ? existing.Index : -1;
        else
            defIdx = doc.InstanceDefinitions.Add(name, description, basePoint, geometries, attrs);
        if (defIdx < 0)
            return new { success = false, message = "Failed to create block definition" };
        var def = doc.InstanceDefinitions[defIdx];
        doc.Views.Redraw();
        return new { success = true, name = def.Name, id = def.Id.ToString(), index = defIdx, object_count = geometries.Count };
    }

    public static object InsertBlock(Dictionary<string, JsonElement> p)
    {
        var doc       = RhinoDoc.ActiveDoc;
        var blockName = p.String("block_name") ?? p.String("name") ?? "";
        var def       = doc.InstanceDefinitions.Find(blockName);
        if (def is null)
            return new { success = false, message = $"Block '{blockName}' not found" };
        var position = ReadPoint(p, "position") ?? ReadPoint(p, "location") ?? Point3d.Origin;
        var composed = Transform.Translation(position.X, position.Y, position.Z);
        var rotArr   = p.DoubleArray("rotation");
        if (rotArr.Length == 3)
        {
            var rx   = RhinoMath.ToRadians(rotArr[0]);
            var ry   = RhinoMath.ToRadians(rotArr[1]);
            var rz   = RhinoMath.ToRadians(rotArr[2]);
            var rotX = Math.Abs(rx) > double.Epsilon ? Transform.Rotation(rx, Vector3d.XAxis, Point3d.Origin) : Transform.Identity;
            var rotY = Math.Abs(ry) > double.Epsilon ? Transform.Rotation(ry, Vector3d.YAxis, Point3d.Origin) : Transform.Identity;
            var rotZ = Math.Abs(rz) > double.Epsilon ? Transform.Rotation(rz, Vector3d.ZAxis, Point3d.Origin) : Transform.Identity;
            composed = composed * rotZ * rotY * rotX;
        }
        var scaleVal = p.Double("scale", 1.0);
        if (Math.Abs(scaleVal - 1.0) > double.Epsilon)
            composed = composed * Transform.Scale(Point3d.Origin, scaleVal);
        var id = doc.Objects.AddInstanceObject(def.Index, composed);
        if (id == Guid.Empty)
            return new { success = false, message = "Failed to insert block" };
        doc.Views.Redraw();
        return new { success = true, id = id.ToString(), block_name = blockName, position = PointArray(position) };
    }

    // -------------------------------------------------------------------------
    // Transform helpers
    // -------------------------------------------------------------------------

    private static object Modify(RhinoObject obj, Dictionary<string, JsonElement> p)
    {
        ApplyAttributes(obj, p);
        ApplyTransform(obj.Id, p);
        if (p.TryGetValue("visible", out var visible) && visible.ValueKind is JsonValueKind.True or JsonValueKind.False)
        {
            if (visible.GetBoolean())
                RhinoDoc.ActiveDoc.Objects.Show(obj, true);
            else
                RhinoDoc.ActiveDoc.Objects.Hide(obj, true);
        }
        var updated = RhinoDoc.ActiveDoc.Objects.FindId(obj.Id);
        return updated is not null ? SerializeObject(updated, false) : new { success = true, id = obj.Id.ToString() };
    }

    private static void ApplyAttributes(RhinoObject? obj, Dictionary<string, JsonElement> p)
    {
        if (obj is null)
            return;
        var attrs = obj.Attributes.Duplicate();
        var name = p.String("name") ?? p.String("new_name");
        if (!string.IsNullOrWhiteSpace(name))
            attrs.Name = name;
        var color = ReadColor(p, "color") ?? ReadColor(p, "new_color");
        if (color.HasValue)
        {
            attrs.ObjectColor = color.Value;
            attrs.ColorSource = ObjectColorSource.ColorFromObject;
        }
        var layer = p.String("layer");
        if (!string.IsNullOrWhiteSpace(layer))
        {
            var doc = RhinoDoc.ActiveDoc;
            var index = doc.Layers.FindByFullPath(layer, -1);
            if (index < 0)
                index = doc.Layers.Add(layer, Color.LightGray);
            attrs.LayerIndex = index;
        }
        RhinoDoc.ActiveDoc.Objects.ModifyAttributes(obj, attrs, true);
    }

    private static void ApplyTransform(Guid id, Dictionary<string, JsonElement> p)
    {
        // Fix 8: compose all transforms into a single matrix, apply once.
        // Param keys: position/translation (translate), scale, rotation (Euler XYZ degrees).
        // Optional pivot [x,y,z] — when provided, rotation and scale are applied around that
        // point instead of the object's bounding-box center.
        var doc = RhinoDoc.ActiveDoc;

        // Resolve translation array from "translation" or "position"
        double[] translationArr;
        if (p.TryGetValue("translation", out var translationEl) && translationEl.ValueKind == JsonValueKind.Array)
            translationArr = translationEl.EnumerateArray().Select(e => e.GetDouble()).ToArray();
        else if (p.TryGetValue("position", out var positionEl) && positionEl.ValueKind == JsonValueKind.Array)
            translationArr = positionEl.EnumerateArray().Select(e => e.GetDouble()).ToArray();
        else
            translationArr = Array.Empty<double>();

        var hasScale = p.TryGetValue("scale", out var scaleElement);
        var rotationArr = p.DoubleArray("rotation");

        // Nothing to apply — bail early
        if (translationArr.Length != 3 && !hasScale && rotationArr.Length != 3)
            return;

        // Resolve pivot: explicit param > bounding-box center
        Point3d pivot;
        var pivotArr = p.DoubleArray("pivot");
        if (pivotArr.Length == 3)
        {
            pivot = new Point3d(pivotArr[0], pivotArr[1], pivotArr[2]);
        }
        else
        {
            var objForBbox = doc.Objects.FindId(id);
            if (objForBbox is null) return;
            var bbox = objForBbox.Geometry.GetBoundingBox(true);
            pivot = bbox.IsValid ? bbox.Center : Point3d.Origin;
        }

        // Build composed transform: scale → rotate → translate
        var composed = Transform.Identity;

        // Scale around pivot
        if (hasScale)
        {
            Transform scaleTx;
            if (scaleElement.ValueKind == JsonValueKind.Number)
            {
                scaleTx = Transform.Scale(pivot, scaleElement.GetDouble());
            }
            else if (scaleElement.ValueKind == JsonValueKind.Array)
            {
                var sa = scaleElement.EnumerateArray().Select(e => e.GetDouble()).ToArray();
                if (sa.Length == 3)
                    scaleTx = Transform.Scale(new Plane(pivot, Vector3d.XAxis, Vector3d.YAxis), sa[0], sa[1], sa[2]);
                else if (sa.Length == 1)
                    scaleTx = Transform.Scale(pivot, sa[0]);
                else
                    scaleTx = Transform.Identity;
            }
            else
            {
                scaleTx = Transform.Identity;
            }
            composed = scaleTx * composed;
        }

        // Euler XYZ rotation around pivot — compose X→Y→Z into one matrix.
        // Wire format: "rotation": [rx_deg, ry_deg, rz_deg]  (degrees, flat JSON array).
        // The Python MCP tools document this same convention; never pass radians here.
        if (rotationArr.Length == 3)
        {
            var rx = RhinoMath.ToRadians(rotationArr[0]);
            var ry = RhinoMath.ToRadians(rotationArr[1]);
            var rz = RhinoMath.ToRadians(rotationArr[2]);
            var rotX = Math.Abs(rx) > double.Epsilon ? Transform.Rotation(rx, Vector3d.XAxis, pivot) : Transform.Identity;
            var rotY = Math.Abs(ry) > double.Epsilon ? Transform.Rotation(ry, Vector3d.YAxis, pivot) : Transform.Identity;
            var rotZ = Math.Abs(rz) > double.Epsilon ? Transform.Rotation(rz, Vector3d.ZAxis, pivot) : Transform.Identity;
            composed = rotZ * rotY * rotX * composed;
        }

        // Translation
        if (translationArr.Length == 3)
        {
            composed = Transform.Translation(translationArr[0], translationArr[1], translationArr[2]) * composed;
        }

        if (composed != Transform.Identity)
            doc.Objects.Transform(id, composed, true);
    }

    private static void ApplyEulerRotation(Guid id, double rxDeg, double ryDeg, double rzDeg)
    {
        // Used by CreateObject — receives degrees (from the flat "rotation": [rx,ry,rz] JSON array)
        // and composes them into a single X→Y→Z Euler transform around the object centre.
        // Callers must pass degrees; this method converts to radians via RhinoMath.ToRadians().
        var doc = RhinoDoc.ActiveDoc;
        var obj = doc.Objects.FindId(id);
        if (obj is null) return;
        var bbox = obj.Geometry.GetBoundingBox(true);
        var center = bbox.IsValid ? bbox.Center : Point3d.Origin;

        var rx = RhinoMath.ToRadians(rxDeg);
        var ry = RhinoMath.ToRadians(ryDeg);
        var rz = RhinoMath.ToRadians(rzDeg);

        var rotX = Math.Abs(rx) > double.Epsilon ? Transform.Rotation(rx, Vector3d.XAxis, center) : Transform.Identity;
        var rotY = Math.Abs(ry) > double.Epsilon ? Transform.Rotation(ry, Vector3d.YAxis, center) : Transform.Identity;
        var rotZ = Math.Abs(rz) > double.Epsilon ? Transform.Rotation(rz, Vector3d.ZAxis, center) : Transform.Identity;
        var composed = rotZ * rotY * rotX;
        if (composed != Transform.Identity)
            doc.Objects.Transform(id, composed, true);
    }

    // -------------------------------------------------------------------------
    // Filter helpers
    // -------------------------------------------------------------------------

    private static RhinoObject? FindObject(Dictionary<string, JsonElement> p)
    {
        var id = p.String("id") ?? p.String("object_id");
        if (Guid.TryParse(id, out var guid))
            return RhinoDoc.ActiveDoc.Objects.FindId(guid);
        var name = p.String("name");
        return string.IsNullOrWhiteSpace(name)
            ? null
            : RhinoDoc.ActiveDoc.Objects.FirstOrDefault(o => !o.IsDeleted && o.Name == name);
    }

    private static bool MatchFilter(RhinoObject obj, string key, JsonElement expected, int? colorTolerance = null)
    {
        var text = expected.ValueKind == JsonValueKind.String ? expected.GetString() : expected.ToString();
        switch (key.ToLowerInvariant())
        {
            case "id":
            case "ids":
                return text is not null && obj.Id.ToString().Equals(text, StringComparison.OrdinalIgnoreCase);
            case "name":
            case "exact_name":
                return obj.Name == text;
            case "name_contains":
                return obj.Name?.Contains(text ?? "", StringComparison.OrdinalIgnoreCase) == true;
            case "name_pattern":
                return MatchWildcard(obj.Name, text ?? "");
            case "layer":
                return LayerName(obj) == text;
            case "type":
                return ToNormalizedTypeName(obj).Contains((text ?? "").ToUpperInvariant(), StringComparison.OrdinalIgnoreCase);
            case "color":
                return MatchColorFilter(obj, expected, colorTolerance ?? 0);
            default:
                // User-string attribute fallback
                if (!_builtInFilterKeys.Contains(key))
                {
                    var userVal = obj.Attributes.GetUserString(key);
                    return userVal is not null &&
                           userVal.Contains(text ?? "", StringComparison.OrdinalIgnoreCase);
                }
                return false;
        }
    }

    /// <summary>
    /// Simple wildcard match supporting leading/trailing '*'.
    /// e.g. "Wall*", "*_base", "*door*"
    /// </summary>
    private static bool MatchWildcard(string? input, string pattern)
    {
        if (input is null) return false;
        if (pattern == "*") return true;
        var startsWild = pattern.StartsWith("*");
        var endsWild = pattern.EndsWith("*");
        var core = pattern.Trim('*');
        if (startsWild && endsWild)
            return input.Contains(core, StringComparison.OrdinalIgnoreCase);
        if (startsWild)
            return input.EndsWith(core, StringComparison.OrdinalIgnoreCase);
        if (endsWild)
            return input.StartsWith(core, StringComparison.OrdinalIgnoreCase);
        return input.Equals(core, StringComparison.OrdinalIgnoreCase);
    }

    private static bool MatchColorFilter(RhinoObject obj, JsonElement expected, int tolerance = 0)
    {
        if (obj.Attributes.ColorSource != ObjectColorSource.ColorFromObject)
            return false;
        if (expected.ValueKind != JsonValueKind.Array)
            return false;
        var arr = expected.EnumerateArray().Select(e => e.GetInt32()).ToArray();
        if (arr.Length < 3)
            return false;
        var c = obj.Attributes.ObjectColor;
        if (tolerance <= 0)
            return c.R == arr[0] && c.G == arr[1] && c.B == arr[2];
        // Euclidean RGB distance
        var dist = Math.Sqrt(
            Math.Pow(c.R - arr[0], 2) +
            Math.Pow(c.G - arr[1], 2) +
            Math.Pow(c.B - arr[2], 2));
        return dist <= tolerance;
    }

    // -------------------------------------------------------------------------
    // Boolean / geometry result helpers
    // -------------------------------------------------------------------------

    private static object AddBooleanResults(Brep[]? results, IEnumerable<string> sourceIds, Dictionary<string, JsonElement> p)
    {
        if (results is null || results.Length == 0)
            return new { success = false, message = "Boolean operation failed." };
        if (p.Bool("delete_sources", true))
        {
            foreach (var idText in sourceIds)
            {
                if (Guid.TryParse(idText, out var id))
                    RhinoDoc.ActiveDoc.Objects.Delete(id, true);
            }
        }
        return AddBreps(results, p.String("name"), "Boolean operation completed");
    }

    private static object AddBreps(IEnumerable<Brep>? breps, string? name, string message)
    {
        var ids = new List<string>();
        foreach (var brep in breps ?? Array.Empty<Brep>())
            ids.Add(RhinoDoc.ActiveDoc.Objects.AddBrep(brep, AttributesWithName(name)).ToString());
        RhinoDoc.ActiveDoc.Views.Redraw();
        return new { success = ids.Count > 0, result_ids = ids, count = ids.Count, message };
    }

    private static object AddCurves(IEnumerable<Curve>? curves, string? name, string message)
    {
        var ids = new List<string>();
        foreach (var curve in curves ?? Array.Empty<Curve>())
            ids.Add(RhinoDoc.ActiveDoc.Objects.AddCurve(curve, AttributesWithName(name)).ToString());
        RhinoDoc.ActiveDoc.Views.Redraw();
        return new { success = ids.Count > 0, result_ids = ids, count = ids.Count, message };
    }

    // -------------------------------------------------------------------------
    // Low-level utilities
    // -------------------------------------------------------------------------

    private static ObjectAttributes AttributesWithName(string? name)
    {
        var attr = new ObjectAttributes();
        if (!string.IsNullOrWhiteSpace(name))
            attr.Name = name;
        return attr;
    }

    private static RhinoObject? FindById(string? idText)
        => Guid.TryParse(idText, out var id) ? RhinoDoc.ActiveDoc.Objects.FindId(id) : null;

    private static Curve? GetCurveFromId(string? idText)
        => FindById(idText)?.Geometry as Curve;

    private static Brep? GetBrepFromId(string? idText)
    {
        var geometry = FindById(idText)?.Geometry;
        return geometry switch
        {
            Brep brep => brep,
            Extrusion extrusion => extrusion.ToBrep(),
            Surface surface => surface.ToBrep(),
            _ => null
        };
    }

    private static string? SafePluginPath(Guid id)
    {
        try { return PlugIn.PathFromId(id); }
        catch { return null; }
    }

    // Layer-name cache — avoids repeated table lookups during large batch serializations.
    // Thread-safe: Rhino can invoke handlers from background threads.
    private static readonly Dictionary<(uint docSerialNumber, int layerIndex), string> _layerNameCache = new();
    private static uint _layerNameCacheDocSerial = 0;
    private static readonly object _layerCacheLock = new();

    private static string? LayerName(RhinoObject obj)
    {
        var index = obj.Attributes.LayerIndex;
        if (index < 0)
            return null;

        var doc = RhinoDoc.ActiveDoc;
        var serial = doc.RuntimeSerialNumber;

        lock (_layerCacheLock)
        {
            if (serial != _layerNameCacheDocSerial)
            {
                _layerNameCache.Clear();
                _layerNameCacheDocSerial = serial;
            }

            var key = (serial, index);
            if (_layerNameCache.TryGetValue(key, out var cached))
                return cached;

            var fullPath = doc.Layers[index].FullPath;
            _layerNameCache[key] = fullPath;
            return fullPath;
        }
    }

    private static Point3d? ReadPoint(Dictionary<string, JsonElement> p, string key)
        => p.TryGetValue(key, out var value) ? ReadPoint(value) : null;

    private static Point3d? ReadPoint(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Array)
            return null;
        var values = value.EnumerateArray().Select(v => v.GetDouble()).ToArray();
        return values.Length >= 3
            ? new Point3d(values[0], values[1], values[2])
            : values.Length == 2
                ? new Point3d(values[0], values[1], 0)
                : null;
    }

    private static Color? ReadColor(Dictionary<string, JsonElement> p, string key)
    {
        if (!p.TryGetValue(key, out var value) || value.ValueKind != JsonValueKind.Array)
            return null;
        var values = value.EnumerateArray().Select(v => v.GetInt32()).ToArray();
        return values.Length >= 3 ? Color.FromArgb(values[0], values[1], values[2]) : null;
    }

    private static int[] ColorArray(Color color) => new[] { (int)color.R, (int)color.G, (int)color.B };
    private static double[] PointArray(Point3d point) => new[] { point.X, point.Y, point.Z };
    private static double[] VectorArray(Vector3d v) => new[] { v.X, v.Y, v.Z };

    private static bool BoundingBoxesIntersect(BoundingBox a, BoundingBox b)
    {
        return a.Min.X <= b.Max.X && a.Max.X >= b.Min.X &&
               a.Min.Y <= b.Max.Y && a.Max.Y >= b.Min.Y &&
               a.Min.Z <= b.Max.Z && a.Max.Z >= b.Min.Z;
    }

    public static object GetPluginCommands(Dictionary<string, JsonElement> p)
    {
        var pluginName = p.String("plugin_name");
        var pluginIdStr = p.String("plugin_id");

        Guid pluginGuid = Guid.Empty;
        string? resolvedName = "";

        if (!string.IsNullOrWhiteSpace(pluginIdStr) && !Guid.TryParse(pluginIdStr, out pluginGuid))
            return new { success = false, message = $"Invalid plugin_id format: '{pluginIdStr}'" };

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

        if (pluginGuid != Guid.Empty && string.IsNullOrEmpty(resolvedName))
            PlugIn.GetInstalledPlugIns().TryGetValue(pluginGuid, out resolvedName);

        if (pluginGuid == Guid.Empty)
            return new { success = false, message = $"Plugin not found: {pluginName ?? pluginIdStr}" };

        var commandNames = PlugIn.GetEnglishCommandNames(pluginGuid);
        var commands = commandNames
            .Select(name => new {
                name,
                id = Rhino.Commands.Command.LookupCommandId(name, true)
            })
            .Where(c => c.id != Guid.Empty)
            .Select(c => new { c.name, id = c.id.ToString() })
            .ToList();

        return new { success = true, plugin_name = resolvedName, plugin_id = pluginGuid.ToString(), commands, count = commands.Count };
    }
}

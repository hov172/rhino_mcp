using System.Text.Json;
using Rhino;

namespace RhinoMCPPlugin;

public static class CommandDispatcher
{
    public static McpResponse Dispatch(McpRequest request)
    {
        var p = JsonHelpers.Dict(request.Params);

        // Read-only commands bypass undo recording
        var readOnly = request.Type is
            "get_document_summary" or
            "get_objects" or
            "get_object_info" or
            "get_selected_objects_info" or
            "list_plugins" or
            "get_materials" or
            "capture_viewport" or
            "get_pbr_material" or
            "list_pbr_materials" or
            // Grasshopper read-only
            "gh_get_definition_info" or
            "gh_search_components" or
            "gh_list_components" or
            "gh_get_canvas" or
            "gh_get_component_info" or
            "gh_get_output" or
            "gh_get_solution_errors" or
            "gh_get_solution_state" or
            "get_plugin_commands";

        var doc = Rhino.RhinoDoc.ActiveDoc;
        uint undoRecord = uint.MaxValue;
        if (!readOnly)
            undoRecord = doc.BeginUndoRecord($"MCP: {request.Type}");

        try
        {
            var result = request.Type switch
            {
                "ping" => McpResponse.Ok(new { ok = true, version = "0.9.0", rhino = RhinoApp.Version.ToString() }),
                "get_document_summary" => McpResponse.Ok(RhinoHandlers.GetDocumentSummary()),
                "get_objects" => McpResponse.Ok(RhinoHandlers.GetObjects(p)),
                "get_object_info" => McpResponse.Ok(RhinoHandlers.GetObjectInfo(p)),
                "get_selected_objects_info" => McpResponse.Ok(RhinoHandlers.GetSelectedObjectsInfo(p)),
                "create_object" => McpResponse.Ok(RhinoHandlers.CreateObject(p)),
                "create_objects" => McpResponse.Ok(RhinoHandlers.CreateObjects(p)),
                "delete_object" => McpResponse.Ok(RhinoHandlers.DeleteObject(p)),
                "modify_object" => McpResponse.Ok(RhinoHandlers.ModifyObject(p)),
                "modify_objects" => McpResponse.Ok(RhinoHandlers.ModifyObjects(p)),
                "select_objects" => McpResponse.Ok(RhinoHandlers.SelectObjects(p)),
                "create_layer" => McpResponse.Ok(RhinoHandlers.CreateLayer(p)),
                "delete_layer" => McpResponse.Ok(RhinoHandlers.DeleteLayer(p)),
                "get_or_set_current_layer" => McpResponse.Ok(RhinoHandlers.GetOrSetCurrentLayer(p)),
                "undo" => McpResponse.Ok(RhinoHandlers.UndoSteps(p.Int("steps", 1))),
                "redo" => McpResponse.Ok(RhinoHandlers.RedoSteps(p.Int("steps", 1))),
                "capture_viewport" => McpResponse.Ok(RhinoHandlers.CaptureViewport(p)),
                "execute_rhinoscript_python_code" => McpResponse.Ok(RhinoHandlers.ExecutePython(p)),
                "execute_rhinocommon_csharp_code" => McpResponse.Ok(RhinoHandlers.ExecuteCSharp(p)),
                "boolean_union" => McpResponse.Ok(RhinoHandlers.BooleanUnion(p)),
                "boolean_difference" => McpResponse.Ok(RhinoHandlers.BooleanDifference(p)),
                "boolean_intersection" => McpResponse.Ok(RhinoHandlers.BooleanIntersection(p)),
                "loft" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("loft", p)),
                "extrude_curve" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("extrude_curve", p)),
                "sweep1" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("sweep1", p)),
                "offset_curve" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("offset_curve", p)),
                "pipe" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("pipe", p)),
                "project_curve" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("project_curve", p)),
                "intersect_curves" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("intersect_curves", p)),
                "split_curve" => McpResponse.Ok(RhinoHandlers.RunAdvancedCommand("split_curve", p)),
                "list_plugins" => McpResponse.Ok(RhinoHandlers.ListPlugins(p)),
                "load_plugin" => McpResponse.Ok(RhinoHandlers.LoadPlugin(p)),
                "run_command" => McpResponse.Ok(RunScript(p.String("command") ?? "", p.Bool("echo", false))),
                // Material commands
                "get_materials" => McpResponse.Ok(RhinoHandlers.GetMaterials()),
                "create_material" => McpResponse.Ok(RhinoHandlers.CreateMaterial(p)),
                "set_object_material" => McpResponse.Ok(RhinoHandlers.SetObjectMaterial(p)),
                "delete_material" => McpResponse.Ok(RhinoHandlers.DeleteMaterial(p)),
                // Block / instance commands
                "create_block_definition" => McpResponse.Ok(RhinoHandlers.CreateBlockDefinition(p)),
                "insert_block" => McpResponse.Ok(RhinoHandlers.InsertBlock(p)),
                // PBR material and rendering commands
                "create_pbr_material"  => McpResponse.Ok(RhinoHandlers.CreatePbrMaterial(p)),
                "set_environment_map"  => McpResponse.Ok(RhinoHandlers.SetEnvironmentMap(p)),
                "render_viewport"      => McpResponse.Ok(RhinoHandlers.RenderViewport(p)),
                "get_pbr_material"     => McpResponse.Ok(RhinoHandlers.GetPbrMaterial(p)),
                "list_pbr_materials"   => McpResponse.Ok(RhinoHandlers.ListPbrMaterials(p)),
                "set_render_settings"  => McpResponse.Ok(RhinoHandlers.SetRenderSettings(p)),
                "assign_pbr_material"  => McpResponse.Ok(RhinoHandlers.AssignPbrMaterial(p)),
                // Grasshopper — document
                "gh_get_definition_info" => McpResponse.Ok(GHDocumentHandlers.GetDefinitionInfo(p)),
                "gh_open_document"       => McpResponse.Ok(GHDocumentHandlers.OpenDocument(p)),
                "gh_new_document"        => McpResponse.Ok(GHDocumentHandlers.NewDocument(p)),
                "gh_save_document"       => McpResponse.Ok(GHDocumentHandlers.SaveDocument(p)),
                "gh_close_document"      => McpResponse.Ok(GHDocumentHandlers.CloseDocument(p)),
                // Grasshopper — canvas
                "gh_search_components"    => McpResponse.Ok(GHCanvasHandlers.SearchComponents(p)),
                "gh_list_components"      => McpResponse.Ok(GHCanvasHandlers.ListComponents(p)),
                "gh_get_canvas"           => McpResponse.Ok(GHCanvasHandlers.GetCanvas(p)),
                "gh_get_component_info"   => McpResponse.Ok(GHCanvasHandlers.GetComponentInfo(p)),
                "gh_add_component"        => McpResponse.Ok(GHCanvasHandlers.AddComponent(p)),
                "gh_remove_component"     => McpResponse.Ok(GHCanvasHandlers.RemoveComponent(p)),
                "gh_move_component"       => McpResponse.Ok(GHCanvasHandlers.MoveComponent(p)),
                "gh_rename_component"     => McpResponse.Ok(GHCanvasHandlers.RenameComponent(p)),
                "gh_set_component_comment"=> McpResponse.Ok(GHCanvasHandlers.SetComponentComment(p)),
                "gh_connect_wire"         => McpResponse.Ok(GHCanvasHandlers.ConnectWire(p)),
                "gh_disconnect_wire"      => McpResponse.Ok(GHCanvasHandlers.DisconnectWire(p)),
                "gh_add_group"            => McpResponse.Ok(GHCanvasHandlers.AddGroup(p)),
                // Grasshopper — params
                "gh_get_output"          => McpResponse.Ok(GHParamHandlers.GetOutput(p)),
                "gh_get_solution_errors" => McpResponse.Ok(GHParamHandlers.GetSolutionErrors(p)),
                "gh_set_slider"          => McpResponse.Ok(GHParamHandlers.SetSlider(p)),
                "gh_set_panel"           => McpResponse.Ok(GHParamHandlers.SetPanel(p)),
                "gh_set_number_param"    => McpResponse.Ok(GHParamHandlers.SetNumberParam(p)),
                "gh_set_point_param"     => McpResponse.Ok(GHParamHandlers.SetPointParam(p)),
                "gh_add_script_component"=> McpResponse.Ok(GHParamHandlers.AddScriptComponent(p)),
                "gh_set_script_code"     => McpResponse.Ok(GHParamHandlers.SetScriptCode(p)),
                // Grasshopper — solution
                "gh_get_solution_state" => McpResponse.Ok(GHSolutionHandlers.GetSolutionState(p)),
                "gh_run_solution"       => McpResponse.Ok(GHSolutionHandlers.RunSolution(p)),
                "gh_bake_component"     => McpResponse.Ok(GHSolutionHandlers.BakeComponent(p)),
                "gh_bake_all"           => McpResponse.Ok(GHSolutionHandlers.BakeAll(p)),
                "gh_enable_component"   => McpResponse.Ok(GHSolutionHandlers.EnableComponent(p)),
                "get_plugin_commands" => McpResponse.Ok(RhinoHandlers.GetPluginCommands(p)),
                _ => McpResponse.Error($"Unsupported command type: {request.Type}")
            };
            return result;
        }
        finally
        {
            if (undoRecord != uint.MaxValue)
                doc.EndUndoRecord(undoRecord);
        }
    }

    private static object RunScript(string command, bool echo = false)
    {
        if (string.IsNullOrWhiteSpace(command))
            return new { ok = false, message = "command is required" };
        bool prevCapture = RhinoApp.CommandWindowCaptureEnabled;
        RhinoApp.CommandWindowCaptureEnabled = true;
        bool ok;
        string[] lines;
        try
        {
            ok = RhinoApp.RunScript(command, echo);
            lines = RhinoApp.CapturedCommandWindowStrings(true) ?? Array.Empty<string>();
        }
        finally
        {
            RhinoApp.CommandWindowCaptureEnabled = prevCapture;
        }
        var output = string.Join("\n", lines).Trim();
        return new { ok, command, output };
    }
}

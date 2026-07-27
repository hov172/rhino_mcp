# Rhino MCP Notes

## Connection
Rhino 8.11+ includes `rhinocode`, a command line tool that can list running Rhino instances, execute Rhino commands, and run scripts in a Rhino instance. Rhino's script server must be started inside Rhino with `StartScriptServer`.

## Python
Rhino Python scripts can use `rhinoscriptsyntax` for concise modeling commands and RhinoCommon for lower-level geometry, document, display, file, and viewport APIs. MCP scripts should assign JSON-compatible data to a variable named `result`.

## Geometry
Common `rhinoscriptsyntax` constructors include `AddPoint`, `AddLine`, `AddPolyline`, `AddCurve`, `AddCircle`, `AddArc3Pt`, `AddSphere`, `AddBox`, `AddCylinder`, `AddCone`, `AddTorus`, `AddPlaneSurface`, `AddMesh`, and `AddText`.

## Layers
Use layers to keep generated scenes manageable. Useful functions include `AddLayer`, `DeleteLayer`, `CurrentLayer`, `LayerNames`, `LayerColor`, `LayerVisible`, `LayerLocked`, and `ObjectLayer`.

## Objects
Object operations commonly use `AllObjects`, `SelectedObjects`, `SelectObjects`, `UnselectAllObjects`, `DeleteObjects`, `ObjectName`, `ObjectColor`, `ObjectLayer`, `MoveObjects`, `RotateObjects`, and `ScaleObjects`.

## RhinoCommon
Use RhinoCommon when RhinoScriptSyntax is not expressive enough. Important namespaces include `Rhino.Geometry`, `Rhino.DocObjects`, `Rhino.Display`, `Rhino.FileIO`, and `Rhino.RhinoDoc.ActiveDoc`.

## Export
Rhino export behavior is usually driven by command macros. The file extension selects exporters such as `.3dm`, `.obj`, `.stl`, `.fbx`, `.step`, `.iges`, `.dwg`, and `.dxf`.

## View Capture
Viewport capture is available through RhinoCommon view APIs. Set camera and target before capture when the user needs a specific composition.

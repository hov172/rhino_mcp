
var vp = doc.Views.ActiveView;

var shadedMode = Rhino.Display.DisplayModeDescription.FindByName("Shaded");
if (shadedMode != null)
    vp.ActiveViewport.DisplayMode = shadedMode;

var target = new Point3d(0, 40, 0);
var camPos  = new Point3d(-260, -160, 140);
vp.ActiveViewport.SetCameraLocation(camPos, true);
vp.ActiveViewport.SetCameraTarget(target, true);
vp.ActiveViewport.Camera35mmLensLength = 28;
vp.Redraw();

output.AppendLine("View: Shaded, SW elevated perspective");

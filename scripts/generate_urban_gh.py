"""
Generate the baseline Grasshopper definitions used by the urban massing tools.

Run this script inside Rhino through the RhinoMCP plug-in's
execute_rhinoscript_python_code command. It creates valid .gh documents with
the NickName contract expected by src/rhmcp/tools/urban.py:

- named Number Sliders for each typology
- a BakeTarget Brep parameter containing default massing geometry
- a Metrics panel with GFA/FAR/Units/OpenSpace text
- analysis_solar.gh input/output panels and a radiation_mesh BakeTarget
"""

import os
from System import Decimal
from System.Drawing import PointF

from Grasshopper.Kernel import GH_Document, GH_DocumentIO
from Grasshopper.Kernel.Parameters import Param_Brep
from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel
from Grasshopper.Kernel.Types import GH_Brep
from Rhino.Geometry import Box, Brep, Interval, Plane, Point3d, Vector3d


ROOT = "/Users/helpdesk/Developer/GitHub/rhino_mcp/grasshopper/urban"


def _decimal(value):
    return Decimal.Parse(str(value))


def _set_pivot(obj, x, y):
    obj.CreateAttributes()
    obj.Attributes.Pivot = PointF(float(x), float(y))


def _slider(nickname, minimum, maximum, value, x, y, decimals=0):
    slider = GH_NumberSlider()
    slider.NickName = nickname
    slider.Name = nickname
    slider.Description = "Urban massing input: " + nickname
    slider.Slider.Minimum = _decimal(minimum)
    slider.Slider.Maximum = _decimal(maximum)
    slider.Slider.DecimalPlaces = int(decimals)
    slider.SetSliderValue(_decimal(value))
    _set_pivot(slider, x, y)
    return slider


def _panel(nickname, text, x, y):
    panel = GH_Panel()
    panel.NickName = nickname
    panel.Name = nickname
    panel.Description = "Urban massing panel: " + nickname
    panel.SetUserText(str(text))
    _set_pivot(panel, x, y)
    return panel


def _box_brep(width, depth, height, cx=0.0, cy=0.0, z0=0.0):
    plane = Plane(Point3d(cx, cy, z0), Vector3d.XAxis, Vector3d.YAxis)
    box = Box(
        plane,
        Interval(-float(width) / 2.0, float(width) / 2.0),
        Interval(-float(depth) / 2.0, float(depth) / 2.0),
        Interval(0.0, float(height)),
    )
    return box.ToBrep()


def _brep_param(nickname, breps, x, y):
    param = Param_Brep()
    param.NickName = nickname
    param.Name = nickname
    param.Description = "Bake target for generated urban massing geometry"
    for brep in breps:
        if brep is not None:
            param.AddPersistentData(GH_Brep(brep))
    _set_pivot(param, x, y)
    return param


def _metrics_panel(gfa, site_area, residential_pct, open_space_pct):
    units = int(float(gfa) * (float(residential_pct) / 100.0) / 70.0)
    far = float(gfa) / float(site_area) if site_area else 0.0
    return "GFA: %.0f\nFAR: %.2f\nUnits: %d\nOpenSpace: %.0f" % (
        float(gfa),
        far,
        units,
        float(open_space_pct),
    )


def _save_doc(path, sliders, panels, bake_targets):
    doc = GH_Document()
    for obj in sliders + panels + bake_targets:
        doc.AddObject(obj, False)
    io = GH_DocumentIO(doc)
    if not io.SaveQuiet(path):
        raise Exception("Failed to save " + path)
    return path


def _tower():
    path = os.path.join(ROOT, "tower.gh")
    specs = [
        ("site_width", 10, 500, 80, 0),
        ("site_depth", 10, 500, 80, 0),
        ("tower_count", 1, 6, 1, 0),
        ("floor_count", 5, 80, 30, 0),
        ("floor_height", 2.8, 5.0, 3.2, 1),
        ("footprint_width", 8, 40, 22, 0),
        ("footprint_depth", 8, 40, 22, 0),
        ("setback", 0, 20, 6, 0),
        ("residential_pct", 0, 100, 70, 0),
        ("retail_floors", 0, 5, 1, 0),
    ]
    sliders = [_slider(name, mn, mx, val, 20, 20 + i * 35, dec) for i, (name, mn, mx, val, dec) in enumerate(specs)]
    gfa = 22 * 22 * 30
    site_area = 80 * 80
    open_space = (site_area - 22 * 22) / site_area * 100.0
    panels = [_panel("Metrics", _metrics_panel(gfa, site_area, 70, open_space), 420, 40)]
    bake = [_brep_param("BakeTarget", [_box_brep(22, 22, 30 * 3.2)], 420, 180)]
    return _save_doc(path, sliders, panels, bake)


def _podium_tower():
    path = os.path.join(ROOT, "podium_tower.gh")
    specs = [
        ("site_width", 20, 500, 120, 0),
        ("site_depth", 20, 500, 120, 0),
        ("podium_floors", 1, 8, 4, 0),
        ("podium_setback", 0, 15, 3, 0),
        ("tower_floors", 5, 60, 25, 0),
        ("tower_count", 1, 2, 1, 0),
        ("floor_height", 2.8, 5.0, 3.2, 1),
        ("residential_pct", 0, 100, 60, 0),
        ("retail_pct", 0, 100, 20, 0),
    ]
    sliders = [_slider(name, mn, mx, val, 20, 20 + i * 35, dec) for i, (name, mn, mx, val, dec) in enumerate(specs)]
    podium_w = 120 - 2 * 3
    podium_d = 120 - 2 * 3
    podium_h = 4 * 3.2
    tower_h = 25 * 3.2
    podium_gfa = podium_w * podium_d * 4
    tower_gfa = 22 * 22 * 25
    total_gfa = podium_gfa + tower_gfa
    open_space = (120 * 120 - podium_w * podium_d) / (120 * 120) * 100.0
    panels = [_panel("Metrics", _metrics_panel(total_gfa, 120 * 120, 60, open_space), 420, 40)]
    bake = [_brep_param("BakeTarget", [_box_brep(podium_w, podium_d, podium_h), _box_brep(22, 22, tower_h, z0=podium_h)], 420, 180)]
    return _save_doc(path, sliders, panels, bake)


def _courtyard():
    path = os.path.join(ROOT, "courtyard.gh")
    specs = [
        ("site_width", 20, 300, 80, 0),
        ("site_depth", 20, 300, 80, 0),
        ("wing_width", 6, 25, 14, 0),
        ("floor_count", 2, 12, 6, 0),
        ("floor_height", 2.8, 4.5, 3.2, 1),
        ("corner_opening_width", 0, 20, 0, 0),
        ("residential_pct", 0, 100, 80, 0),
        ("retail_pct", 0, 100, 10, 0),
    ]
    sliders = [_slider(name, mn, mx, val, 20, 20 + i * 35, dec) for i, (name, mn, mx, val, dec) in enumerate(specs)]
    site_area = 80 * 80
    footprint = site_area - (80 - 2 * 14) * (80 - 2 * 14)
    gfa = footprint * 6
    open_space = (site_area - footprint) / site_area * 100.0
    h = 6 * 3.2
    # Four wings approximate the courtyard perimeter and bake as separate solids.
    breps = [
        _box_brep(80, 14, h, cy=33),
        _box_brep(80, 14, h, cy=-33),
        _box_brep(14, 52, h, cx=33),
        _box_brep(14, 52, h, cx=-33),
    ]
    panels = [_panel("Metrics", _metrics_panel(gfa, site_area, 80, open_space), 420, 40)]
    bake = [_brep_param("BakeTarget", breps, 420, 180)]
    return _save_doc(path, sliders, panels, bake)


def _perimeter_block():
    path = os.path.join(ROOT, "perimeter_block.gh")
    specs = [
        ("site_width", 20, 300, 80, 0),
        ("site_depth", 20, 300, 80, 0),
        ("block_width", 8, 30, 16, 0),
        ("floor_count", 2, 10, 5, 0),
        ("floor_height", 2.8, 4.5, 3.2, 1),
        ("residential_pct", 0, 100, 75, 0),
        ("retail_pct", 0, 100, 15, 0),
    ]
    sliders = [_slider(name, mn, mx, val, 20, 20 + i * 35, dec) for i, (name, mn, mx, val, dec) in enumerate(specs)]
    site_area = 80 * 80
    gfa = site_area * 5
    panels = [_panel("Metrics", _metrics_panel(gfa, site_area, 75, 0), 420, 40)]
    bake = [_brep_param("BakeTarget", [_box_brep(80, 80, 5 * 3.2)], 420, 180)]
    return _save_doc(path, sliders, panels, bake)


def _street_grid():
    path = os.path.join(ROOT, "street_grid.gh")
    specs = [
        ("site_width", 50, 2000, 400, 0),
        ("site_depth", 50, 2000, 400, 0),
        ("block_width", 30, 200, 80, 0),
        ("block_depth", 30, 150, 60, 0),
        ("road_width", 6, 30, 12, 0),
        ("grid_rotation", -45, 45, 0, 0),
    ]
    sliders = [_slider(name, mn, mx, val, 20, 20 + i * 35, dec) for i, (name, mn, mx, val, dec) in enumerate(specs)]
    n_x = max(1, int(400 / (80 + 12)))
    n_y = max(1, int(400 / (60 + 12)))
    breps = []
    start_x = -((n_x - 1) * (80 + 12)) / 2.0
    start_y = -((n_y - 1) * (60 + 12)) / 2.0
    for ix in range(n_x):
        for iy in range(n_y):
            breps.append(_box_brep(80, 60, 0.2, cx=start_x + ix * 92, cy=start_y + iy * 72))
    site_area = 400 * 400
    road_area = site_area - n_x * n_y * 80 * 60
    metrics = "GFA: 0\nFAR: 0.00\nUnits: 0\nOpenSpace: %.0f" % (road_area / site_area * 100.0)
    panels = [_panel("Metrics", metrics, 420, 40)]
    bake = [_brep_param("BakeTarget", breps, 420, 180)]
    return _save_doc(path, sliders, panels, bake)


def _analysis_solar():
    path = os.path.join(ROOT, "analysis_solar.gh")
    panels = [
        _panel("epw_path", "~/ladybug/EPWs/GBR_London.Gatwick.037760_IWEC.epw", 20, 20),
        _panel("geometry_layer", "Urban::Massing::courtyard", 20, 80),
        _panel("analysis_period", "Jun 21 9am-5pm", 20, 140),
        _panel("avg_radiation_kwh_m2", "380", 420, 40),
        _panel("overshadow_hours_worst", "4.2", 420, 100),
    ]
    sliders = [_slider("grid_size", 0.5, 5.0, 1.0, 20, 220, 1)]
    bake = [_brep_param("radiation_mesh", [_box_brep(40, 40, 0.1)], 420, 180)]
    return _save_doc(path, sliders, panels, bake)


if not os.path.isdir(ROOT):
    os.makedirs(ROOT)

saved = [
    _tower(),
    _podium_tower(),
    _courtyard(),
    _perimeter_block(),
    _street_grid(),
    _analysis_solar(),
]

print("Generated urban Grasshopper definitions:")
for path in saved:
    print(path)

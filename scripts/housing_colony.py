"""
Housing Colony Layout
---------------------
20 plots | 10 per side | each 60x40 ft | 18 ft central road

Run inside Rhino:  Tools > PythonScript > Run  (select this file)
or paste into:     Tools > PythonScript > Edit
"""

import rhinoscriptsyntax as rs

# ── dimensions (feet) ──────────────────────────────────────────────────────
PLOT_WIDTH  = 60   # along road
PLOT_DEPTH  = 40   # away from road
ROAD_WIDTH  = 18
PLOTS_PER_SIDE = 10

# ── derived ────────────────────────────────────────────────────────────────
ROAD_HALF   = ROAD_WIDTH / 2.0          # 9 ft
TOTAL_LEN   = PLOTS_PER_SIDE * PLOT_WIDTH  # 600 ft

# Y extents
ROAD_S  = -ROAD_HALF                    # -9
ROAD_N  =  ROAD_HALF                    # +9
SOUTH_S =  ROAD_S - PLOT_DEPTH         # -49
NORTH_N =  ROAD_N + PLOT_DEPTH         #  +49


def _ensure_layer(name, color):
    if not rs.IsLayer(name):
        rs.AddLayer(name, color)
    return name


def _add_rect(x0, y0, x1, y1, layer):
    pts = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, 0)]
    crv = rs.AddPolyline(pts)
    rs.ObjectLayer(crv, layer)
    return crv


def _add_label(text, cx, cy, layer, height=4):
    pt = rs.AddTextDot(text, (cx, cy, 0))
    rs.ObjectLayer(pt, layer)
    return pt


def build_colony():
    rs.EnableRedraw(False)
    try:
        layer_road   = _ensure_layer("Colony::Road",   (180, 180, 180))
        layer_plot   = _ensure_layer("Colony::Plots",  ( 80, 160,  80))
        layer_label  = _ensure_layer("Colony::Labels", ( 50,  50, 200))
        layer_border = _ensure_layer("Colony::Border", (200,  80,  80))

        # ── road ──────────────────────────────────────────────────────────
        _add_rect(0, ROAD_S, TOTAL_LEN, ROAD_N, layer_road)
        _add_label("18' Road", TOTAL_LEN / 2, 0, layer_label, height=5)

        # ── plots ─────────────────────────────────────────────────────────
        for i in range(PLOTS_PER_SIDE):
            x0 = i * PLOT_WIDTH
            x1 = x0 + PLOT_WIDTH
            cx = (x0 + x1) / 2.0

            # north side: plots 1–10
            _add_rect(x0, ROAD_N, x1, NORTH_N, layer_plot)
            _add_label("P{}".format(i + 1), cx, ROAD_N + PLOT_DEPTH / 2.0, layer_label)

            # south side: plots 11–20
            _add_rect(x0, SOUTH_S, x1, ROAD_S, layer_plot)
            _add_label("P{}".format(i + 11), cx, ROAD_S - PLOT_DEPTH / 2.0, layer_label)

        # ── outer colony border ───────────────────────────────────────────
        _add_rect(0, SOUTH_S, TOTAL_LEN, NORTH_N, layer_border)

        # ── dimension annotations ─────────────────────────────────────────
        # road width arrow (right side)
        rs.ObjectLayer(
            rs.AddLine((TOTAL_LEN + 5, ROAD_S, 0), (TOTAL_LEN + 5, ROAD_N, 0)),
            layer_label
        )
        _add_label("18'", TOTAL_LEN + 12, 0, layer_label)

        # plot depth annotation (top)
        rs.ObjectLayer(
            rs.AddLine((TOTAL_LEN + 5, ROAD_N, 0), (TOTAL_LEN + 5, NORTH_N, 0)),
            layer_label
        )
        _add_label("40'", TOTAL_LEN + 12, ROAD_N + PLOT_DEPTH / 2.0, layer_label)

        # plot width annotation (top edge)
        rs.ObjectLayer(
            rs.AddLine((0, NORTH_N + 5, 0), (PLOT_WIDTH, NORTH_N + 5, 0)),
            layer_label
        )
        _add_label("60'", PLOT_WIDTH / 2.0, NORTH_N + 10, layer_label)

    finally:
        rs.EnableRedraw(True)

    # zoom to colony
    rs.Command("_Zoom _All _Enter", False)

    print("Done: 20 plots created (P1–P10 north, P11–P20 south)")
    print("Colony: {} ft wide x {} ft deep".format(TOTAL_LEN, NORTH_N - SOUTH_S))
    print("Layers: Colony::Road | Colony::Plots | Colony::Labels | Colony::Border")


build_colony()

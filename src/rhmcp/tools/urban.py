"""
High-level MCP tools for AI-driven urban massing workflows.

Drives pre-built Grasshopper definitions in grasshopper/urban/ to generate
parametric 3D massing typologies, read back GFA/FAR/unit metrics, and run
Ladybug solar analysis — all through composite tool calls Claude uses in
conversation.
"""
from __future__ import annotations

import base64
import json
import os

from mcp.server.fastmcp import FastMCP, Image

from rhmcp.tools_helpers import backend as rhino
from rhmcp.tools.view import _CAPTURE_SCRIPT

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_GH_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "grasshopper", "urban"
    )
)

_TYPOLOGY_GH_MAP: dict[str, str] = {
    "tower":           os.path.join(_GH_DIR, "tower.gh"),
    "podium_tower":    os.path.join(_GH_DIR, "podium_tower.gh"),
    "courtyard":       os.path.join(_GH_DIR, "courtyard.gh"),
    "perimeter_block": os.path.join(_GH_DIR, "perimeter_block.gh"),
    "street_grid":     os.path.join(_GH_DIR, "street_grid.gh"),
}

_ANALYSIS_GH_MAP: dict[str, str] = {
    "solar": os.path.join(_GH_DIR, "analysis_solar.gh"),
}  # used by urban_run_analysis (Task 6)

_EPW_BASE = os.path.expanduser("~/ladybug/EPWs")

_EPW_DEFAULTS: dict[str, str] = {
    "London":    "GBR_London.Gatwick.037760_IWEC.epw",
    "New York":  "USA_NY_New.York-J.F.K.Intl.AP.744860_TMY3.epw",
    "Dubai":     "ARE_Dubai.Intl.AP.411940_IWEC.epw",
    "Tokyo":     "JPN_Tokyo.Hyakuri.477150_IWEC.epw",
    "Sydney":    "AUS_NSW_Sydney.Intl.AP.947670_IWEC.epw",
    "Singapore": "SGP_Singapore.486980_IWEC.epw",
    "Berlin":    "DEU_Berlin.Tempelhof.103840_IWEC.epw",
}

# Ordered list of NickNames for each typology's Number Sliders.
# Must exactly match the NickName field set on each slider in the .gh file.
_SLIDER_MAPS: dict[str, list[str]] = {
    "tower": [
        "site_width", "site_depth", "tower_count", "floor_count",
        "floor_height", "footprint_width", "footprint_depth",
        "setback", "residential_pct", "retail_floors",
    ],
    "podium_tower": [
        "site_width", "site_depth", "podium_floors", "podium_setback",
        "tower_floors", "tower_count", "floor_height",
        "residential_pct", "retail_pct",
    ],
    "courtyard": [
        "site_width", "site_depth", "wing_width", "floor_count",
        "floor_height", "corner_opening_width", "residential_pct", "retail_pct",
    ],
    "perimeter_block": [
        "site_width", "site_depth", "block_width", "floor_count",
        "floor_height", "residential_pct", "retail_pct",
    ],
    "street_grid": [
        "site_width", "site_depth", "block_width", "block_depth",
        "road_width", "grid_rotation",
    ],
}

# ---------------------------------------------------------------------------
# Module-level state
# Set by urban_generate_massing; consumed by urban_update_param,
# urban_get_metrics, and urban_capture_and_evaluate.
# ---------------------------------------------------------------------------

_current_typology: str | None = None
_current_slider_guids: dict[str, str] = {}   # param_name → instance_guid
_current_metrics_guid: str | None = None
_current_bake_guid: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gh(command: str, params: dict[str, object]) -> dict[str, object]:
    try:
        return rhino.plugin_result(command, params)
    except OSError:
        return {
            "ok": False,
            "error": "Grasshopper plugin not connected. Ensure Rhino is running with the RhinoMCP plugin loaded.",
        }


def _resolve_slider_guids(typology: str) -> tuple[dict[str, str], str | None, str | None]:
    """
    After gh_open_document, discover NickName→GUID mappings by running a
    Python script inside Rhino that reads the active GH document directly.

    Returns (slider_guids, metrics_guid, bake_guid).
    """
    code = r"""
import Grasshopper
doc = Grasshopper.Instances.ActiveCanvas.Document
nick_to_guid = {}
for obj in doc.Objects:
    nick = getattr(obj, 'NickName', None)
    if nick:
        nick_to_guid[str(nick)] = str(obj.InstanceGuid)
result = nick_to_guid
"""
    try:
        raw = rhino.execute_python(code)
    except Exception:
        return {}, None, None

    mapping: dict[str, str] = {}
    if isinstance(raw, dict):
        r = raw.get("result", {})
        if isinstance(r, dict):
            mapping = r

    expected = set(_SLIDER_MAPS.get(typology, []))
    slider_guids = {k: v for k, v in mapping.items() if k in expected}
    metrics_guid = mapping.get("Metrics")
    bake_guid = mapping.get("BakeTarget")
    return slider_guids, metrics_guid, bake_guid


def _parse_metrics_panel(text: str) -> dict[str, object]:
    """
    Parse the Metrics panel output from a .gh definition.

    Expected format (one field per line):
        GFA: 28000
        FAR: 3.5
        Units: 280
        OpenSpace: 22
    """
    metrics: dict[str, object] = {
        "gfa_m2": 0.0,
        "far": 0.0,
        "unit_count_est": 0,
        "open_space_pct": 0.0,
    }
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().upper()
        val = val.strip()
        try:
            if key == "GFA":
                metrics["gfa_m2"] = float(val)
            elif key == "FAR":
                metrics["far"] = float(val)
            elif key == "UNITS":
                metrics["unit_count_est"] = int(float(val))
            elif key == "OPENSPACE":
                metrics["open_space_pct"] = float(val)
        except ValueError:
            pass
    return metrics


def _capture_view() -> list[object]:
    """
    Capture the active Rhino viewport.
    Returns [meta_dict, Image] on success, or [error_dict] on failure.
    Reuses the same capture script as capture_rhino_view in view.py.
    """
    payload = {"path": None, "width": 1200, "height": 900}
    code = "__mcp_capture = {!s}\n{}".format(json.dumps(payload), _CAPTURE_SCRIPT)
    raw = rhino.execute_python(code)
    r = raw.get("result") if isinstance(raw, dict) else None
    b64 = r.get("b64") if isinstance(r, dict) else None
    if not b64:
        return [raw]
    meta = {
        "path": r.get("path"),
        "saved": r.get("saved", False),
        "width": r.get("width", 1200),
        "height": r.get("height", 900),
    }
    return [meta, Image(data=base64.b64decode(b64), format="png")]


def _urban_get_metrics() -> dict[str, object]:
    """
    Read GFA, FAR, unit count, open space % from the currently open GH definition.
    Returns zero-safe defaults when no definition is open or parse fails.
    """
    _zero: dict[str, object] = {
        "gfa_m2": 0.0, "far": 0.0, "unit_count_est": 0, "open_space_pct": 0.0,
    }
    if not _current_metrics_guid:
        return _zero
    result = _gh("gh_get_output", {"instance_guid": _current_metrics_guid})
    if not result.get("ok"):
        return _zero
    raw = result.get("result", {})
    outputs = raw.get("outputs", []) if isinstance(raw, dict) else []
    for out in outputs:
        values = out.get("values", [])
        if values:
            return _parse_metrics_panel(str(values[0]))
    return _zero


def register(mcp: FastMCP) -> None:
    from mcp.types import ToolAnnotations

    @mcp.tool(annotations=ToolAnnotations(title="Get Urban Massing Metrics", readOnlyHint=True))
    def urban_get_metrics(rhino_id: str | None = None) -> dict[str, object]:
        """
        Read GFA, FAR, estimated unit count, and open space percentage from the
        currently open Grasshopper massing definition's Metrics output panel.

        Returns {gfa_m2, far, unit_count_est, open_space_pct}.
        Returns zeros if no massing definition is currently open.
        """
        return _urban_get_metrics()

    @mcp.tool(annotations=ToolAnnotations(title="Generate Urban Massing", destructiveHint=True))
    def urban_generate_massing(
        typology: str,
        site_origin: list[float],
        site_width: float,
        site_depth: float,
        params: dict[str, float] | None = None,
        layer_prefix: str = "Urban",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Generate parametric 3D urban massing in Rhino by driving a pre-built
        Grasshopper definition.

        typology: One of "tower", "podium_tower", "courtyard", "perimeter_block",
                  "street_grid".
        site_origin: [x, y, z] in model units (metres). Baked geometry is moved
                     here after solving.
        site_width: Site width in metres.
        site_depth: Site depth in metres.
        params: Slider overrides, e.g. {"floor_count": 20, "residential_pct": 75}.
                Any key from the typology's slider map is valid.
        layer_prefix: Baked geometry goes to {layer_prefix}::Massing::{typology}.
        Returns: {ok, typology, layer, gfa_m2, far, unit_count_est, open_space_pct}.
        """
        global _current_typology, _current_slider_guids, _current_metrics_guid, _current_bake_guid

        if typology not in _TYPOLOGY_GH_MAP:
            return {
                "ok": False,
                "error": f"Unknown typology '{typology}'. Valid: {sorted(_TYPOLOGY_GH_MAP)}",
            }

        gh_path = _TYPOLOGY_GH_MAP[typology]
        open_result = _gh("gh_open_document", {"path": gh_path})
        if not open_result.get("ok"):
            return {"ok": False, "error": f"Failed to open {gh_path}: {open_result.get('error')}"}

        slider_guids, metrics_guid, bake_guid = _resolve_slider_guids(typology)
        _current_typology = typology
        _current_slider_guids = slider_guids
        _current_metrics_guid = metrics_guid
        _current_bake_guid = bake_guid

        combined: dict[str, float] = {"site_width": site_width, "site_depth": site_depth}
        if params:
            combined.update(params)
        for key, value in combined.items():
            if key in slider_guids:
                _gh("gh_set_slider", {"instance_guid": slider_guids[key], "value": value})

        run_result = _gh("gh_run_solution", {"wait_ms": 15000})
        if not run_result.get("ok"):
            return {"ok": False, "error": f"GH solution failed: {run_result.get('error')}"}

        layer = f"{layer_prefix}::Massing::{typology}"
        if bake_guid:
            _gh("gh_bake", {"instance_guid": bake_guid, "layer": layer})

        # Move baked geometry to site_origin if non-zero
        ox, oy = float(site_origin[0]), float(site_origin[1])
        oz = float(site_origin[2]) if len(site_origin) > 2 else 0.0
        if ox != 0.0 or oy != 0.0 or oz != 0.0:
            move_code = (
                "import rhinoscriptsyntax as rs\n"
                f"objs = rs.ObjectsByLayer('{layer}')\n"
                f"if objs: rs.MoveObjects(objs, ({ox}, {oy}, {oz}))\n"
                "result = {'moved': len(objs) if objs else 0}"
            )
            rhino.execute_python(move_code)

        metrics = _urban_get_metrics()
        return {"ok": True, "typology": typology, "layer": layer, **metrics}

"""
High-level MCP tools for AI-driven urban massing workflows.

Drives pre-built Grasshopper definitions in grasshopper/urban/ to generate
parametric 3D massing typologies, read back GFA/FAR/unit metrics, and run
Ladybug solar analysis — all through composite tool calls Claude uses in
conversation.
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import re

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
_current_params: dict[str, float] = {}
_current_site_width: float | None = None
_current_site_depth: float | None = None
_current_metrics_cache: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_use_mix(residential: float | None, office: float | None, retail: float | None) -> dict[str, float]:
    values = {
        "residential_pct": 70.0 if residential is None else float(residential),
        "office_pct": 20.0 if office is None else float(office),
        "retail_pct": 10.0 if retail is None else float(retail),
    }
    total = sum(max(0.0, v) for v in values.values())
    if total > 100.0:
        scale = 100.0 / total
        values = {k: round(max(0.0, v) * scale, 2) for k, v in values.items()}
    return values


def _recommend_typology(far_target: float | None, prompt: str = "") -> str:
    text = prompt.lower()
    for typology in _TYPOLOGY_GH_MAP:
        if typology in text or typology.replace("_", " ") in text:
            return typology
    if any(word in text for word in ["transit", "station", "tower", "high-rise", "high rise"]):
        return "podium_tower" if far_target and far_target < 5.0 else "tower"
    if any(word in text for word in ["grid", "street", "masterplan", "district", "parcel", "block layout"]):
        return "street_grid"
    if far_target is None:
        return "podium_tower"
    if far_target < 1.5:
        return "perimeter_block"
    if far_target < 3.0:
        return "courtyard"
    if far_target < 5.0:
        return "podium_tower"
    return "tower"


def _parse_urban_prompt_text(prompt: str) -> dict[str, object]:
    text = prompt.strip()
    lower = text.lower()

    far_target: float | None = None
    far_match = re.search(r"\b(?:far|floor\s+area\s+ratio)\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)", lower)
    if not far_match:
        far_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:far|floor\s+area\s+ratio)\b", lower)
    if far_match:
        far_target = float(far_match.group(1))

    site_width: float | None = None
    site_depth: float | None = None
    dim_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)\s*(?:m|metres|meters)?",
        lower,
    )
    if dim_match:
        site_width = float(dim_match.group(1))
        site_depth = float(dim_match.group(2))

    def pct(label: str) -> float | None:
        patterns = [
            rf"(\d+(?:\.\d+)?)\s*%\s*{label}",
            rf"{label}\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)\s*%",
        ]
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                return float(match.group(1))
        return None

    use_mix = _normalize_use_mix(pct("residential"), pct("office"), pct("retail"))
    typology = _recommend_typology(far_target, text)
    climate_zone = next((zone for zone in _EPW_DEFAULTS if zone.lower() in lower), None)

    missing = []
    if site_width is None:
        missing.append("site_width")
    if site_depth is None:
        missing.append("site_depth")
    if far_target is None:
        missing.append("far_target")

    params: dict[str, float] = {
        "residential_pct": use_mix["residential_pct"],
        "retail_pct": use_mix["retail_pct"],
    }
    if typology == "tower":
        params["floor_count"] = max(5.0, round((far_target or 3.0) * 6.0))
    elif typology == "podium_tower":
        params["podium_floors"] = 4.0
    elif typology in {"courtyard", "perimeter_block"}:
        params["floor_count"] = max(2.0, round(far_target or 3.0))
    elif typology == "street_grid":
        params.update({"block_width": 80.0, "block_depth": 60.0, "road_width": 12.0})

    confidence = 1.0 - (len(missing) * 0.25)
    return {
        "ok": True,
        "prompt": prompt,
        "typology": typology,
        "site_origin": [0.0, 0.0, 0.0],
        "site_width": site_width,
        "site_depth": site_depth,
        "far_target": far_target,
        "use_mix": use_mix,
        "climate_zone": climate_zone or "London",
        "height_strategy": "towers_near_transit" if "transit" in lower or "station" in lower else "balanced",
        "params": params,
        "missing_fields": missing,
        "confidence": max(0.0, confidence),
    }


def _iter_geojson_coords(value: object):
    if isinstance(value, (int, float)):
        return
    if isinstance(value, list):
        if len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
            yield [float(value[0]), float(value[1])]
            return
        for item in value:
            yield from _iter_geojson_coords(item)
    elif isinstance(value, dict):
        if "bbox" in value and isinstance(value["bbox"], list) and len(value["bbox"]) >= 4:
            bbox = value["bbox"]
            yield [float(bbox[0]), float(bbox[1])]
            yield [float(bbox[2]), float(bbox[3])]
            return
        if value.get("type") == "FeatureCollection":
            for feature in value.get("features", []) or []:
                yield from _iter_geojson_coords(feature)
        elif value.get("type") == "Feature":
            yield from _iter_geojson_coords(value.get("geometry"))
        else:
            yield from _iter_geojson_coords(value.get("coordinates"))


def _site_dimensions_from_boundary(site_boundary: dict[str, object] | None) -> dict[str, object]:
    """
    Extract approximate site dimensions from GeoJSON-like input.

    Coordinates are treated as model units. For lon/lat GIS input, callers
    should project before calling or pass explicit dimensions in the prompt.
    """
    if not site_boundary:
        return {"ok": False, "error": "site_boundary is empty"}
    coords = list(_iter_geojson_coords(site_boundary))
    if not coords:
        return {"ok": False, "error": "No coordinates found in site_boundary"}
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    width = max(xs) - min(xs)
    depth = max(ys) - min(ys)
    return {
        "ok": width > 0 and depth > 0,
        "site_width": width,
        "site_depth": depth,
        "bbox": [[min(xs), min(ys)], [max(xs), max(ys)]],
        "coordinate_count": len(coords),
    }


def _calculate_metrics(
    site_width: float,
    site_depth: float,
    gfa_m2: float,
    residential_pct: float = 70.0,
    open_space_pct: float = 0.0,
    far_target: float | None = None,
) -> dict[str, object]:
    site_area = max(0.0, float(site_width) * float(site_depth))
    far = (float(gfa_m2) / site_area) if site_area else 0.0
    unit_count = int(float(gfa_m2) * (float(residential_pct) / 100.0) / 70.0) if gfa_m2 else 0
    result: dict[str, object] = {
        "site_area_m2": site_area,
        "gfa_m2": round(float(gfa_m2), 2),
        "far": round(far, 3),
        "unit_count_est": unit_count,
        "open_space_pct": round(float(open_space_pct), 2),
    }
    if far_target is not None:
        delta = far - float(far_target)
        result["far_target"] = float(far_target)
        result["far_delta"] = round(delta, 3)
        result["far_within_2pct"] = abs(delta) <= max(0.02 * float(far_target), 0.02)
    return result


def _estimate_typology_metrics(
    typology: str,
    site_width: float,
    site_depth: float,
    params: dict[str, float],
) -> dict[str, object]:
    site_area = max(float(site_width) * float(site_depth), 0.0)
    residential_pct = float(params.get("residential_pct", 70.0))
    if typology == "tower":
        footprint = float(params.get("footprint_width", 22.0)) * float(params.get("footprint_depth", 22.0))
        tower_count = float(params.get("tower_count", 1.0))
        gfa = footprint * float(params.get("floor_count", 30.0)) * tower_count
        open_space = max(0.0, (site_area - footprint * tower_count) / site_area * 100.0) if site_area else 0.0
    elif typology == "podium_tower":
        setback = float(params.get("podium_setback", 3.0))
        podium_fp = max(0.0, float(site_width) - 2.0 * setback) * max(0.0, float(site_depth) - 2.0 * setback)
        podium_gfa = podium_fp * float(params.get("podium_floors", 4.0))
        tower_fp = float(params.get("footprint_width", 22.0)) * float(params.get("footprint_depth", 22.0))
        tower_gfa = tower_fp * float(params.get("tower_floors", 25.0)) * float(params.get("tower_count", 1.0))
        gfa = podium_gfa + tower_gfa
        open_space = max(0.0, (site_area - podium_fp) / site_area * 100.0) if site_area else 0.0
    elif typology == "courtyard":
        wing = float(params.get("wing_width", 14.0))
        footprint = site_area - max(0.0, float(site_width) - 2.0 * wing) * max(0.0, float(site_depth) - 2.0 * wing)
        gfa = footprint * float(params.get("floor_count", 6.0))
        open_space = max(0.0, (site_area - footprint) / site_area * 100.0) if site_area else 0.0
    elif typology == "perimeter_block":
        gfa = site_area * float(params.get("floor_count", 5.0))
        open_space = 0.0
    elif typology == "street_grid":
        block_w = float(params.get("block_width", 80.0))
        block_d = float(params.get("block_depth", 60.0))
        road = float(params.get("road_width", 12.0))
        nx = max(1, int(float(site_width) / max(block_w + road, 1.0)))
        ny = max(1, int(float(site_depth) / max(block_d + road, 1.0)))
        plot_area = nx * ny * block_w * block_d
        gfa = 0.0
        open_space = max(0.0, (site_area - plot_area) / site_area * 100.0) if site_area else 0.0
    else:
        gfa = 0.0
        open_space = 0.0
    return _calculate_metrics(site_width, site_depth, gfa, residential_pct, open_space)


def _build_site_layout(site_width: float, site_depth: float, block_width: float, block_depth: float, road_width: float) -> dict[str, object]:
    nx = max(1, int(float(site_width) / max(float(block_width) + float(road_width), 1.0)))
    ny = max(1, int(float(site_depth) / max(float(block_depth) + float(road_width), 1.0)))
    parcels = []
    start_x = -((nx - 1) * (block_width + road_width)) / 2.0
    start_y = -((ny - 1) * (block_depth + road_width)) / 2.0
    for ix in range(nx):
        for iy in range(ny):
            cx = start_x + ix * (block_width + road_width)
            cy = start_y + iy * (block_depth + road_width)
            parcels.append({
                "id": f"P{ix + 1}-{iy + 1}",
                "center": [round(cx, 3), round(cy, 3), 0.0],
                "width": float(block_width),
                "depth": float(block_depth),
                "area_m2": round(float(block_width) * float(block_depth), 2),
            })
    site_area = float(site_width) * float(site_depth)
    parcel_area = sum(float(p["area_m2"]) for p in parcels)
    return {
        "site_width": float(site_width),
        "site_depth": float(site_depth),
        "block_width": float(block_width),
        "block_depth": float(block_depth),
        "road_width": float(road_width),
        "parcel_count": len(parcels),
        "parcels": parcels,
        "road_area_m2": round(max(0.0, site_area - parcel_area), 2),
        "open_space_pct": round((max(0.0, site_area - parcel_area) / site_area * 100.0) if site_area else 0.0, 2),
    }

def _gh(command: str, params: dict[str, object]) -> dict[str, object]:
    try:
        return rhino.plugin_result(command, params)
    except OSError:
        return {
            "ok": False,
            "error": "Grasshopper plugin not connected. Ensure Rhino is running with the RhinoMCP plugin loaded.",
        }


def _discover_gh_nicknames() -> dict[str, str]:
    """
    Return Grasshopper object NickName -> InstanceGuid for the active document.

    Prefer the plugin's structured canvas command. Fall back to a Rhino Python
    probe that prints JSON for older plugin builds whose execute_python handler
    does not return a result variable.
    """
    canvas = _gh("gh_get_canvas", {"include_wires": False})
    if canvas.get("ok"):
        raw = canvas.get("result", {})
        components = raw.get("components", []) if isinstance(raw, dict) else []
        mapping: dict[str, str] = {}
        for component in components:
            if not isinstance(component, dict):
                continue
            nick = component.get("nick_name") or component.get("name")
            guid = component.get("instance_guid")
            if nick and guid:
                mapping[str(nick)] = str(guid)
        if mapping:
            return mapping

    code = r"""
import Grasshopper
import json
doc = Grasshopper.Instances.ActiveCanvas.Document
nick_to_guid = {}
for obj in doc.Objects:
    nick = getattr(obj, 'NickName', None)
    if nick:
        nick_to_guid[str(nick)] = str(obj.InstanceGuid)
print(json.dumps(nick_to_guid))
"""
    try:
        raw = rhino.execute_python(code)
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}
    result = raw.get("result", {})
    if isinstance(result, dict):
        nested = result.get("result", {})
        if isinstance(nested, dict):
            return {str(k): str(v) for k, v in nested.items()}
        output = result.get("output")
        if isinstance(output, str):
            for line in reversed(output.strip().splitlines()):
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return {str(k): str(v) for k, v in parsed.items()}
    return {}


def _resolve_slider_guids(typology: str) -> tuple[dict[str, str], str | None, str | None]:
    """
    After gh_open_document, discover NickName→GUID mappings by running a
    Python script inside Rhino that reads the active GH document directly.

    Returns (slider_guids, metrics_guid, bake_guid).
    """
    mapping = _discover_gh_nicknames()
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
    plugin_capture = _gh("capture_viewport", {"path": None, "width": 1200, "height": 900})
    if plugin_capture.get("ok"):
        plugin_result = plugin_capture.get("result", {})
        b64_plugin = plugin_result.get("image_data") if isinstance(plugin_result, dict) else None
        if b64_plugin:
            meta = {
                "path": plugin_result.get("saved_path"),
                "saved": bool(plugin_result.get("saved_path")),
                "width": plugin_result.get("width", 1200),
                "height": plugin_result.get("height", 900),
                "viewport_name": plugin_result.get("viewport_name"),
            }
            return [meta, Image(data=base64.b64decode(b64_plugin), format="png")]

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
    if _current_metrics_cache is not None:
        return dict(_current_metrics_cache)
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
        global _current_params, _current_site_width, _current_site_depth, _current_metrics_cache

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
        _current_params = {k: float(v) for k, v in combined.items()}
        _current_site_width = float(site_width)
        _current_site_depth = float(site_depth)
        for key, value in combined.items():
            if key in slider_guids:
                _gh("gh_set_slider", {"instance_guid": slider_guids[key], "value": value})

        run_result = _gh("gh_run_solution", {"wait_ms": 15000})
        if not run_result.get("ok"):
            return {"ok": False, "error": f"GH solution failed: {run_result.get('error')}"}

        layer = f"{layer_prefix}::Massing::{typology}"
        if bake_guid:
            _gh("gh_bake_component", {"instance_guid": bake_guid, "layer": layer})

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

        metrics = _estimate_typology_metrics(typology, site_width, site_depth, _current_params)
        _current_metrics_cache = metrics
        return {"ok": True, "typology": typology, "layer": layer, **metrics}

    @mcp.tool(annotations=ToolAnnotations(title="Update Urban Massing Parameter", destructiveHint=True))
    def urban_update_param(
        param_name: str,
        value: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Update a single slider parameter on the currently open Grasshopper massing
        definition and re-run the solver.

        param_name: NickName of the slider to update, e.g. "floor_count".
        value: New value. Grasshopper clamps to the slider's min/max.
        Returns {ok, param_name, gfa_m2, far, unit_count_est, open_space_pct}.
        """
        if param_name not in _current_slider_guids:
            active = sorted(_current_slider_guids.keys()) or ["none - call urban_generate_massing first"]
            return {
                "ok": False,
                "error": f"Unknown param '{param_name}' for current typology '{_current_typology}'. "
                         f"Valid params: {active}",
            }

        set_result = _gh(
            "gh_set_slider",
            {"instance_guid": _current_slider_guids[param_name], "value": value},
        )
        if not set_result.get("ok"):
            return {"ok": False, "error": f"Failed to set '{param_name}': {set_result.get('error')}"}

        run_result = _gh("gh_run_solution", {"wait_ms": 15000})
        if not run_result.get("ok"):
            return {"ok": False, "error": f"GH solution failed: {run_result.get('error')}"}

        if _current_typology and _current_site_width is not None and _current_site_depth is not None:
            _current_params[param_name] = float(value)
            global _current_metrics_cache
            _current_metrics_cache = _estimate_typology_metrics(
                _current_typology,
                _current_site_width,
                _current_site_depth,
                _current_params,
            )
        metrics = _urban_get_metrics()
        return {"ok": True, "param_name": param_name, **metrics}

    @mcp.tool(annotations=ToolAnnotations(title="Capture and Evaluate Urban Massing", readOnlyHint=True))
    def urban_capture_and_evaluate(rhino_id: str | None = None) -> list[object]:
        """
        Capture the active Rhino viewport and read massing metrics in one call.

        Returns [metrics_dict, Image] on successful capture, or [metrics_dict]
        when capture fails.
        """
        metrics = _urban_get_metrics()
        capture = _capture_view()
        if len(capture) >= 2:
            return [metrics, capture[1]]
        return [metrics]

    @mcp.tool(annotations=ToolAnnotations(title="Run Urban Environmental Analysis", destructiveHint=True))
    def urban_run_analysis(
        analysis_type: str,
        geometry_layer: str,
        climate_zone: str = "London",
        epw_path: str | None = None,
        analysis_period: str = "Jun 21 9am-5pm",
        grid_size: float = 1.0,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Run environmental analysis on baked massing geometry using Grasshopper.

        Currently supports analysis_type="solar". The analysis definition is
        expected to expose NickNames for epw_path, geometry_layer,
        analysis_period, grid_size, radiation_mesh, avg_radiation_kwh_m2, and
        overshadow_hours_worst.
        """
        if analysis_type not in _ANALYSIS_GH_MAP:
            return {
                "ok": False,
                "error": f"Unknown analysis_type '{analysis_type}'. Supported: {sorted(_ANALYSIS_GH_MAP)}",
            }

        if epw_path:
            resolved_epw = epw_path
        elif climate_zone in _EPW_DEFAULTS:
            resolved_epw = os.path.join(_EPW_BASE, _EPW_DEFAULTS[climate_zone])
        else:
            return {
                "ok": False,
                "error": f"Unknown climate_zone '{climate_zone}'. Known: {sorted(_EPW_DEFAULTS)}. "
                         "Pass epw_path directly for custom locations.",
            }

        gh_path = _ANALYSIS_GH_MAP[analysis_type]
        open_result = _gh("gh_open_document", {"path": gh_path})
        if not open_result.get("ok"):
            return {"ok": False, "error": f"Failed to open {gh_path}: {open_result.get('error')}"}

        guid_map = _discover_gh_nicknames()

        for panel_name, text in [
            ("epw_path", resolved_epw),
            ("geometry_layer", geometry_layer),
            ("analysis_period", analysis_period),
        ]:
            if panel_name in guid_map:
                _gh("gh_set_panel", {"instance_guid": guid_map[panel_name], "text": text})

        if "grid_size" in guid_map:
            _gh("gh_set_slider", {"instance_guid": guid_map["grid_size"], "value": grid_size})

        run_result = _gh("gh_run_solution", {"wait_ms": 120000})
        if not run_result.get("ok"):
            return {"ok": False, "error": f"Analysis solve failed: {run_result.get('error')}"}

        if "radiation_mesh" in guid_map:
            _gh(
                "gh_bake_component",
                {
                    "instance_guid": guid_map["radiation_mesh"],
                    "layer": f"{geometry_layer}::Analysis::Solar",
                },
            )

        avg_rad = 0.0
        overshadow = 0.0
        for out_name, key in [
            ("avg_radiation_kwh_m2", "avg_rad"),
            ("overshadow_hours_worst", "overshadow"),
        ]:
            if out_name not in guid_map:
                continue
            out = _gh("gh_get_output", {"instance_guid": guid_map[out_name]})
            if not out.get("ok"):
                continue
            outputs = out.get("result", {}).get("outputs", [])
            for item in outputs:
                vals = item.get("values", [])
                if not vals:
                    continue
                try:
                    value = float(str(vals[0]))
                except ValueError:
                    continue
                if key == "avg_rad":
                    avg_rad = value
                else:
                    overshadow = value

        return {
            "ok": True,
            "analysis_type": analysis_type,
            "avg_radiation_kwh_m2": avg_rad,
            "overshadow_hours_worst": overshadow,
            "epw_used": resolved_epw,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Clear Urban Massing", destructiveHint=True))
    def urban_clear_massing(
        layer_prefix: str = "Urban",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete all baked urban massing and analysis objects on matching layers.

        layer_prefix defaults to "Urban". Pass "Urban::Massing" to clear only
        generated massing layers while keeping analysis layers elsewhere.
        """
        global _current_typology, _current_slider_guids, _current_metrics_guid, _current_bake_guid
        global _current_params, _current_site_width, _current_site_depth, _current_metrics_cache

        code = (
            "import Rhino\n"
            "doc = Rhino.RhinoDoc.ActiveDoc\n"
            "deleted = 0\n"
            f"prefix = {layer_prefix!r}\n"
            "layer_indices = set()\n"
            "for layer in doc.Layers:\n"
            "    if not layer.IsDeleted and str(layer.FullPath).startswith(prefix):\n"
            "        layer_indices.add(layer.Index)\n"
            "for obj in list(doc.Objects):\n"
            "    if obj.IsDeleted:\n"
            "        continue\n"
            "    if obj.Attributes.LayerIndex in layer_indices:\n"
            "        if doc.Objects.Delete(obj, True):\n"
            "            deleted += 1\n"
            "doc.Views.Redraw()\n"
            "print(deleted)\n"
            "result = {'deleted': deleted}"
        )
        raw = rhino.execute_python(code)
        deleted = 0
        if isinstance(raw, dict):
            r = raw.get("result", {})
            if isinstance(r, dict):
                deleted = int(r.get("deleted", 0))
                output = r.get("output")
                if output is not None:
                    lines = str(output).strip().splitlines()
                    if lines:
                        try:
                            deleted = int(lines[-1].strip())
                        except ValueError:
                            pass

        _current_typology = None
        _current_slider_guids = {}
        _current_metrics_guid = None
        _current_bake_guid = None
        _current_params = {}
        _current_site_width = None
        _current_site_depth = None
        _current_metrics_cache = None

        return {"ok": True, "deleted": deleted}

    @mcp.tool(annotations=ToolAnnotations(title="Parse Urban Prompt", readOnlyHint=True))
    def parse_urban_prompt(prompt: str, rhino_id: str | None = None) -> dict[str, object]:
        """
        Parse a natural-language urban design brief into structured parameters.

        Returns typology, FAR target, site dimensions, use mix, climate zone,
        generated slider params, missing fields, and confidence. This is a
        deterministic schema guard for LLM clients.
        """
        return _parse_urban_prompt_text(prompt)

    @mcp.tool(annotations=ToolAnnotations(title="Generate Site Layout", destructiveHint=True))
    def generate_site_layout(
        site_width: float,
        site_depth: float,
        block_width: float = 80.0,
        block_depth: float = 60.0,
        road_width: float = 12.0,
        grid_rotation: float = 0.0,
        bake: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Generate a parcel/block layout for a site.

        Returns structured parcel geometry metadata. When bake=True, also drives
        the street_grid Grasshopper definition and bakes the plot geometry.
        """
        layout = _build_site_layout(site_width, site_depth, block_width, block_depth, road_width)
        layout["grid_rotation"] = float(grid_rotation)
        if not bake:
            return {"ok": True, "layout": layout}

        generated = urban_generate_massing(
            typology="street_grid",
            site_origin=[0.0, 0.0, 0.0],
            site_width=site_width,
            site_depth=site_depth,
            params={
                "block_width": block_width,
                "block_depth": block_depth,
                "road_width": road_width,
                "grid_rotation": grid_rotation,
            },
            rhino_id=rhino_id,
        )
        return {"ok": bool(generated.get("ok")), "layout": layout, "massing": generated}

    @mcp.tool(annotations=ToolAnnotations(title="Generate Massing", destructiveHint=True))
    def generate_massing(
        typology: str,
        site_width: float,
        site_depth: float,
        site_origin: list[float] | None = None,
        params: dict[str, float] | None = None,
        layer_prefix: str = "Urban",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        PRD-facing alias for urban_generate_massing.
        """
        return urban_generate_massing(
            typology=typology,
            site_origin=site_origin or [0.0, 0.0, 0.0],
            site_width=site_width,
            site_depth=site_depth,
            params=params,
            layer_prefix=layer_prefix,
            rhino_id=rhino_id,
        )

    @mcp.tool(annotations=ToolAnnotations(title="Calculate Urban Metrics", readOnlyHint=True))
    def calculate_urban_metrics(
        site_width: float | None = None,
        site_depth: float | None = None,
        gfa_m2: float | None = None,
        residential_pct: float = 70.0,
        open_space_pct: float | None = None,
        far_target: float | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Calculate FAR, GFA, estimated units, open space, and target validation.

        If gfa_m2 is omitted, reads the active urban Grasshopper metrics panel.
        """
        current = _urban_get_metrics()
        width = _to_float(site_width, 0.0)
        depth = _to_float(site_depth, 0.0)
        gfa = _to_float(gfa_m2, _to_float(current.get("gfa_m2"), 0.0))
        open_space = _to_float(open_space_pct, _to_float(current.get("open_space_pct"), 0.0))
        if width <= 0 or depth <= 0:
            far = _to_float(current.get("far"), 0.0)
            site_area = (gfa / far) if far else 0.0
            result = {
                "site_area_m2": round(site_area, 2),
                "gfa_m2": round(gfa, 2),
                "far": round(far, 3),
                "unit_count_est": int(_to_float(current.get("unit_count_est"), 0.0)),
                "open_space_pct": round(open_space, 2),
            }
            if far_target is not None:
                delta = far - float(far_target)
                result["far_target"] = float(far_target)
                result["far_delta"] = round(delta, 3)
                result["far_within_2pct"] = abs(delta) <= max(0.02 * float(far_target), 0.02)
            return {"ok": True, "metrics": result}
        return {"ok": True, "metrics": _calculate_metrics(width, depth, gfa, residential_pct, open_space, far_target)}

    @mcp.tool(annotations=ToolAnnotations(title="Optimize Urban Plan", destructiveHint=True))
    def optimize_plan(
        target_far: float,
        site_width: float,
        site_depth: float,
        typology: str | None = None,
        params: dict[str, float] | None = None,
        apply: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Produce a simple FAR-targeted parameter recommendation.

        When apply=True, regenerates the recommended massing immediately.
        """
        chosen = typology or _recommend_typology(float(target_far))
        recommended = dict(params or {})
        if chosen == "tower":
            footprint = float(recommended.get("footprint_width", 22.0)) * float(recommended.get("footprint_depth", 22.0))
            floors = max(5, round((float(target_far) * site_width * site_depth) / max(footprint, 1.0)))
            recommended["floor_count"] = float(min(80, floors))
        elif chosen == "podium_tower":
            podium_floors = float(recommended.get("podium_floors", 4.0))
            setback = float(recommended.get("podium_setback", 3.0))
            podium_fp = max(0.0, float(site_width) - 2.0 * setback) * max(0.0, float(site_depth) - 2.0 * setback)
            podium_gfa = podium_fp * podium_floors
            tower_fp = float(recommended.get("footprint_width", 22.0)) * float(recommended.get("footprint_depth", 22.0))
            target_gfa = float(target_far) * float(site_width) * float(site_depth)
            tower_floors = max(5.0, (target_gfa - podium_gfa) / max(tower_fp, 1.0))
            recommended["podium_floors"] = podium_floors
            recommended.setdefault("podium_setback", setback)
            recommended["tower_floors"] = float(min(60, tower_floors))
        elif chosen in {"courtyard", "perimeter_block"}:
            recommended["floor_count"] = float(min(12 if chosen == "courtyard" else 10, max(2, round(float(target_far)))))
        elif chosen == "street_grid":
            recommended.update({"block_width": 80.0, "block_depth": 60.0, "road_width": 12.0})

        result: dict[str, object] = {
            "ok": True,
            "typology": chosen,
            "target_far": float(target_far),
            "recommended_params": recommended,
            "strategy": "heuristic_far_fit",
        }
        if apply:
            result["massing"] = urban_generate_massing(
                typology=chosen,
                site_origin=[0.0, 0.0, 0.0],
                site_width=site_width,
                site_depth=site_depth,
                params=recommended,
                rhino_id=rhino_id,
            )
        return result

    @mcp.tool(annotations=ToolAnnotations(title="Render Urban Preview", readOnlyHint=True))
    def render_urban_preview(rhino_id: str | None = None) -> list[object]:
        """
        Return current urban metrics plus a viewport preview image.
        """
        return urban_capture_and_evaluate(rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Export Urban Model", destructiveHint=True))
    def export_model(
        output_format: str = "3dm",
        path: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Export the active Rhino document/model.

        Supports 3dm, glb/gltf, geojson, and pdf paths. GeoJSON export returns
        a lightweight layer/object manifest when full GIS export is unavailable.
        """
        fmt = output_format.lower().lstrip(".")
        if fmt not in {"3dm", "glb", "gltf", "geojson", "pdf"}:
            return {"ok": False, "error": "output_format must be one of 3dm, glb, gltf, geojson, pdf"}
        export_path = path or os.path.join("/tmp", f"urban_export_{_dt.datetime.now(_dt.UTC).strftime('%Y%m%d_%H%M%S')}.{fmt}")
        if fmt == "geojson":
            code = (
                "import json, Rhino\n"
                "doc = Rhino.RhinoDoc.ActiveDoc\n"
                "features = []\n"
                "for obj in doc.Objects:\n"
                "    if obj.IsDeleted: continue\n"
                "    bbox = obj.Geometry.GetBoundingBox(True)\n"
                "    layer = doc.Layers[obj.Attributes.LayerIndex].FullPath if obj.Attributes.LayerIndex >= 0 else ''\n"
                "    features.append({'type':'Feature','properties':{'id':str(obj.Id),'layer':layer,'bbox':[[bbox.Min.X,bbox.Min.Y,bbox.Min.Z],[bbox.Max.X,bbox.Max.Y,bbox.Max.Z]]},'geometry':None})\n"
                f"open({export_path!r}, 'w').write(json.dumps({{'type':'FeatureCollection','features':features}}))\n"
                f"print({export_path!r})\n"
            )
        elif fmt == "3dm":
            code = f"import Rhino\nok = Rhino.RhinoDoc.ActiveDoc.WriteFile({export_path!r}, Rhino.FileIO.FileWriteOptions())\nprint({export_path!r} if ok else 'FAILED')\n"
        else:
            macro = f'_-Export "{export_path}" _Enter'
            code = f"import Rhino\nok = Rhino.RhinoApp.RunScript({macro!r}, False)\nprint({export_path!r} if ok else 'FAILED')\n"
        raw = rhino.execute_python(code, rhino_id=rhino_id)
        ok = isinstance(raw, dict) and "FAILED" not in str(raw)
        return {"ok": ok, "format": fmt, "path": export_path, "raw": raw}

    @mcp.tool(annotations=ToolAnnotations(title="Save Urban Project Version", destructiveHint=True))
    def save_project_version(
        project_name: str,
        version_name: str | None = None,
        directory: str = "/tmp/rhino_mcp_versions",
        metadata: dict[str, object] | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Save a timestamped design version manifest and 3DM export.
        """
        safe_project = re.sub(r"[^A-Za-z0-9_.-]+", "_", project_name).strip("_") or "urban_project"
        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")
        safe_version = re.sub(r"[^A-Za-z0-9_.-]+", "_", version_name or stamp).strip("_")
        folder = os.path.join(directory, safe_project, safe_version)
        os.makedirs(folder, exist_ok=True)
        model_path = os.path.join(folder, f"{safe_project}_{safe_version}.3dm")
        manifest_path = os.path.join(folder, "version.json")
        export = export_model("3dm", model_path, rhino_id=rhino_id)
        manifest = {
            "project_name": project_name,
            "version_name": version_name or stamp,
            "created_utc": _dt.datetime.now(_dt.UTC).isoformat().replace("+00:00", "Z"),
            "model_path": model_path,
            "metadata": metadata or {},
            "export_ok": export.get("ok"),
        }
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
        return {"ok": True, "directory": folder, "model_path": model_path, "manifest_path": manifest_path, "export": export}

    @mcp.tool(annotations=ToolAnnotations(title="Create Urban Scheme", destructiveHint=True))
    def create_urban_scheme(
        prompt: str,
        site_boundary: dict[str, object] | None = None,
        output_format: str | None = None,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        PRD orchestrator: parse prompt, generate layout/massing, calculate
        metrics, optionally export the result.
        """
        parsed = parse_urban_prompt(prompt, rhino_id=rhino_id)
        boundary = _site_dimensions_from_boundary(site_boundary)
        if boundary.get("ok"):
            if parsed.get("site_width") is None:
                parsed["site_width"] = boundary["site_width"]
            if parsed.get("site_depth") is None:
                parsed["site_depth"] = boundary["site_depth"]
            parsed["missing_fields"] = [
                field for field in parsed.get("missing_fields", [])
                if field not in {"site_width", "site_depth"}
            ]
        if parsed.get("missing_fields"):
            return {"ok": False, "stage": "parse", "parsed": parsed, "error": "Missing required fields"}

        site_width = float(parsed["site_width"])
        site_depth = float(parsed["site_depth"])
        typology = str(parsed["typology"])
        optimized = optimize_plan(
            target_far=_to_float(parsed.get("far_target"), 0.0),
            site_width=site_width,
            site_depth=site_depth,
            typology=typology,
            params=parsed.get("params") if isinstance(parsed.get("params"), dict) else None,
            apply=False,
            rhino_id=rhino_id,
        )
        scheme_params = optimized.get("recommended_params") if isinstance(optimized.get("recommended_params"), dict) else parsed.get("params")
        layout = generate_site_layout(site_width, site_depth, bake=(typology == "street_grid"), rhino_id=rhino_id)
        massing = generate_massing(
            typology=typology,
            site_width=site_width,
            site_depth=site_depth,
            site_origin=parsed.get("site_origin") if isinstance(parsed.get("site_origin"), list) else [0.0, 0.0, 0.0],
            params=scheme_params if isinstance(scheme_params, dict) else None,
            rhino_id=rhino_id,
        )
        metrics = calculate_urban_metrics(
            site_width=site_width,
            site_depth=site_depth,
            gfa_m2=_to_float(massing.get("gfa_m2"), 0.0),
            residential_pct=_to_float(parsed.get("use_mix", {}).get("residential_pct") if isinstance(parsed.get("use_mix"), dict) else 70.0, 70.0),
            open_space_pct=_to_float(massing.get("open_space_pct"), 0.0),
            far_target=_to_float(parsed.get("far_target"), 0.0),
            rhino_id=rhino_id,
        )
        export = export_model(output_format, rhino_id=rhino_id) if output_format else None
        summary = f"Generated {typology} scheme with FAR {metrics.get('metrics', {}).get('far', 0)}"
        return {
            "ok": bool(massing.get("ok")),
            "summary": summary,
            "parsed": parsed,
            "layout": layout,
            "massing": massing,
            "metrics": metrics.get("metrics", {}),
            "downloads": export,
            "site_boundary": boundary if site_boundary is not None else None,
            "site_boundary_received": site_boundary is not None,
        }

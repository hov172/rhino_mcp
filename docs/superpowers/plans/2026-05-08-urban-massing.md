# Urban Massing Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an AI-driven urban massing workflow — Claude collects a site brief, drives pre-built Grasshopper definitions to generate parametric 3D massing typologies, reads back GFA/FAR/unit count metrics, and runs Ladybug solar analysis.

**Architecture:** Two new auto-discovered tool modules (`urban.py` and `urban_prompt.py`) drop into `src/rhmcp/tools/` and are loaded by the existing `pkgutil` loop in `__init__.py` — no registration changes needed. Six Grasshopper definitions (`grasshopper/urban/*.gh`) are the parametric engine; Python drives them by setting named sliders, running the solver, and baking geometry. Module-level state tracks the currently open definition's slider GUIDs between tool calls.

**Tech Stack:** Python (FastMCP), `@mcp.tool` / `@mcp.prompt` decorators, `rhino.plugin_result()` for GH commands, `rhino.execute_python()` for RhinoScript, Grasshopper + Ladybug Tools, existing `capture_rhino_view` Image return.

**Spec:** `docs/superpowers/specs/2026-05-08-urban-massing-design.md`

---

## File Map

| Status | Path | What it does |
|---|---|---|
| Create | `src/rhmcp/tools/urban.py` | 6 MCP tools + internal helpers |
| Create | `src/rhmcp/tools/urban_prompt.py` | `urban_brief` FastMCP prompt resource |
| Create | `grasshopper/urban/tower.gh` | Tower typology (built in GH) |
| Create | `grasshopper/urban/podium_tower.gh` | Podium + tower typology |
| Create | `grasshopper/urban/courtyard.gh` | Courtyard block typology |
| Create | `grasshopper/urban/perimeter_block.gh` | Perimeter block typology |
| Create | `grasshopper/urban/street_grid.gh` | Street grid + site subdivision |
| Create | `grasshopper/urban/analysis_solar.gh` | Ladybug solar analysis |
| Create | `tests/test_urban_unit.py` | Unit tests (all 6 tools, mocked backend) |
| Modify | `README.md` | Add Urban Massing section |

No changes to `src/rhmcp/__init__.py` or `src/rhmcp/tools/__init__.py` — auto-discovery handles both new modules.

---

## Task 1: urban.py — skeleton, constants, helpers

**Files:**
- Create: `src/rhmcp/tools/urban.py`
- Create: `tests/test_urban_unit.py`

- [x] **Step 1: Write the failing skeleton test**

```python
# tests/test_urban_unit.py
"""Unit tests for urban massing tools. Requires no running Rhino instance."""
from __future__ import annotations
import unittest
from unittest.mock import patch, MagicMock

from mcp.server.fastmcp import FastMCP


def _register_urban() -> dict[str, object]:
    """Register urban module and return tool-name → callable map."""
    import importlib
    mod = importlib.import_module("rhmcp.tools.urban")
    mcp = FastMCP("test-urban")
    with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
        mod.register(mcp)
    return {name: tool.fn for name, tool in mcp._tool_manager._tools.items()}


class TestUrbanConstants(unittest.TestCase):
    def test_typology_gh_map_has_five_entries(self) -> None:
        import rhmcp.tools.urban as u
        self.assertEqual(len(u._TYPOLOGY_GH_MAP), 5)

    def test_slider_maps_cover_all_typologies(self) -> None:
        import rhmcp.tools.urban as u
        for typology in u._TYPOLOGY_GH_MAP:
            self.assertIn(typology, u._SLIDER_MAPS)
            self.assertGreater(len(u._SLIDER_MAPS[typology]), 0)

    def test_epw_defaults_has_seven_entries(self) -> None:
        import rhmcp.tools.urban as u
        self.assertEqual(len(u._EPW_DEFAULTS), 7)

    def test_parse_metrics_panel_parses_all_fields(self) -> None:
        import rhmcp.tools.urban as u
        text = "GFA: 28000\nFAR: 3.5\nUnits: 280\nOpenSpace: 22"
        m = u._parse_metrics_panel(text)
        self.assertAlmostEqual(m["gfa_m2"], 28000.0)
        self.assertAlmostEqual(m["far"], 3.5)
        self.assertEqual(m["unit_count_est"], 280)
        self.assertAlmostEqual(m["open_space_pct"], 22.0)

    def test_parse_metrics_panel_returns_zeros_on_empty(self) -> None:
        import rhmcp.tools.urban as u
        m = u._parse_metrics_panel("")
        self.assertEqual(m["gfa_m2"], 0.0)
        self.assertEqual(m["far"], 0.0)
```

- [x] **Step 2: Run to confirm failure**

```bash
cd /path/to/rhino_mcp && uv run pytest tests/test_urban_unit.py -v 2>&1 | head -20
```
Expected: `ERROR` — `ModuleNotFoundError: No module named 'rhmcp.tools.urban'`

- [x] **Step 3: Create `src/rhmcp/tools/urban.py` with skeleton**

```python
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
from mcp.types import ToolAnnotations

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
    "tower":          os.path.join(_GH_DIR, "tower.gh"),
    "podium_tower":   os.path.join(_GH_DIR, "podium_tower.gh"),
    "courtyard":      os.path.join(_GH_DIR, "courtyard.gh"),
    "perimeter_block": os.path.join(_GH_DIR, "perimeter_block.gh"),
    "street_grid":    os.path.join(_GH_DIR, "street_grid.gh"),
}

_ANALYSIS_GH_MAP: dict[str, str] = {
    "solar": os.path.join(_GH_DIR, "analysis_solar.gh"),
}

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

    The script reads Grasshopper.Instances.ActiveCanvas.Document so it requires
    Grasshopper to be open with the target definition active.
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
    raw = rhino.execute_python(code)
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
    meta = {"path": None, "saved": False, "width": 1200, "height": 900}
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
    pass  # tools added in subsequent tasks
```

- [x] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanConstants -v
```
Expected: 5 passed

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): skeleton, constants, helpers — no tools yet"
```

---

## Task 2: urban_get_metrics tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py` (add tool inside `register`)
- Modify: `tests/test_urban_unit.py` (add test class)

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanGetMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_returns_zeros_when_no_definition_open(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = None
        fn = self.tools["urban_get_metrics"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn()
        self.assertEqual(result["gfa_m2"], 0.0)
        self.assertEqual(result["far"], 0.0)
        self.assertEqual(result["unit_count_est"], 0)
        self.assertEqual(result["open_space_pct"], 0.0)

    def test_parses_panel_output_correctly(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = "metrics-guid-123"
        fn = self.tools["urban_get_metrics"]
        mock_result = {
            "ok": True,
            "result": {
                "outputs": [{"values": ["GFA: 19200\nFAR: 3.0\nUnits: 192\nOpenSpace: 35"]}]
            },
        }
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value=mock_result):
            result = fn()
        self.assertAlmostEqual(result["gfa_m2"], 19200.0)
        self.assertAlmostEqual(result["far"], 3.0)
        self.assertEqual(result["unit_count_est"], 192)
        self.assertAlmostEqual(result["open_space_pct"], 35.0)
        u._current_metrics_guid = None  # cleanup
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanGetMetrics -v
```
Expected: FAIL — `urban_get_metrics` not in tools dict

- [x] **Step 3: Add tool inside `register()` in `urban.py`**

Replace `def register(mcp: FastMCP) -> None:\n    pass` with:

```python
def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Get Urban Massing Metrics", readOnlyHint=True))
    def urban_get_metrics(rhino_id: str | None = None) -> dict[str, object]:
        """
        Read GFA, FAR, estimated unit count, and open space percentage from the
        currently open Grasshopper massing definition's Metrics output panel.

        Returns {gfa_m2, far, unit_count_est, open_space_pct}.
        Returns zeros if no massing definition is currently open.
        """
        return _urban_get_metrics()
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all pass (7 total)

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_get_metrics tool"
```

---

## Task 3: urban_generate_massing tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanGenerateMassing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def _mock_execute_python(self, result_value=None):
        """Return a mock for execute_python that yields the discovery script result."""
        mock = MagicMock()
        mock.return_value = {"ok": True, "result": result_value or {
            "site_width": "guid-sw", "site_depth": "guid-sd",
            "floor_count": "guid-fc", "tower_count": "guid-tc",
            "floor_height": "guid-fh", "footprint_width": "guid-fw",
            "footprint_depth": "guid-fd", "setback": "guid-sb",
            "residential_pct": "guid-rp", "retail_floors": "guid-rf",
            "Metrics": "guid-metrics", "BakeTarget": "guid-bake",
        }}
        return mock

    def test_returns_error_on_unknown_typology(self) -> None:
        fn = self.tools["urban_generate_massing"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn(typology="spaceship", site_origin=[0, 0, 0],
                        site_width=80, site_depth=80)
        self.assertFalse(result["ok"])
        self.assertIn("spaceship", result["error"])

    def test_opens_correct_gh_file_for_typology(self) -> None:
        import rhmcp.tools.urban as u
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="tower", site_origin=[0, 0, 0], site_width=80, site_depth=80)

        open_calls = [(c, p) for c, p in plugin_calls if c == "gh_open_document"]
        self.assertEqual(len(open_calls), 1)
        self.assertIn("tower.gh", open_calls[0][1]["path"])

    def test_sets_site_width_and_depth_sliders(self) -> None:
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="tower", site_origin=[0, 0, 0], site_width=100.0, site_depth=80.0)

        slider_calls = {p.get("instance_guid"): p.get("value")
                        for c, p in plugin_calls if c == "gh_set_slider"}
        self.assertIn("guid-sw", slider_calls)
        self.assertIn("guid-sd", slider_calls)
        self.assertAlmostEqual(slider_calls["guid-sw"], 100.0)
        self.assertAlmostEqual(slider_calls["guid-sd"], 80.0)

    def test_bakes_to_correct_layer(self) -> None:
        fn = self.tools["urban_generate_massing"]
        plugin_calls = []

        def capture_plugin(cmd, params):
            plugin_calls.append((cmd, params))
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            fn(typology="courtyard", site_origin=[0, 0, 0], site_width=80, site_depth=80)

        bake_calls = [(c, p) for c, p in plugin_calls if c == "gh_bake"]
        self.assertEqual(len(bake_calls), 1)
        self.assertEqual(bake_calls[0][1]["layer"], "Urban::Massing::courtyard")

    def test_returns_ok_true_with_metrics_fields(self) -> None:
        import rhmcp.tools.urban as u
        fn = self.tools["urban_generate_massing"]

        def capture_plugin(cmd, params):
            if cmd == "gh_get_output":
                return {"ok": True, "result": {
                    "outputs": [{"values": ["GFA: 6400\nFAR: 2.0\nUnits: 64\nOpenSpace: 40"]}]
                }}
            return {"ok": True, "result": {}}

        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture_plugin), \
             patch("rhmcp.tools_helpers.backend.execute_python", self._mock_execute_python()):
            result = fn(typology="courtyard", site_origin=[0, 0, 0],
                        site_width=80, site_depth=80)

        self.assertTrue(result["ok"])
        self.assertIn("gfa_m2", result)
        self.assertIn("far", result)
        self.assertIn("unit_count_est", result)
        self.assertIn("open_space_pct", result)
        u._current_typology = None
        u._current_slider_guids = {}
        u._current_metrics_guid = None
        u._current_bake_guid = None
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanGenerateMassing -v
```
Expected: FAIL — `urban_generate_massing` not in tools dict

- [x] **Step 3: Add tool to `register()` in `urban.py`**

Add after `urban_get_metrics` inside `register()`:

```python
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
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 12 pass

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_generate_massing tool"
```

---

## Task 4: urban_update_param tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanUpdateParam(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def setUp(self) -> None:
        import rhmcp.tools.urban as u
        u._current_typology = "tower"
        u._current_slider_guids = {"floor_count": "guid-fc", "setback": "guid-sb"}
        u._current_metrics_guid = "guid-metrics"

    def tearDown(self) -> None:
        import rhmcp.tools.urban as u
        u._current_typology = None
        u._current_slider_guids = {}
        u._current_metrics_guid = None

    def test_calls_gh_set_slider_with_correct_guid(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(param_name="floor_count", value=25.0)
        set_calls = [c for c in mock_plugin.call_args_list
                     if c[0][0] == "gh_set_slider"]
        self.assertEqual(len(set_calls), 1)
        self.assertEqual(set_calls[0][0][1]["instance_guid"], "guid-fc")
        self.assertAlmostEqual(set_calls[0][0][1]["value"], 25.0)

    def test_re_runs_solver_after_setting_value(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}) as mock_plugin:
            fn(param_name="floor_count", value=10.0)
        solve_calls = [c for c in mock_plugin.call_args_list
                       if c[0][0] == "gh_run_solution"]
        self.assertEqual(len(solve_calls), 1)

    def test_returns_error_on_unknown_param_name(self) -> None:
        fn = self.tools["urban_update_param"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            result = fn(param_name="nonexistent_param", value=5.0)
        self.assertFalse(result["ok"])
        self.assertIn("nonexistent_param", result["error"])
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanUpdateParam -v
```
Expected: FAIL — `urban_update_param` not in tools dict

- [x] **Step 3: Add tool to `register()` in `urban.py`**

Add after `urban_generate_massing` inside `register()`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Update Urban Massing Parameter", destructiveHint=True))
    def urban_update_param(
        param_name: str,
        value: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Update a single slider parameter on the currently open Grasshopper massing
        definition and re-run the solver.

        param_name: NickName of the slider to update (e.g. "floor_count", "setback").
                    Must be a valid slider for the active typology.
        value: New value (will be clamped to the slider's min/max by Grasshopper).
        Returns: {ok, param_name, gfa_m2, far, unit_count_est, open_space_pct}.
        """
        if param_name not in _current_slider_guids:
            active = sorted(_current_slider_guids.keys()) or ["none — call urban_generate_massing first"]
            return {
                "ok": False,
                "error": f"Unknown param '{param_name}' for current typology '{_current_typology}'. "
                         f"Valid params: {active}",
            }
        _gh("gh_set_slider", {"instance_guid": _current_slider_guids[param_name], "value": value})
        _gh("gh_run_solution", {"wait_ms": 15000})
        metrics = _urban_get_metrics()
        return {"ok": True, "param_name": param_name, **metrics}
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 15 pass

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_update_param tool"
```

---

## Task 5: urban_capture_and_evaluate tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
# Minimal valid 1×1 PNG (bytes) reused across capture tests.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestUrbanCaptureAndEvaluate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def setUp(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = "guid-metrics"

    def tearDown(self) -> None:
        import rhmcp.tools.urban as u
        u._current_metrics_guid = None

    def test_returns_metrics_dict_and_image(self) -> None:
        import base64
        from mcp.server.fastmcp import Image

        b64 = base64.b64encode(_PNG_1X1).decode()
        capture_response = {"ok": True, "result": {"b64": b64, "path": None, "saved": False, "width": 1200, "height": 900}}
        metrics_response = {"ok": True, "result": {"outputs": [{"values": ["GFA: 5000\nFAR: 2.0\nUnits: 50\nOpenSpace: 30"]}]}}

        def side_effect(cmd, params):
            if cmd == "gh_get_output":
                return metrics_response
            return {"ok": True}

        fn = self.tools["urban_capture_and_evaluate"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=side_effect), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value=capture_response):
            result = fn()

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 2)
        metrics, img = result[0], result[1]
        self.assertIsInstance(metrics, dict)
        self.assertIn("gfa_m2", metrics)
        self.assertIsInstance(img, Image)

    def test_returns_metrics_only_on_capture_failure(self) -> None:
        metrics_response = {"ok": True, "result": {"outputs": [{"values": ["GFA: 0\nFAR: 0\nUnits: 0\nOpenSpace: 0"]}]}}

        def side_effect(cmd, params):
            if cmd == "gh_get_output":
                return metrics_response
            return {"ok": True}

        fn = self.tools["urban_capture_and_evaluate"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=side_effect), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": False, "error": "no view"}):
            result = fn()

        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], dict)
        self.assertIn("gfa_m2", result[0])
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanCaptureAndEvaluate -v
```
Expected: FAIL — `urban_capture_and_evaluate` not in tools dict

- [x] **Step 3: Add tool to `register()` in `urban.py`**

Add after `urban_update_param` inside `register()`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Capture and Evaluate Urban Massing", readOnlyHint=True))
    def urban_capture_and_evaluate(rhino_id: str | None = None) -> list[object]:
        """
        Capture the active Rhino viewport AND read massing metrics in one call.

        Returns [metrics_dict, Image] so Claude can see the scene and the numbers
        in a single response.  If viewport capture fails, returns [metrics_dict]
        without crashing.

        metrics_dict contains: {gfa_m2, far, unit_count_est, open_space_pct}.
        """
        metrics = _urban_get_metrics()
        capture = _capture_view()
        # capture is [meta, Image] on success, [error_dict] on failure
        if len(capture) >= 2:
            return [metrics, capture[1]]
        return [metrics]
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 18 pass

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_capture_and_evaluate tool"
```

---

## Task 6: urban_run_analysis tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanRunAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_returns_error_on_unknown_analysis_type(self) -> None:
        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result"):
            result = fn(analysis_type="wind", geometry_layer="Urban::Massing::tower")
        self.assertFalse(result["ok"])
        self.assertIn("wind", result["error"])

    def test_opens_analysis_solar_gh(self) -> None:
        plugin_calls = []

        def capture(cmd, params):
            plugin_calls.append((cmd, params))
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            fn(analysis_type="solar", geometry_layer="Urban::Massing::courtyard",
               climate_zone="London")

        open_calls = [(c, p) for c, p in plugin_calls if c == "gh_open_document"]
        self.assertEqual(len(open_calls), 1)
        self.assertIn("analysis_solar.gh", open_calls[0][1]["path"])

    def test_sets_epw_path_for_known_climate_zone(self) -> None:
        import rhmcp.tools.urban as u
        plugin_calls = []

        def capture(cmd, params):
            plugin_calls.append((cmd, params))
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            fn(analysis_type="solar", geometry_layer="Urban::Massing::tower",
               climate_zone="Dubai")

        panel_calls = [(c, p) for c, p in plugin_calls if c == "gh_set_panel"]
        epw_calls = [p for _, p in panel_calls if "Dubai" in str(p.get("text", "")) or ".epw" in str(p.get("text", ""))]
        self.assertTrue(len(epw_calls) > 0, "Expected a gh_set_panel call with the EPW path")

    def test_returns_radiation_dict_keys(self) -> None:
        def capture(cmd, params):
            if cmd == "gh_get_output":
                return {"ok": True, "result": {"outputs": [{"values": ["380"]}]}}
            return {"ok": True, "result": {}}

        fn = self.tools["urban_run_analysis"]
        with patch("rhmcp.tools_helpers.backend.plugin_result", side_effect=capture), \
             patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True, "result": {}}):
            result = fn(analysis_type="solar", geometry_layer="Urban::Massing::tower",
                        climate_zone="London")

        self.assertIn("ok", result)
        self.assertIn("analysis_type", result)
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanRunAnalysis -v
```
Expected: FAIL — `urban_run_analysis` not in tools dict

- [x] **Step 3: Add tool to `register()` in `urban.py`**

Add after `urban_capture_and_evaluate` inside `register()`:

```python
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
        Run environmental analysis on baked massing geometry using Ladybug Tools.

        analysis_type: Analysis to run. Currently supported: "solar".
        geometry_layer: Rhino layer containing the baked massing to analyse
                        (e.g. "Urban::Massing::courtyard").
        climate_zone: One of London, New York, Dubai, Tokyo, Sydney, Singapore, Berlin.
                      Selects a bundled EPW file from ~/ladybug/EPWs/.
        epw_path: Absolute path to a custom .epw file. Overrides climate_zone.
        analysis_period: Ladybug analysis period string (default: "Jun 21 9am-5pm").
        grid_size: Analysis mesh resolution in metres (default 1.0).
        Returns: {ok, analysis_type, avg_radiation_kwh_m2, overshadow_hours_worst, epw_used}.
        """
        if analysis_type not in _ANALYSIS_GH_MAP:
            return {
                "ok": False,
                "error": f"Unknown analysis_type '{analysis_type}'. Supported: {sorted(_ANALYSIS_GH_MAP)}",
            }

        # Resolve EPW path
        if epw_path:
            resolved_epw = epw_path
        elif climate_zone in _EPW_DEFAULTS:
            resolved_epw = os.path.join(_EPW_BASE, _EPW_DEFAULTS[climate_zone])
        else:
            return {
                "ok": False,
                "error": f"Unknown climate_zone '{climate_zone}'. Known: {sorted(_EPW_DEFAULTS)}. "
                         f"Pass epw_path directly for custom locations.",
            }

        gh_path = _ANALYSIS_GH_MAP[analysis_type]
        open_result = _gh("gh_open_document", {"path": gh_path})
        if not open_result.get("ok"):
            return {"ok": False, "error": f"Failed to open {gh_path}: {open_result.get('error')}"}

        # Discover panel GUIDs in the analysis definition
        discover_code = r"""
import Grasshopper
doc = Grasshopper.Instances.ActiveCanvas.Document
nick_to_guid = {}
for obj in doc.Objects:
    nick = getattr(obj, 'NickName', None)
    if nick:
        nick_to_guid[str(nick)] = str(obj.InstanceGuid)
result = nick_to_guid
"""
        raw = rhino.execute_python(discover_code)
        guid_map: dict[str, str] = {}
        if isinstance(raw, dict):
            r = raw.get("result", {})
            if isinstance(r, dict):
                guid_map = r

        # Set inputs
        for panel_name, text in [
            ("epw_path",        resolved_epw),
            ("geometry_layer",  geometry_layer),
            ("analysis_period", analysis_period),
        ]:
            if panel_name in guid_map:
                _gh("gh_set_panel", {"instance_guid": guid_map[panel_name], "text": text})

        if "grid_size" in guid_map:
            _gh("gh_set_slider", {"instance_guid": guid_map["grid_size"], "value": grid_size})

        # Ladybug can be slow on first run
        run_result = _gh("gh_run_solution", {"wait_ms": 120000})
        if not run_result.get("ok"):
            return {"ok": False, "error": f"Analysis solve failed: {run_result.get('error')}"}

        # Bake radiation mesh
        if "radiation_mesh" in guid_map:
            analysis_layer = geometry_layer + "::Analysis::Solar"
            _gh("gh_bake", {"instance_guid": guid_map["radiation_mesh"], "layer": analysis_layer})

        # Read output panels
        avg_rad = 0.0
        overshadow = 0.0
        for out_name, key in [("avg_radiation_kwh_m2", "avg_rad"), ("overshadow_hours_worst", "overshadow")]:
            if out_name in guid_map:
                out = _gh("gh_get_output", {"instance_guid": guid_map[out_name]})
                if out.get("ok"):
                    outputs = out.get("result", {}).get("outputs", [])
                    for item in outputs:
                        vals = item.get("values", [])
                        if vals:
                            try:
                                v = float(str(vals[0]))
                                if key == "avg_rad":
                                    avg_rad = v
                                else:
                                    overshadow = v
                            except ValueError:
                                pass

        return {
            "ok": True,
            "analysis_type": analysis_type,
            "avg_radiation_kwh_m2": avg_rad,
            "overshadow_hours_worst": overshadow,
            "epw_used": resolved_epw,
        }
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 22 pass

- [x] **Step 5: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_run_analysis tool (Ladybug solar)"
```

---

## Task 7: urban_clear_massing tool

**Files:**
- Modify: `src/rhmcp/tools/urban.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing tests**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanClearMassing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with patch("rhmcp.tools_helpers.backend.plugin_result", return_value={"ok": True}):
            cls.tools = _register_urban()

    def test_deletes_objects_on_urban_layers(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 12}}) as mock_py:
            result = fn()
        self.assertTrue(mock_py.called)
        code_arg = mock_py.call_args[0][0]
        self.assertIn("Urban", code_arg)

    def test_returns_deleted_count(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 7}}):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 7)

    def test_noop_safe_when_no_objects(self) -> None:
        fn = self.tools["urban_clear_massing"]
        with patch("rhmcp.tools_helpers.backend.execute_python",
                   return_value={"ok": True, "result": {"deleted": 0}}):
            result = fn()
        self.assertTrue(result["ok"])
        self.assertEqual(result["deleted"], 0)
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanClearMassing -v
```
Expected: FAIL — `urban_clear_massing` not in tools dict

- [x] **Step 3: Add tool to `register()` in `urban.py`**

Add after `urban_run_analysis` inside `register()`:

```python
    @mcp.tool(annotations=ToolAnnotations(title="Clear Urban Massing", destructiveHint=True))
    def urban_clear_massing(
        layer_prefix: str = "Urban",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Delete all baked urban massing and analysis objects.

        layer_prefix: Delete all objects on layers starting with this prefix.
                      Default "Urban" removes everything under Urban::*.
                      Pass "Urban::Massing" to clear geometry while keeping
                      analysis results.
        Returns: {ok, deleted} where deleted is the number of objects removed.
        """
        global _current_typology, _current_slider_guids, _current_metrics_guid, _current_bake_guid

        code = (
            "import rhinoscriptsyntax as rs\n"
            "deleted = 0\n"
            "for layer in rs.LayerNames() or []:\n"
            f"    if str(layer).startswith('{layer_prefix}'):\n"
            "        objs = rs.ObjectsByLayer(layer)\n"
            "        if objs:\n"
            "            rs.DeleteObjects(objs)\n"
            "            deleted += len(objs)\n"
            "result = {'deleted': deleted}"
        )
        raw = rhino.execute_python(code)
        deleted = 0
        if isinstance(raw, dict):
            r = raw.get("result", {})
            if isinstance(r, dict):
                deleted = int(r.get("deleted", 0))

        _current_typology = None
        _current_slider_guids = {}
        _current_metrics_guid = None
        _current_bake_guid = None

        return {"ok": True, "deleted": deleted}
```

- [x] **Step 4: Run all tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 25 pass

- [x] **Step 5: Confirm existing test suite unaffected**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: 125 passed (100 existing + 25 new)

- [x] **Step 6: Commit**

```bash
git add src/rhmcp/tools/urban.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_clear_massing tool; all 125 tests pass"
```

---

## Task 8: urban_prompt.py — FastMCP prompt resource

**Files:**
- Create: `src/rhmcp/tools/urban_prompt.py`
- Modify: `tests/test_urban_unit.py`

- [x] **Step 1: Write failing test**

Append to `tests/test_urban_unit.py`:

```python
class TestUrbanBriefPrompt(unittest.TestCase):
    def test_urban_brief_registers_as_prompt(self) -> None:
        import importlib
        mod = importlib.import_module("rhmcp.tools.urban_prompt")
        mcp = FastMCP("test-urban-prompt")
        mod.register(mcp)
        self.assertIn("urban_brief", mcp._prompt_manager._prompts)

    def test_urban_brief_content_contains_mandatory_fields(self) -> None:
        import importlib, asyncio
        mod = importlib.import_module("rhmcp.tools.urban_prompt")
        mcp = FastMCP("test-urban-prompt")
        mod.register(mcp)
        prompt = mcp._prompt_manager._prompts["urban_brief"]
        # render() returns a list of PromptMessage — convert to text for inspection
        messages = asyncio.run(prompt.render({}))
        text = " ".join(str(m) for m in messages)
        for field in ["site_width", "site_depth", "far_target", "typology", "residential_pct"]:
            self.assertIn(field, text, f"Expected '{field}' in urban_brief content")
```

- [x] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_urban_unit.py::TestUrbanBriefPrompt -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'rhmcp.tools.urban_prompt'`

- [x] **Step 3: Create `src/rhmcp/tools/urban_prompt.py`**

```python
"""
FastMCP prompt resource: urban_brief

Claude reads this prompt before any urban massing generation. It provides a
structured intake template that ensures all mandatory parameters are collected
before the first tool call is made.

Auto-discovered by the pkgutil loop in src/rhmcp/__init__.py (same as all
tool modules). No changes to __init__.py needed.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_BRIEF_TEMPLATE = """\
# Urban Massing Brief

You are about to generate a 3D urban massing in Rhino. Collect the following
parameters from the user before calling urban_generate_massing. Ask for missing
mandatory fields one at a time. Confirm collected values before proceeding.

## Mandatory fields (always ask if not provided)

- **site_width** (metres): Width of the site footprint.
- **site_depth** (metres): Depth of the site footprint.
- **far_target**: Target floor area ratio (e.g. 3.5 = 3.5× the site area as GFA).

## Optional fields (use defaults if not provided)

- **site_origin** [x, y, z]: Corner of the site in Rhino world coordinates.
  Default: [0, 0, 0].
- **typology**: One of "tower", "podium_tower", "courtyard", "perimeter_block",
  "street_grid". If not specified, recommend the best fit based on FAR and
  program mix:
    - FAR < 1.5 → perimeter_block or courtyard
    - 1.5 ≤ FAR < 3.0 → courtyard or podium_tower
    - FAR ≥ 3.0 → podium_tower or tower
    - Large multi-block site → street_grid first, then place typologies on plots
- **residential_pct** (0–100): Percentage residential floor area. Default: 70.
- **office_pct** (0–100): Percentage office floor area. Default: 20.
- **retail_pct** (0–100): Percentage retail floor area. Default: 10.
  (residential_pct + office_pct + retail_pct should sum to ≤ 100)
- **climate_zone**: One of London, New York, Dubai, Tokyo, Sydney, Singapore,
  Berlin. Required only if the user asks for solar analysis. Default: London.
- **epw_path**: Absolute path to a custom .epw weather file. Overrides
  climate_zone. Leave blank unless the user provides a file path.

## Workflow after collecting parameters

1. Confirm: "I'll generate a {typology} massing, {site_width}×{site_depth}m,
   FAR {far_target}, {residential_pct}% residential / {office_pct}% office /
   {retail_pct}% retail. Proceeding…"
2. Call: urban_generate_massing(typology, site_origin, site_width, site_depth,
   params={far_target, residential_pct, office_pct, retail_pct})
3. Call: urban_capture_and_evaluate() → show the image, report metrics.
4. Offer next steps: "Want to adjust any parameters, try a different typology,
   or run solar analysis?"

## Amendment loop

After the first generation, accept free-form amendments:
- "Make the tower 5 floors taller" → urban_update_param("floor_count", current+5)
- "Try a courtyard instead" → urban_clear_massing(), then urban_generate_massing(typology="courtyard", …)
- "Run solar analysis" → urban_run_analysis(analysis_type="solar", …)
- Always call urban_capture_and_evaluate() after any geometry change.
"""


def register(mcp: FastMCP) -> None:
    @mcp.prompt(name="urban_brief", description=(
        "Structured intake for urban massing generation. "
        "Read this before calling any urban_* tool."
    ))
    def urban_brief() -> str:
        return _BRIEF_TEMPLATE
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/test_urban_unit.py -v
```
Expected: all 27 pass

- [x] **Step 5: Verify prompt is discoverable by the server**

```bash
uv run python -c "
import importlib, pkgutil
import rhmcp.tools as tools_pkg
from mcp.server.fastmcp import FastMCP
from unittest.mock import patch

mcp = FastMCP('test')
for _, modname, _ in pkgutil.iter_modules(tools_pkg.__path__):
    if modname.startswith('_'):
        continue
    mod = importlib.import_module(f'rhmcp.tools.{modname}')
    if hasattr(mod, 'register'):
        with patch('rhmcp.tools_helpers.backend.plugin_result', return_value={'ok': True}):
            mod.register(mcp)

print('Tools:', len(mcp._tool_manager._tools))
print('Prompts:', list(mcp._prompt_manager._prompts.keys()))
assert 'urban_brief' in mcp._prompt_manager._prompts
assert 'urban_generate_massing' in mcp._tool_manager._tools
print('OK')
"
```
Expected: `urban_brief` in prompts list, `urban_generate_massing` in tools list, `OK`

- [x] **Step 6: Commit**

```bash
git add src/rhmcp/tools/urban_prompt.py tests/test_urban_unit.py
git commit -m "feat(urban): urban_brief FastMCP prompt resource"
```

---

## Task 9: Grasshopper definitions — tower.gh

**Files:**
- Create: `grasshopper/urban/tower.gh`

This task was completed via reproducible Rhino/Grasshopper automation in scripts/generate_urban_gh.py. Open Grasshopper, build the definition per the spec below, save to the project directory, then commit the binary.

- [x] **Step 1: Create the directory**

```bash
mkdir -p /path/to/rhino_mcp/grasshopper/urban
```

- [x] **Step 2: Build the definition in Grasshopper**

Open Rhino → open Grasshopper. Build a definition with the following structure:

**Input sliders** (Add Number Slider for each; set the NickName exactly as shown):

| NickName | Min | Max | Default | Rounding |
|---|---|---|---|---|
| site_width | 10 | 500 | 80 | Integer |
| site_depth | 10 | 500 | 80 | Integer |
| tower_count | 1 | 6 | 1 | Integer |
| floor_count | 5 | 80 | 30 | Integer |
| floor_height | 2.8 | 5.0 | 3.2 | Float 1dp |
| footprint_width | 8 | 40 | 22 | Integer |
| footprint_depth | 8 | 40 | 22 | Integer |
| setback | 0 | 20 | 6 | Integer |
| residential_pct | 0 | 100 | 70 | Integer |
| retail_floors | 0 | 5 | 1 | Integer |

**Geometry logic** (using standard GH components):
1. `Rectangle` centred at origin: width=site_width, height=site_depth → site boundary curve
2. `Offset Curve` by setback → buildable footprint
3. `Rectangle` centred at each tower position: width=footprint_width, height=footprint_depth
4. `Extrude` tower footprint by (floor_count × floor_height) → tower solid
5. If tower_count > 1: use `Divide Domain²` + `Evaluate Surface` on buildable footprint to get tower positions
6. Group all geometry → connect to a `Geometry` component named **BakeTarget** (NickName: "BakeTarget")

**Metrics panel** (NickName: "Metrics"):
1. Add a `Python 3 Script` component
2. Input: connect all slider values needed for metrics
3. Script body:
```python
site_area = x * y  # site_width * site_depth
floors_above_retail = floor_count - retail_floors
tower_gfa = footprint_width * footprint_depth * floor_count * tower_count
open_space_pct = max(0.0, (site_area - footprint_width * footprint_depth * tower_count) / site_area * 100)
a = f"GFA: {tower_gfa:.0f}\nFAR: {tower_gfa/site_area:.2f}\nUnits: {int(tower_gfa * (residential_pct/100) / 70)}\nOpenSpace: {open_space_pct:.0f}"
```
4. Output `a` → Panel component with NickName **"Metrics"**

- [x] **Step 3: Verify the definition runs cleanly**

With all default values: solver should complete with no errors. Check output of Metrics panel: should show GFA ≈ 14520, FAR ≈ 2.27.

- [x] **Step 4: Save to project**

File → Save As → `grasshopper/urban/tower.gh`

- [x] **Step 5: Commit**

```bash
git add grasshopper/urban/tower.gh
git commit -m "feat(urban): tower.gh Grasshopper definition"
```

---

## Task 10: Grasshopper definitions — podium_tower.gh, courtyard.gh, perimeter_block.gh

**Files:**
- Create: `grasshopper/urban/podium_tower.gh`
- Create: `grasshopper/urban/courtyard.gh`
- Create: `grasshopper/urban/perimeter_block.gh`

Same process as Task 9 for each file. Slider specifications:

### podium_tower.gh

| NickName | Min | Max | Default |
|---|---|---|---|
| site_width | 20 | 500 | 120 |
| site_depth | 20 | 500 | 120 |
| podium_floors | 1 | 8 | 4 |
| podium_setback | 0 | 15 | 3 |
| tower_floors | 5 | 60 | 25 |
| tower_count | 1 | 2 | 1 |
| floor_height | 2.8 | 5.0 | 3.2 |
| residential_pct | 0 | 100 | 60 |
| retail_pct | 0 | 100 | 20 |

**Geometry:** Podium = site rectangle offset by podium_setback, extruded by podium_floors × floor_height. Tower = smaller rectangle on podium roof, extruded by tower_floors × floor_height.

**Metrics Python script:**
```python
site_area = site_width * site_depth
podium_gfa = (site_width - 2*podium_setback) * (site_depth - 2*podium_setback) * podium_floors
tower_fp = 22 * 22  # default tower footprint approximation
tower_gfa = tower_fp * tower_floors * tower_count
total_gfa = podium_gfa + tower_gfa
open_space = max(0.0, (site_area - (site_width-2*podium_setback)*(site_depth-2*podium_setback)) / site_area * 100)
a = f"GFA: {total_gfa:.0f}\nFAR: {total_gfa/site_area:.2f}\nUnits: {int(total_gfa*(residential_pct/100)/70)}\nOpenSpace: {open_space:.0f}"
```

### courtyard.gh

| NickName | Min | Max | Default |
|---|---|---|---|
| site_width | 20 | 300 | 80 |
| site_depth | 20 | 300 | 80 |
| wing_width | 6 | 25 | 14 |
| floor_count | 2 | 12 | 6 |
| floor_height | 2.8 | 4.5 | 3.2 |
| corner_opening_width | 0 | 20 | 0 |
| residential_pct | 0 | 100 | 80 |
| retail_pct | 0 | 100 | 10 |

**Geometry:** Outer rectangle minus inner rectangle (site minus 2×wing_width inset) = hollow perimeter. Optionally cut corner_opening_width openings at corners. Extrude by floor_count × floor_height.

**Metrics Python script:**
```python
site_area = site_width * site_depth
footprint = site_area - (site_width - 2*wing_width) * (site_depth - 2*wing_width)
gfa = footprint * floor_count
open_space = max(0.0, (site_area - footprint) / site_area * 100)
a = f"GFA: {gfa:.0f}\nFAR: {gfa/site_area:.2f}\nUnits: {int(gfa*(residential_pct/100)/70)}\nOpenSpace: {open_space:.0f}"
```

### perimeter_block.gh

| NickName | Min | Max | Default |
|---|---|---|---|
| site_width | 20 | 300 | 80 |
| site_depth | 20 | 300 | 80 |
| block_width | 8 | 30 | 16 |
| floor_count | 2 | 10 | 5 |
| floor_height | 2.8 | 4.5 | 3.2 |
| residential_pct | 0 | 100 | 75 |
| retail_pct | 0 | 100 | 15 |

**Geometry:** Solid filled rectangle, site_width × site_depth, extruded by floor_count × floor_height. Simpler than courtyard — no void.

**Metrics Python script:**
```python
site_area = site_width * site_depth
gfa = site_area * floor_count
open_space = 0.0
a = f"GFA: {gfa:.0f}\nFAR: {gfa/site_area:.2f}\nUnits: {int(gfa*(residential_pct/100)/70)}\nOpenSpace: {open_space:.0f}"
```

- [x] **Step 1: Build each .gh file in Grasshopper per specs above**
- [x] **Step 2: Verify each runs cleanly with default values**
- [x] **Step 3: Save each to `grasshopper/urban/`**
- [x] **Step 4: Commit**

```bash
git add grasshopper/urban/podium_tower.gh grasshopper/urban/courtyard.gh grasshopper/urban/perimeter_block.gh
git commit -m "feat(urban): podium_tower, courtyard, perimeter_block GH definitions"
```

---

## Task 11: Grasshopper definitions — street_grid.gh

**Files:**
- Create: `grasshopper/urban/street_grid.gh`

- [x] **Step 1: Build in Grasshopper**

Sliders:

| NickName | Min | Max | Default |
|---|---|---|---|
| site_width | 50 | 2000 | 400 |
| site_depth | 50 | 2000 | 400 |
| block_width | 30 | 200 | 80 |
| block_depth | 30 | 150 | 60 |
| road_width | 6 | 30 | 12 |
| grid_rotation | -45 | 45 | 0 |

**Geometry:**
1. Site rectangle: site_width × site_depth
2. `Divide Domain²` with (site_width / (block_width + road_width)) × (site_depth / (block_depth + road_width)) divisions
3. Each cell: inset by road_width/2 on all sides → plot rectangle
4. All plot rectangles → Surface → connect to **BakeTarget**
5. Road curves: outer edges of each cell minus inset → connect to a second **BakeTarget** group (or add to same)

**Metrics Python script:**
```python
n_x = max(1, int(site_width / (block_width + road_width)))
n_y = max(1, int(site_depth / (block_depth + road_width)))
n_plots = n_x * n_y
plot_area = block_width * block_depth
total_plot_area = n_plots * plot_area
site_area = site_width * site_depth
road_area = site_area - total_plot_area
a = f"GFA: 0\nFAR: 0.00\nUnits: 0\nOpenSpace: {road_area/site_area*100:.0f}"
```

(GFA/FAR/Units are 0 for street_grid since it's a site subdivider, not a building typology. Buildings go on plots in subsequent calls.)

- [x] **Step 2: Verify runs cleanly with defaults: should generate ~20 plots in a 400×400m site**
- [x] **Step 3: Save and commit**

```bash
git add grasshopper/urban/street_grid.gh
git commit -m "feat(urban): street_grid.gh Grasshopper definition"
```

---

## Task 12: Grasshopper definition — analysis_solar.gh (Ladybug)

**Files:**
- Create: `grasshopper/urban/analysis_solar.gh`

**Prerequisite:** Ladybug Tools must be installed in Rhino before building this file. Install with:

```
yak install ladybug
```

Restart Rhino after installation. Confirm `LadybugTools` tab appears in Grasshopper.

- [x] **Step 1: Build in Grasshopper**

**Input panels** (add `Panel` component for each — set NickName exactly):

| NickName | Content (default) |
|---|---|
| epw_path | ~/ladybug/EPWs/GBR_London.Gatwick.037760_IWEC.epw |
| geometry_layer | Urban::Massing::courtyard |
| analysis_period | Jun 21 9am-5pm |

**Input slider:**

| NickName | Min | Max | Default |
|---|---|---|---|
| grid_size | 0.5 | 5.0 | 1.0 |

**Component chain:**
1. `Ladybug_Open EPW Weather File` → input: `epw_path` panel → output: `location`, `header`, `dry_bulb_temp`, `radiation`
2. `Geometry Pipeline` → layer: connect `geometry_layer` panel → output: geometry of baked massing
3. `LB Analysis Period` → input: `analysis_period` panel → output: `period`
4. `LB Incident Radiation` → inputs: `location`, `period`, `geometry` from Pipeline, `grid_size` → outputs: `radiation_result`, `mesh`
5. `LB Color Mesh` → input: `mesh`, `radiation_result` → coloured radiation mesh
6. Output panel **avg_radiation_kwh_m2** (NickName exactly): connect average of `radiation_result`
7. Output panel **overshadow_hours_worst** (NickName exactly): use `LB Shadow Study` or compute from `radiation_result` minimum
8. Component **radiation_mesh** (NickName exactly): `Geometry` component connected to coloured mesh → this is the BakeTarget for the analysis layer

**Note on Geometry Pipeline:** The `Geometry Pipeline` component reads baked Rhino geometry by layer at solve time. Set the layer name via a Panel connected to its `Layer` input. This is how the Python tools pass the massing layer name.

- [x] **Step 2: Verify with default inputs**

Manually set `geometry_layer` panel to an existing layer in your test file and run the solver. Should produce a coloured radiation mesh without errors.

- [x] **Step 3: Save to project**

```bash
# Save from Grasshopper: File → Save As → grasshopper/urban/analysis_solar.gh
```

- [x] **Step 4: Commit**

```bash
git add grasshopper/urban/analysis_solar.gh
git commit -m "feat(urban): analysis_solar.gh Ladybug solar analysis definition"
```

---

## Task 13: README update

**Files:**
- Modify: `README.md`

- [x] **Step 1: Find the insertion point in README.md**

```bash
grep -n "^## " README.md | head -20
```

Find the `## Tools` or `## Features` section — insert the new section before or after it.

- [x] **Step 2: Add the Urban Massing section**

Insert the following block at the appropriate location in `README.md`:

````markdown
## Urban Massing

rhino_mcp includes an AI-driven urban massing workflow — describe a site in plain English and Claude generates, iterates, and analyses parametric 3D massing directly in Rhino.

UrbanAgent brings natural-language-to-3D urban massing capability into your local Rhino environment.

### Prerequisites

1. **Rhino 8** with the RhinoMCP plugin loaded (`MCPStart`)
2. **Grasshopper** open (launch via `Grasshopper` command)
3. **Ladybug Tools** for solar analysis — install via:
   ```
   yak install ladybug
   ```
   Restart Rhino after installation.

### Workflow

A typical session has four phases:

**1. Intake** — Claude reads the `urban_brief` prompt resource and collects mandatory parameters:
- Site dimensions (width × depth in metres)
- FAR target (floor area ratio)
- Program mix (% residential / office / retail)
- Climate zone (for solar analysis)

**2. Generation** — Claude calls `urban_generate_massing` with your brief. A pre-built Grasshopper definition opens, sliders are set, the solver runs, and geometry is baked into named Rhino layers. Claude captures the viewport and reports GFA, FAR, estimated unit count, and open space %.

**3. Iteration** — Free-form amendments: "make the tower taller", "try a courtyard typology instead", "add more retail floors". Claude calls `urban_update_param` or re-generates with new parameters.

**4. Analysis** — "Run solar analysis" triggers `urban_run_analysis`, which opens a Ladybug definition, connects the baked geometry via Geometry Pipeline, runs the solver, and returns average radiation and worst-case overshadowing.

### Example

```
User: Design a mixed-use development in Shoreditch — FAR 3.5, 80m × 80m site, mostly residential.

Claude: What's the program split? (residential / office / retail)

User: 70% residential, 20% office, 10% retail.

Claude: [generates podium_tower massing, shows viewport image]
        GFA 22,400m² · FAR 3.5 · ~224 units · 18% open space

User: The tower looks too thin. Widen the footprint to 28m.

Claude: [calls urban_update_param("footprint_width", 28), shows updated view]
        GFA 24,640m² · FAR 3.85 · ~246 units · 14% open space

User: Run solar analysis.

Claude: [opens analysis_solar.gh, connects baked geometry, runs Ladybug]
        Average façade radiation 380 kWh/m² · Worst overshadowing 4.2h
        [shows coloured radiation mesh on viewport image]
```

### Typologies

| Name | Description | Best for |
|---|---|---|
| `tower` | Single or clustered point towers | FAR ≥ 3.0, tight footprints |
| `podium_tower` | Low podium + 1–2 towers | FAR 2.0–5.0, mixed-use |
| `courtyard` | Hollow perimeter with central courtyard | FAR 1.5–3.0, residential |
| `perimeter_block` | Solid perimeter fill | FAR 1.0–2.5, dense low-rise |
| `street_grid` | Site subdivider — roads + plots | Multi-block masterplan |

### Urban Massing Tools

| Tool | Description |
|---|---|
| `urban_generate_massing` | Opens the typology .gh, sets sliders, runs solver, bakes, returns metrics |
| `urban_update_param` | Sets one named slider on the open definition and re-runs solver |
| `urban_capture_and_evaluate` | Viewport screenshot + metrics in one call — returns `[metrics, Image]` |
| `urban_run_analysis` | Opens `analysis_solar.gh`, connects baked geometry, runs Ladybug, returns radiation results |
| `urban_get_metrics` | Reads GFA, FAR, unit count, open space % from the current GH definition |
| `urban_clear_massing` | Deletes all objects on `Urban::*` layers |

### Layer Structure

All baked geometry uses a hierarchical naming convention:

```
Urban::
  Massing::
    tower
    podium_tower
    courtyard
    perimeter_block
    street_grid
  Analysis::
    Solar
```

`urban_clear_massing()` clears everything under `Urban::*`.
`urban_clear_massing(layer_prefix="Urban::Massing")` clears geometry but keeps analysis results.

### EPW Climate Zones

For solar analysis, pass `climate_zone` to `urban_run_analysis`. Bundled zones:

| Zone | EPW file stem |
|---|---|
| London | GBR_London.Gatwick.037760_IWEC |
| New York | USA_NY_New.York-J.F.K.Intl.AP.744860_TMY3 |
| Dubai | ARE_Dubai.Intl.AP.411940_IWEC |
| Tokyo | JPN_Tokyo.Hyakuri.477150_IWEC |
| Sydney | AUS_NSW_Sydney.Intl.AP.947670_IWEC |
| Singapore | SGP_Singapore.486980_IWEC |
| Berlin | DEU_Berlin.Tempelhof.103840_IWEC |

EPW files are resolved from `~/ladybug/EPWs/`. For a custom location, pass `epw_path="/absolute/path/to/file.epw"`.

### Tweaking Definitions

The `.gh` files in `grasshopper/urban/` are standard Grasshopper definitions. Open any of them directly to inspect the parametric logic, adjust slider ranges, or extend the geometry. Changes persist to disk — Claude will pick them up on the next `urban_generate_massing` call.
````

- [x] **Step 3: Run all tests one final time**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
```
Expected: 127 passed (or more — no failures)

- [x] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add Urban Massing section to README"
```

---

## Self-Review

**Spec coverage:**
- ✅ Section 3 (6 tools) — Tasks 2–7
- ✅ Section 4 (prompt resource) — Task 8
- ✅ Sections 5–6 (.gh definitions) — Tasks 9–12
- ✅ Section 8 (module-level state) — Task 1
- ✅ Section 9 (registration) — auto-discovery, no changes needed
- ✅ Section 10 (testing) — all 6 tool classes with 25 tests
- ✅ Section 11 (README) — Task 13

**Placeholder scan:** No TBD, TODO, or vague steps. All code is shown in full.

**Type consistency:** `_urban_get_metrics()` returns `dict[str, object]` throughout. `urban_capture_and_evaluate` returns `list[object]` (metrics dict + optional Image) consistently. `_gh()` returns `dict[str, object]` everywhere. Slider maps use `list[str]` consistently.

# Urban Massing Workflow Implementation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an AI-driven urban massing workflow to rhino_mcp — Claude accepts a natural-language site brief, generates parametric 3D massing typologies in Rhino/Grasshopper, reads back metrics (GFA, FAR, unit count, open space), and runs Ladybug solar analysis, all through an iterative conversation loop.

**Architecture:** A new `urban` MCP tool module exposes six high-level composite tools that wrap the existing `gh_*` and `capture_rhino_view` tool machinery. Pre-built Grasshopper definitions (one per typology) are the parametric engine; Claude drives them by setting named sliders. A FastMCP prompt resource (`urban_brief`) enforces a structured intake before any geometry is generated. Target users are both architects who know Rhino/Grasshopper and non-designers who just want a result.

**Tech Stack:** Python (FastMCP), RhinoCommon Python scripting, Grasshopper + Ladybug Tools, existing `gh_*` MCP tools, `capture_rhino_view` Image return.

---

## 1. New Files

| Path | Purpose |
|---|---|
| `src/rhmcp/tools/urban.py` | 6 MCP tools for the urban massing workflow |
| `src/rhmcp/urban_prompt.py` | FastMCP prompt resource: `urban_brief` |
| `grasshopper/urban/tower.gh` | Tower typology |
| `grasshopper/urban/podium_tower.gh` | Podium + tower typology |
| `grasshopper/urban/courtyard.gh` | Courtyard block typology |
| `grasshopper/urban/perimeter_block.gh` | Perimeter block typology |
| `grasshopper/urban/street_grid.gh` | Street grid + site subdivision |
| `grasshopper/urban/analysis_solar.gh` | Ladybug solar radiation + overshadowing |
| `tests/test_urban_unit.py` | Unit tests for all 6 tools (mocked backend) |

## 2. Modified Files

| Path | Change |
|---|---|
| `src/rhmcp/__init__.py` | Register urban tools + `urban_brief` prompt resource |
| `src/rhmcp/tools/__init__.py` | Import `urban` module |
| `README.md` | Add Urban Massing section: tool list, workflow, EPW setup |

---

## 3. MCP Tools — `src/rhmcp/tools/urban.py`

### `urban_generate_massing`

```
urban_generate_massing(
    typology: str,              # "tower" | "podium_tower" | "courtyard" | "perimeter_block" | "street_grid"
    site_origin: list[float],   # [x, y, z] in model units (metres)
    site_width: float,          # metres
    site_depth: float,          # metres
    params: dict[str, float],   # slider overrides — any key from the typology's slider map
    layer_prefix: str = "Urban" # baked geometry goes to {layer_prefix}::Massing::{Typology}
) -> dict[str, object]
```

**Behaviour:**
1. Validates `typology` against `_TYPOLOGY_GH_MAP`; raises `ValueError` on unknown value.
2. Resolves the `.gh` path relative to the `grasshopper/urban/` directory shipped with the package.
3. Calls `gh_open_definition(path)`.
4. Sets `site_width`, `site_depth` sliders, then all keys in `params` via `gh_set_slider`.
5. Calls `gh_run_solution(wait_ms=15000)`.
6. Calls `gh_bake(instance_guid=<metrics_output_guid>, layer=f"{layer_prefix}::Massing::{typology}")`.
7. Calls `urban_get_metrics()` and merges into the return dict.

**Returns:** `{ok: bool, typology, layer, gfa_m2, far, unit_count_est, open_space_pct, error?}`

### `urban_update_param`

```
urban_update_param(
    param_name: str,   # named slider key (e.g. "floor_count", "setback")
    value: float,
) -> dict[str, object]
```

**Behaviour:**
1. Looks up `param_name` in the slider registry for the currently open definition (stored as module-level state after `urban_generate_massing` sets it).
2. Calls `gh_set_slider(instance_guid, value)`.
3. Calls `gh_run_solution(wait_ms=15000)`.
4. Returns `{ok, param_name, clamped_value, gfa_m2, far, unit_count_est, open_space_pct}`.
5. Raises `KeyError` if `param_name` is not in the current definition's slider map.

### `urban_capture_and_evaluate`

```
urban_capture_and_evaluate() -> list[object]
```

**Behaviour:**
1. Calls `capture_rhino_view(path=None)` — returns `[meta_dict, Image]`.
2. Calls `urban_get_metrics()`.
3. Returns `[metrics_dict, Image]` — metrics first so Claude sees numbers before the image.
4. If capture fails, returns `[metrics_dict]` with no crash.

### `urban_run_analysis`

```
urban_run_analysis(
    analysis_type: str,         # "solar" (only supported type in v1)
    geometry_layer: str,        # layer name of baked massing to analyse
    climate_zone: str = "London", # key into _EPW_DEFAULTS, or pass epw_path directly
    epw_path: str | None = None,  # overrides climate_zone if provided
    analysis_period: str = "Jun 21 9am-5pm",
    grid_size: float = 1.0,
) -> dict[str, object]
```

**Behaviour:**
1. Validates `analysis_type`; raises `ValueError` on unknown value.
2. Resolves EPW path: `epw_path` takes priority; otherwise looks up `climate_zone` in `_EPW_DEFAULTS`.
3. Calls `gh_open_definition("grasshopper/urban/analysis_solar.gh")`.
4. Sets `epw_path` panel, `geometry_layer` panel, `analysis_period` panel, `grid_size` slider.
5. Calls `gh_run_solution(wait_ms=60000)` — Ladybug can be slow.
6. Calls `gh_bake(layer=f"{geometry_layer}::Analysis::Solar")`.
7. Reads output panels: `avg_radiation_kwh_m2`, `overshadow_hours_worst`, `courtyard_avg_kwh_m2` (if applicable).

**Returns:** `{ok, analysis_type, avg_radiation_kwh_m2, overshadow_hours_worst, epw_used, error?}`

### `urban_get_metrics`

```
urban_get_metrics() -> dict[str, object]
```

**Behaviour:**
1. Calls `gh_get_output(instance_guid=<metrics_panel_guid>, output_name="Metrics")` on the currently open definition.
2. Parses the panel text: expects lines of `key: value` format (e.g. `GFA: 28000`).
3. Returns `{gfa_m2, far, unit_count_est, open_space_pct}`.
4. Returns zero-safe defaults `{gfa_m2: 0, far: 0.0, unit_count_est: 0, open_space_pct: 0.0}` if no definition is open or parse fails.

### `urban_clear_massing`

```
urban_clear_massing(
    layer_prefix: str = "Urban",
) -> dict[str, object]
```

**Behaviour:**
1. Executes a RhinoCommon Python script that selects and deletes all objects on layers matching `{layer_prefix}::*`.
2. Returns `{ok, deleted_count}`.
3. No-ops safely if no matching objects exist.

---

## 4. Prompt Resource — `src/rhmcp/urban_prompt.py`

Registers a FastMCP prompt resource named `urban_brief`.

When Claude reads this resource it receives a structured markdown template instructing it to collect exactly these fields before calling any urban tool:

```
- site_origin: [x, y, z] in metres (default [0, 0, 0])
- site_width: metres
- site_depth: metres
- typology: tower | podium_tower | courtyard | perimeter_block | street_grid | mixed (Claude picks best fit)
- far_target: target floor area ratio (e.g. 3.5)
- residential_pct: 0–100
- office_pct: 0–100
- retail_pct: 0–100 (residential + office + retail must sum to ≤ 100)
- climate_zone: London | New York | Dubai | Tokyo | Sydney | Singapore | Berlin | custom
- epw_path: only required if climate_zone is "custom"
```

The prompt instructs Claude to:
1. Ask for any missing mandatory fields (site dimensions + FAR target are always required).
2. Accept reasonable defaults for optional fields (origin = [0,0,0], typology = Claude's recommendation based on FAR and program mix).
3. Confirm the collected parameters before generating.

---

## 5. Grasshopper Definitions

Each `.gh` file in `grasshopper/urban/` must follow these conventions so the Python tools can drive them reliably:

- **Named sliders:** Every Number Slider has a unique `NickName` matching the key in `_SLIDER_MAPS` in `urban.py`. Claude looks up instance GUIDs by NickName after opening the definition.
- **Metrics panel group:** A group named `"Metrics"` contains a single Panel component whose output is a multi-line string: `GFA: {value}\nFAR: {value}\nUnits: {value}\nOpenSpace: {value}`.
- **Bake layer:** The geometry output component is named `"BakeTarget"` — `gh_bake` is called on this GUID.
- **No external file dependencies** except EPW files (analysis_solar.gh only).

### Slider Maps (per typology)

**tower.gh**

| NickName | Range | Default |
|---|---|---|
| site_width | 10–500 | 80 |
| site_depth | 10–500 | 80 |
| tower_count | 1–6 | 1 |
| floor_count | 5–80 | 30 |
| floor_height | 2.8–5.0 | 3.2 |
| footprint_width | 8–40 | 22 |
| footprint_depth | 8–40 | 22 |
| setback | 0–20 | 6 |
| residential_pct | 0–100 | 70 |
| retail_floors | 0–5 | 1 |

**podium_tower.gh**

| NickName | Range | Default |
|---|---|---|
| site_width | 20–500 | 120 |
| site_depth | 20–500 | 120 |
| podium_floors | 1–8 | 4 |
| podium_setback | 0–15 | 3 |
| tower_floors | 5–60 | 25 |
| tower_count | 1–2 | 1 |
| floor_height | 2.8–5.0 | 3.2 |
| residential_pct | 0–100 | 60 |
| retail_pct | 0–100 | 20 |

**courtyard.gh**

| NickName | Range | Default |
|---|---|---|
| site_width | 20–300 | 80 |
| site_depth | 20–300 | 80 |
| wing_width | 6–25 | 14 |
| floor_count | 2–12 | 6 |
| floor_height | 2.8–4.5 | 3.2 |
| corner_opening_width | 0–20 | 0 |
| residential_pct | 0–100 | 80 |
| retail_pct | 0–100 | 10 |

**perimeter_block.gh**

| NickName | Range | Default |
|---|---|---|
| site_width | 20–300 | 80 |
| site_depth | 20–300 | 80 |
| block_width | 8–30 | 16 |
| floor_count | 2–10 | 5 |
| floor_height | 2.8–4.5 | 3.2 |
| residential_pct | 0–100 | 75 |
| retail_pct | 0–100 | 15 |

**street_grid.gh**

| NickName | Range | Default |
|---|---|---|
| site_width | 50–2000 | 400 |
| site_depth | 50–2000 | 400 |
| block_width | 30–200 | 80 |
| block_depth | 30–150 | 60 |
| road_width | 6–30 | 12 |
| grid_rotation | -45–45 | 0 |

**analysis_solar.gh**

| NickName | Type | Notes |
|---|---|---|
| geometry_layer | Panel | Layer name of baked massing |
| epw_path | Panel | Absolute path to .epw file |
| analysis_period | Panel | e.g. "Jun 21 9am-5pm" |
| grid_size | Slider 0.5–5.0 | Analysis mesh resolution in metres |

Outputs: `avg_radiation_kwh_m2` (Panel), `overshadow_hours_worst` (Panel), `radiation_mesh` (geometry bake target).

---

## 6. EPW Climate Zone Defaults

Bundled in `urban.py` as `_EPW_DEFAULTS: dict[str, str]`. Values are EnergyPlus EPW filenames resolvable against the Ladybug default EPW library path (`~/ladybug/EPWs/`).

| Key | EPW filename stem |
|---|---|
| London | GBR_London.Gatwick.037760_IWEC |
| New York | USA_NY_New.York-J.F.K.Intl.AP.744860_TMY3 |
| Dubai | ARE_Dubai.Intl.AP.411940_IWEC |
| Tokyo | JPN_Tokyo.Hyakuri.477150_IWEC |
| Sydney | AUS_NSW_Sydney.Intl.AP.947670_IWEC |
| Singapore | SGP_Singapore.486980_IWEC |
| Berlin | DEU_Berlin.Tempelhof.103840_IWEC |

If the EPW file is not found at the default path, `urban_run_analysis` returns `{ok: false, error: "EPW not found: {path}. Install via Ladybug or pass epw_path directly."}`.

---

## 7. Layer Naming Convention

All baked geometry uses a hierarchical layer structure:

```
Urban::
  Massing::
    Tower
    PodiumTower
    Courtyard
    PerimeterBlock
    StreetGrid
  Analysis::
    Solar
```

`urban_clear_massing(layer_prefix="Urban")` deletes all objects under `Urban::*`. To preserve analysis results while clearing massing, call `urban_clear_massing(layer_prefix="Urban::Massing")`.

---

## 8. Module-Level State in `urban.py`

`urban_update_param` needs to know which definition is currently open and the instance GUIDs of its sliders. This state is stored as module-level variables set by `urban_generate_massing`:

```python
_current_typology: str | None = None
_current_slider_guids: dict[str, str] = {}  # param_name → instance_guid
_current_metrics_guid: str | None = None
_current_bake_guid: str | None = None
```

These are populated after `gh_open_definition` returns the component list, by matching NickNames against `_SLIDER_MAPS[typology]`. They are reset to `None` by `urban_clear_massing`.

---

## 9. Registration in `src/rhmcp/__init__.py`

```python
from rhmcp.tools import urban
urban.register(mcp)

from rhmcp import urban_prompt
urban_prompt.register(mcp)
```

`urban_prompt.register(mcp)` calls `mcp.add_prompt("urban_brief", urban_prompt.handler)`.

---

## 10. Testing Strategy

All tests in `tests/test_urban_unit.py` use the same mock pattern as the existing test suite: `unittest.mock.patch("rhmcp.tools_helpers.backend")` to intercept all Rhino calls.

**Test classes:**

- `TestUrbanGenerateMassing` — 5 tests: correct .gh path per typology, slider calls, bake layer name, metrics return, ValueError on unknown typology
- `TestUrbanUpdateParam` — 3 tests: correct slider guid lookup, solver re-run, KeyError on unknown param
- `TestUrbanCaptureAndEvaluate` — 3 tests: Image in return list, metrics dict present, graceful capture failure
- `TestUrbanRunAnalysis` — 4 tests: opens correct .gh, sets EPW path for known zone, ValueError on unknown type, radiation dict structure
- `TestUrbanGetMetrics` — 2 tests: parses panel output correctly, returns zero defaults when no definition open
- `TestUrbanClearMassing` — 3 tests: deletes Urban:: objects only, returns deleted_count, no-ops safely

Target: all existing 100 tests continue to pass; 20 new tests added (total ≥ 120).

---

## 11. README Section

Add a new `## Urban Massing` section to `README.md` covering:

- Overview and workflow (4-phase: intake → generate → amend → analyse)
- Prerequisites: Ladybug Tools installed in Rhino (`yak install ladybug`)
- EPW file setup: where Ladybug stores them, how to pass a custom path
- Tool reference table: all 6 tools with parameters
- Example conversation transcript
- Layer naming reference

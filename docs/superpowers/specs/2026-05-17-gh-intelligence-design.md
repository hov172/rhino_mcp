# GH Intelligence — v0.12.0 Design Spec

**Date:** 2026-05-17  
**Status:** Approved  
**Target version:** 0.12.0  

---

## Overview

Add three GH intelligence features to rhino_mcp that match and exceed McNeel's official RhinoMCP:

1. **Canvas analysis** — complexity metrics, cluster detection, actionable suggestions
2. **Canvas refactor (de-spaghettify)** — auto-layout GH1 and GH2 canvases to reduce wire crossings and add logical grouping
3. **GH1→GH2 migration** — structured migration of a GH1 definition to a GH2 canvas

rhino_mcp's approach: direct tool execution with validated structured data, not script generation. Smaller attack surface, deterministic results, fully auditable.

**New tool count:** 351 (up from 347)

---

## Architecture

### C# plugin — 3 new handlers

Added to `CommandDispatcher.cs` and implemented in a new `GHIntelligenceHandlers.cs`:

| Handler | Description |
|---|---|
| `gh_get_canvas_analysis` | Reads GH1 canvas via GH object model. Returns: component count, connection count, estimated wire crossing count, connected subgraphs (clusters), ungrouped components, isolated nodes, canvas bounds. |
| `gh_get_layout_plan` | Runs topological sort on component graph, returns suggested `{component_id: {x, y}}` per component using layer-based left-to-right layout to minimise crossings. Read-only, no side effects. |
| `gh1_export_migration_data` | Exports every GH1 component as structured JSON: type GUID, nickname, input/output param names and types, current persistent values, all connections. Sufficient to reconstruct in GH2. Read-only. |

All three handlers:
- Run on Rhino main UI thread via `RhinoApp.InvokeOnUiThread`
- Are read-only — no writes to the GH document
- Return `{"status": "error", "message": "..."}` if GH is not open

### Python tools — new module `src/rhmcp/tools/gh_intelligence.py`

| Tool | Description |
|---|---|
| `gh_analyze_canvas` | Calls `gh_get_canvas_analysis`, returns structured report + human-readable summary with suggestions. |
| `gh_refactor_canvas` | Orchestrates GH1 canvas reorganisation: analyze → layout plan → dry-run → apply moves + groups. |
| `gh2_refactor_canvas` | Same as above but reads via `gh2_get_canvas_graph` and writes via GH2 tools. |
| `gh_migrate_to_gh2` | Exports GH1 data → maps types via YAML → calls `gh2_start` + `gh2_apply_graph`. |

### Data file — `src/rhmcp/data/gh1_to_gh2_map.yml`

Versioned mapping of GH1 component type GUIDs to GH2 type names.

```yaml
last_verified_rhino_version: "9.0-wip"
mappings:
  - gh1_guid: "57da07bd-ecab-415d-9d86-be1145e9f0eb"  # Point
    gh2_name: "Point"
  # ... one entry per known component
```

- Loaded once at module import (not per call)
- File path hardcoded — never user-supplied
- Schema validated on load: malformed entries skipped with warning, never crash
- Missing file: falls back to empty map, all components go to `unmapped`

---

## Tool Specifications

### `gh_analyze_canvas(rhino_id?)`

**Parameters:** `rhino_id` (optional, UUID string)

**Returns:**
```json
{
  "ok": true,
  "component_count": 24,
  "connection_count": 31,
  "wire_crossing_estimate": 8,
  "cluster_count": 3,
  "ungrouped_component_count": 18,
  "isolated_component_count": 2,
  "complexity_score": 67,
  "canvas_bounds": {"x_min": -400, "x_max": 1200, "y_min": -200, "y_max": 600},
  "suggestions": [
    "18 components could be organised into 3 logical groups",
    "8 estimated wire crossings — refactor recommended",
    "2 isolated components have no connections"
  ]
}
```

`complexity_score` is 0–100, clamped. No side effects. Safe to call anytime.

---

### `gh_refactor_canvas(apply=False, group_clusters=True, rhino_id?)`

**Parameters:**
- `apply` (bool, default `False`) — preview plan without executing
- `group_clusters` (bool, default `True`) — add GH groups per detected cluster
- `rhino_id` (optional, UUID string)

**Flow:**
1. Call `gh_get_canvas_analysis` → get clusters and current metrics
2. Call `gh_get_layout_plan` → get `{component_id: {x, y}}` for all components
3. **Dry-run:** validate all positions are within bounds — abort if any invalid
4. If `apply=False`: return plan as preview (no canvas changes)
5. If `apply=True` and dry-run passes:
   - Call `gh_move_component` for each component
   - Call `gh_add_group` for each cluster (if `group_clusters=True`)
   - Return result

**Returns (apply=False):**
```json
{
  "ok": true,
  "preview": true,
  "moves": [{"component_id": "...", "from": {"x": 0, "y": 0}, "to": {"x": 120, "y": 0}}],
  "groups_to_add": 3,
  "estimated_crossings_after": 1
}
```

**Returns (apply=True):**
```json
{
  "ok": true,
  "moved": 24,
  "groups_added": 3,
  "crossings_before": 8,
  "crossings_after": 1
}
```

**Partial failure:** If `gh_move_component` fails mid-execution (after dry-run passes), returns `{ok: false, moved: N, failed: [...]}` with all failures listed. Dry-run prevents most failures.

---

### `gh2_refactor_canvas(apply=False, group_clusters=True, rhino_id?)`

Identical contract to `gh_refactor_canvas`. Differences in implementation only:
- Reads canvas via `gh2_get_canvas_graph` instead of `gh_get_canvas_analysis`
- Layout plan computed Python-side from GH2 graph data (no separate C# handler needed — GH2 graph already exposes position data)
- Writes via GH2 move/group tools
- Returns `error_code: GH2_NOT_AVAILABLE` on Rhino 8

---

### `gh_migrate_to_gh2(confirm=False, close_gh1=False, rhino_id?)`

**Parameters:**
- `confirm` (bool, default `False`) — must be `True` to execute
- `close_gh1` (bool, default `False`) — leave GH1 open for side-by-side comparison
- `rhino_id` (optional, UUID string)

**Flow:**
1. If `confirm=False`: return `error_code: CONFIRMATION_REQUIRED`
2. Call `gh1_export_migration_data` → full component+wire JSON
3. Map each component type GUID against `gh1_to_gh2_map.yml`
4. Call `gh2_start()` → ensure GH2 editor is open
5. Call `gh2_apply_graph(components, wires)` with mapped components only
6. If `close_gh1=True`: close GH1 definition
7. Return result

**Returns:**
```json
{
  "ok": true,
  "migrated": 20,
  "unmapped": [
    {"gh1_guid": "...", "nickname": "MyLegacyComponent", "reason": "No GH2 equivalent in mapping table"}
  ],
  "gh2_errors": [],
  "gh1_closed": false
}
```

**Requirements:**
- Requires Rhino 9 (GH2 not available on Rhino 8 — returns `GH2_NOT_AVAILABLE`)
- Does not auto-save either document
- `unmapped` list is always present (empty array if all components mapped)

---

## Data Flow Diagrams

### Refactor

```
gh_refactor_canvas(apply=True)
  │
  ├─→ C#: gh_get_canvas_analysis   → clusters, metrics
  ├─→ C#: gh_get_layout_plan       → {id: {x,y}} per component
  ├─→ Python: dry-run validation   → abort if any position invalid
  ├─→ gh_move_component × N        → reposition each component
  ├─→ gh_add_group × clusters      → group by cluster
  └─→ return {moved, groups_added, crossings_before, crossings_after}
```

### Migration

```
gh_migrate_to_gh2(confirm=True)
  │
  ├─→ C#: gh1_export_migration_data  → full component+wire JSON
  ├─→ Python: YAML type mapping       → {mapped: [...], unmapped: [...]}
  ├─→ gh2_start()                     → open GH2 editor
  ├─→ gh2_apply_graph(...)            → build GH2 canvas
  └─→ return {migrated, unmapped, gh2_errors}
```

---

## Error Handling

| Situation | Error code | Behaviour |
|---|---|---|
| GH not open | `GH_NOT_OPEN` | Consistent with all existing GH tools |
| GH2 not available (Rhino 8) | `GH2_NOT_AVAILABLE` | Clear message, graceful degradation |
| `confirm=False` on migration | `CONFIRMATION_REQUIRED` | Consistent with `gh_clear_canvas` pattern |
| Component has no GH2 equivalent | — | Added to `unmapped`, migration continues |
| Dry-run pre-check fails | `LAYOUT_VALIDATION_FAILED` | Abort before first move, list invalid positions |
| Partial move failure (post dry-run) | — | `{ok: false, moved: N, failed: [...]}` |
| YAML missing or corrupt | — | Falls back to empty map, all go to `unmapped` |
| Canvas position out of bounds | — | Clamped to ±100,000 canvas units, never rejected |

---

## Security

**Input validation:**
- `rhino_id` validated as UUID string if provided
- All component GUIDs from C# responses re-validated before use in subsequent tool calls
- Canvas coordinates from layout plan clamped to ±100,000 before `gh_move_component`
- Group name strings validated against `^[\w\s.\-]{1,64}$`

**YAML mapping file:**
- Path hardcoded — never user-supplied
- Loaded once at module import
- Schema validated on load: malformed entries skipped with warning

**Destructive operation gates:**
- `gh_migrate_to_gh2` requires `confirm=True`
- `gh_refactor_canvas(apply=True)` requires dry-run to pass
- Neither tool auto-saves

**C# handlers:**
- All three are read-only — no GH document writes
- Run on UI thread via `RhinoApp.InvokeOnUiThread`

**No script generation:**
- No user input ever becomes executable code
- Structurally smaller attack surface than McNeel's script-generation approach

---

## Testing

### Unit tests — `tests/test_gh_intelligence.py`

- `gh_analyze_canvas` response contains all required fields
- `complexity_score` stays in 0–100 range regardless of input
- `apply=False` makes zero canvas mutations (mock verifies no `gh_move_component` calls)
- `confirm=False` on migration returns `CONFIRMATION_REQUIRED` without calling `gh2_start`
- YAML mapping loads correctly and handles missing file gracefully (empty map fallback)
- Canvas position clamping — values beyond ±100,000 are clamped, not rejected
- `unmapped` populated when YAML has no entry for a component GUID
- Dry-run pre-check blocks execution when any position is invalid

### Smoke tests — additions to `test_smoke.py`

- `gh_intelligence` module imports without error
- All 4 new tools register with unique names
- Total tool count is 351

### Integration tests — `tests/test_gh_intelligence_integration.py`

Marked `@pytest.mark.integration`. Require live Rhino 8 with GH open.

Fixtures (checked into `tests/fixtures/`):
- `messy_canvas.gh` — known definition with ≥8 wire crossings and ≥3 identifiable clusters
- `simple_migration.gh` — GH1 definition using only components with confirmed GH2 equivalents, zero unmapped

Tests:
- Open `messy_canvas.gh` → `gh_analyze_canvas` returns `cluster_count >= 3` and `wire_crossing_estimate >= 8`
- `gh_refactor_canvas(apply=False)` returns plan without moving anything (verify component positions unchanged)
- `gh_refactor_canvas(apply=True)` → `crossings_after < crossings_before`
- Open `simple_migration.gh` → `gh_migrate_to_gh2(confirm=True)` → `unmapped == []`, GH2 canvas has correct component count
- `gh2_refactor_canvas(apply=True)` on a messy GH2 canvas → `crossings_after < crossings_before` *(Rhino 9 only)*

### What is not tested

- Visual layout quality — only crossing count reduction is asserted
- GH2 component API correctness (McNeel's responsibility) — mapping logic is tested, not runtime

---

## Competitive Positioning

| Capability | rhino_mcp v0.12.0 | mcneel/RhinoMCP |
|---|---|---|
| Canvas analysis | ✅ metrics + suggestions | ✗ |
| GH1 de-spaghettify | ✅ direct tool execution | ✅ script generation |
| GH2 de-spaghettify | ✅ | ✗ |
| GH1→GH2 migration | ✅ structured + auditable | ✅ AI-generated |
| Attack surface | Smaller — no code execution path | Larger — script generation |
| Partial failure handling | ✅ dry-run + partial result | Unknown |
| Preview before apply | ✅ apply=False default | Unknown |
| 347 other Rhino tools | ✅ | ✗ |

---

## Files Changed

| File | Change |
|---|---|
| `rhino_plugin/RhinoMCPPlugin/GHIntelligenceHandlers.cs` | New — 3 C# handlers |
| `rhino_plugin/RhinoMCPPlugin/CommandDispatcher.cs` | Wire new handlers |
| `rhino_plugin/RhinoMCPPlugin/RhinoMCPPlugin.csproj` | Add new file |
| `src/rhmcp/tools/gh_intelligence.py` | New — 4 Python tools |
| `src/rhmcp/data/gh1_to_gh2_map.yml` | New — GH1→GH2 type mapping |
| `tests/test_gh_intelligence.py` | New — unit tests |
| `tests/test_gh_intelligence_integration.py` | New — integration tests |
| `tests/fixtures/messy_canvas.gh` | New — refactor test fixture |
| `tests/fixtures/simple_migration.gh` | New — migration test fixture |
| `tests/test_smoke.py` | Update tool count to 351 |
| `pyproject.toml` | Bump version to 0.12.0 |
| `CHANGELOG.md` | Add v0.12.0 entry |

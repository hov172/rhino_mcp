# src/rhmcp/tools/gh_intelligence.py
"""
GH Intelligence tools: canvas analysis, refactor (de-spaghettify), GH1→GH2 migration.
Requires the RhinoMCP plugin (all tools are plugin-only — no rhinocode fallback).
"""
from __future__ import annotations

import re
from collections import deque
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_COORD = 100_000.0
_MAP_PATH = Path(__file__).parent.parent / "data" / "gh1_to_gh2_map.yml"
_GROUP_NAME_RE = re.compile(r'^[\w\s.\-]{1,64}$')  # group label validation pattern for user-supplied labels
_LAYER_W = 200.0    # horizontal spacing between layers
_NODE_H  = 120.0    # vertical spacing within a layer

# ---------------------------------------------------------------------------
# Layout utility (shared by GH1 and GH2 refactor)
# ---------------------------------------------------------------------------

def _compute_layout(
    components: list[dict],
    connections: list[dict],
) -> dict[str, dict]:
    """Topological sort → layer assignment → {id: {x, y}} positions.

    components: list of {id, x, y, name}
    connections: list of {from_id, to_id}
    Returns dict of {id: {x: float, y: float}} with..."""
    ids    = [c["id"] for c in components]
    id_set = set(ids)

    in_deg   = {id_: 0   for id_ in ids}
    children = {id_: []  for id_ in ids}

    for conn in connections:
        f = conn.get("from_id", "")
        t = conn.get("to_id", "")
        if f in id_set and t in id_set:
            children[f].append(t)
            in_deg[t] += 1

    # BFS to assign layers (longest-path to handle diamonds correctly)
    layer: dict[str, int] = {id_: 0 for id_ in ids if in_deg[id_] == 0}
    queue = deque(id_ for id_ in ids if in_deg[id_] == 0)
    in_deg_work = dict(in_deg)

    while queue:
        node = queue.popleft()
        for child in children[node]:
            in_deg_work[child] -= 1
            layer[child] = max(layer.get(child, 0), layer[node] + 1)
            if in_deg_work[child] == 0:
                queue.append(child)

    # Assign x/y by layer
    layer_rows: dict[int, int] = {}
    result: dict[str, dict] = {}
    for id_ in ids:
        lyr = layer.get(id_, 0)
        row = layer_rows.get(lyr, 0)
        result[id_] = {"x": float(lyr * _LAYER_W), "y": float(row * _NODE_H)}
        layer_rows[lyr] = row + 1

    return result


def _clamp_positions(layout: dict[str, dict]) -> dict[str, dict]:
    """Clamp all x/y values to ±_MAX_COORD."""
    return {
        id_: {
            "x": max(-_MAX_COORD, min(_MAX_COORD, pos["x"])),
            "y": max(-_MAX_COORD, min(_MAX_COORD, pos["y"])),
        }
        for id_, pos in layout.items()
    }

# ---------------------------------------------------------------------------
# GH1→GH2 type mapping
# ---------------------------------------------------------------------------

def _load_gh1_to_gh2_map() -> dict[str, str]:
    """Load gh1_to_gh2_map.yml. Logs specific failure reason; returns empty dict on error."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        with open(_MAP_PATH) as f:
            data = yaml.safe_load(f)
        if data is None:
            _log.warning("gh1_to_gh2_map.yml is empty — GH1→GH2 migration will report all components as unmapped")
            return {}
        if not isinstance(data, dict):
            _log.error("gh1_to_gh2_map.yml has unexpected format (expected a YAML mapping, got %s) — migration disabled", type(data).__name__)
            return {}
        result: dict[str, str] = {}
        for entry in data.get("mappings", []):
            gh1 = entry.get("gh1_guid", "")
            gh2 = entry.get("gh2_name", "")
            if gh1 and gh2:
                result[gh1.lower()] = gh2
        return result
    except FileNotFoundError:
        _log.error("gh1_to_gh2_map.yml not found at %s — GH1→GH2 migration will report all components as unmapped", _MAP_PATH)
        return {}
    except PermissionError as ex:
        _log.error("Cannot read gh1_to_gh2_map.yml (permission denied: %s) — migration disabled", ex)
        return {}
    except yaml.YAMLError as ex:
        _log.error("gh1_to_gh2_map.yml is malformed YAML: %s — migration disabled", ex)
        return {}
    except Exception as ex:
        _log.error("Unexpected error loading gh1_to_gh2_map.yml (%s: %s) — migration disabled", type(ex).__name__, ex)
        return {}


_GH1_TO_GH2_MAP: dict[str, str] = _load_gh1_to_gh2_map()

# ---------------------------------------------------------------------------
# Plugin dispatch helper
# ---------------------------------------------------------------------------

def _gh_intel(
    command: str,
    params: dict[str, object] | None = None,
    rhino_id: str | None = None,
) -> dict[str, object]:
    """Plugin-only dispatch with optional rhino_id routing. Unwraps the inner result dict."""
    from rhmcp.tools_helpers.plugin_client import connection_settings
    host, port, _ = connection_settings()
    try:
        r = rhino.plugin_result(command, params or {}, rhino_id=rhino_id)
        if isinstance(r, dict) and r.get("ok") and isinstance(r.get("result"), dict):
            return r["result"]
        return r
    except OSError as ex:
        return {
            "ok": False,
            "error": (
                f"Cannot reach the Rhino plugin at {host}:{port} — {ex}. "
                "Ensure Rhino is running, the RhinoMCP plugin is loaded (run MCPStart), "
                "and Grasshopper is open."
            ),
            "error_code": "SOCKET_UNAVAILABLE",
            "host": host,
            "port": port,
        }
    except TimeoutError as ex:
        return {
            "ok": False,
            "error": (
                f"Timed out waiting for Rhino plugin response on {host}:{port} — {ex}. "
                "The Grasshopper canvas may be busy; try again in a moment."
            ),
            "error_code": "TIMEOUT",
            "host": host,
            "port": port,
        }
    except ValueError as ex:
        return {
            "ok": False,
            "error": f"Malformed response from Rhino plugin (command={command!r}): {ex}",
            "error_code": "MALFORMED_RESPONSE",
        }
    except Exception as ex:
        return {
            "ok": False,
            "error": f"Unexpected error communicating with Rhino plugin (command={command!r}, {type(ex).__name__}): {ex}",
            "error_code": "INTERNAL_ERROR",
        }

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Analyze GH Canvas Complexity", readOnlyHint=True))
    def gh_analyze_canvas(rhino_id: str | None = None) -> dict[str, object]:
        """Analyze the active Grasshopper canvas and return complexity metrics.

        Returns component_count, connection_count, wire_crossing_estimate,
        cluster_count, ungrouped_component_count,..."""
        return _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Refactor GH1 Canvas Layout", destructiveHint=True))
    def gh_refactor_canvas(
        apply: bool = False,
        group_clusters: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Reorganise the active GH1 canvas to reduce wire crossings and add logical groups.

        apply: False (default) returns the layout plan without touching the canvas.
               True executes..."""
        analysis = _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)
        if not analysis.get("ok"):
            return analysis

        graph = _gh_intel("gh_get_graph_data", {}, rhino_id=rhino_id)
        if not graph.get("ok"):
            return graph

        components        = graph.get("components", [])
        connections       = graph.get("connections", [])
        clusters          = analysis.get("clusters", [])
        crossings_before  = int(analysis.get("wire_crossing_estimate", 0))

        # Compute layout via shared Python algorithm
        raw_layout = _compute_layout(components, connections)

        # Dry-run: validate all positions are within bounds (check before clamping)
        invalid = [id_ for id_, pos in raw_layout.items()
                   if abs(pos["x"]) > _MAX_COORD or abs(pos["y"]) > _MAX_COORD]
        if invalid:
            return {
                "ok":         False,
                "error":      "Layout validation failed — positions out of bounds",
                "error_code": "LAYOUT_VALIDATION_FAILED",
                "invalid_ids": invalid,
            }

        layout = _clamp_positions(raw_layout)

        # Build moves list (include from position for preview)
        pos_by_id = {c["id"]: {"x": c["x"], "y": c["y"]} for c in components}
        moves = [
            {"component_id": id_, "from": pos_by_id.get(id_, {}), "to": pos}
            for id_, pos in layout.items()
        ]

        if not apply:
            return {
                "ok":                       True,
                "preview":                  True,
                "moves":                    moves,
                "groups_to_add":            len(clusters) if group_clusters else 0,
                "estimated_crossings_after": max(0, crossings_before - len(moves) // 4),
            }

        # Apply moves
        name_by_id = {c["id"]: c.get("name", "") for c in components}
        moved  = 0
        failed = []
        for id_, pos in layout.items():
            r = _gh_intel("gh_move_component",
                          {"instance_guid": id_, "x": pos["x"], "y": pos["y"]},
                          rhino_id=rhino_id)
            if r.get("ok"):
                moved += 1
            else:
                name = name_by_id.get(id_, "")
                failed.append({
                    "id": id_,
                    "name": name,
                    "target": pos,
                    "error": r.get("error") or r.get("message") or "Unknown move failure",
                    "error_code": r.get("error_code", ""),
                })

        if failed:
            return {
                "ok": False,
                "error": f"Failed to move {len(failed)} of {len(layout)} component(s). See 'failed' for details.",
                "error_code": "MOVE_PARTIAL_FAILURE",
                "moved": moved,
                "failed": failed,
            }

        # Add groups per cluster
        groups_added = 0
        if group_clusters:
            for cluster in clusters:
                member_ids = cluster.get("member_ids", [])
                if len(member_ids) >= 2:
                    r = _gh_intel(
                        "gh_add_group",
                        {"instance_guids": member_ids, "label": cluster.get("label", "")},
                        rhino_id=rhino_id,
                    )
                    if r.get("ok"):
                        groups_added += 1

        # Re-read crossings after
        after = _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)
        crossings_after = int(after.get("wire_crossing_estimate", 0)) if after.get("ok") else 0

        return {
            "ok":              True,
            "moved":           moved,
            "groups_added":    groups_added,
            "crossings_before": crossings_before,
            "crossings_after": crossings_after,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Refactor GH2 Canvas Layout", destructiveHint=True))
    def gh2_refactor_canvas(
        apply: bool = False,
        group_clusters: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Reorganise the active GH2 canvas to reduce wire crossings and add logical groups.
        Requires Rhino 9 — returns GH2_NOT_AVAILABLE on Rhino 8.

        apply: False (default) returns layout..."""
        # Read GH2 canvas (GH2 graph already exposes positions + connections)
        graph = _gh_intel("gh2_get_canvas_graph", {"sample_size": 0}, rhino_id=rhino_id)  # 0 = return all components
        if not graph.get("ok"):
            return graph

        # Normalise GH2 graph data to same shape as GH1 graph data
        raw_comps = graph.get("components", [])
        components = [
            {
                "id": c.get("instance_guid") or c.get("id", ""),
                "x":  float(c.get("x", 0)),
                "y":  float(c.get("y", 0)),
                "name": c.get("name", ""),
            }
            for c in raw_comps
        ]
        raw_conns = graph.get("connections", graph.get("wires", []))
        connections = [
            {
                "from_id": w.get("from_instance") or w.get("from_id", ""),
                "to_id":   w.get("to_instance")   or w.get("to_id", ""),
            }
            for w in raw_conns
        ]

        # Compute clusters from connections (BFS)
        id_set = {c["id"] for c in components}
        adj: dict[str, list] = {c["id"]: [] for c in components}
        rev: dict[str, list] = {c["id"]: [] for c in components}
        for conn in connections:
            f, t = conn["from_id"], conn["to_id"]
            if f in id_set and t in id_set:
                adj[f].append(t)
                rev[t].append(f)

        visited: set[str] = set()
        clusters = []
        for comp in components:
            cid = comp["id"]
            if cid in visited:
                continue
            members: list[str] = []
            queue: deque[str] = deque([cid])
            visited.add(cid)
            while queue:
                node = queue.popleft()
                members.append(node)
                for nb in adj[node] + rev[node]:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            clusters.append({"member_ids": members, "label": f"Cluster {len(clusters) + 1}"})

        # Build pos_by_id before crossings_before to avoid redundant linear scans
        pos_by_id = {c["id"]: {"x": c["x"], "y": c["y"]} for c in components}

        crossings_before = sum(
            1 for conn in connections
            if conn["from_id"] in id_set and conn["to_id"] in id_set
            and pos_by_id.get(conn["from_id"], {}).get("x", 0)
            > pos_by_id.get(conn["to_id"], {}).get("x", 0)
        )

        raw_layout = _compute_layout(components, connections)
        # Validate before clamping (same pattern as gh_refactor_canvas)
        invalid = [id_ for id_, pos in raw_layout.items()
                   if abs(pos["x"]) > _MAX_COORD or abs(pos["y"]) > _MAX_COORD]
        if invalid:
            return {
                "ok": False, "error": "Layout validation failed",
                "error_code": "LAYOUT_VALIDATION_FAILED", "invalid_ids": invalid,
            }
        layout = _clamp_positions(raw_layout)
        moves = [{"component_id": id_, "from": pos_by_id.get(id_, {}), "to": pos}
                 for id_, pos in layout.items()]

        if not apply:
            return {
                "ok":                       True,
                "preview":                  True,
                "moves":                    moves,
                "groups_to_add":            len(clusters) if group_clusters else 0,
                "estimated_crossings_after": max(0, crossings_before - len(moves) // 4),
            }

        name_by_id_gh2 = {c["id"]: c.get("name", "") for c in components}
        moved = 0
        failed = []
        for id_, pos in layout.items():
            r = _gh_intel("gh2_move_component",
                          {"instance_guid": id_, "x": pos["x"], "y": pos["y"]},
                          rhino_id=rhino_id)
            if r.get("ok"):
                moved += 1
            else:
                name = name_by_id_gh2.get(id_, "")
                failed.append({
                    "id": id_,
                    "name": name,
                    "target": pos,
                    "error": r.get("error") or r.get("message") or "Unknown move failure",
                    "error_code": r.get("error_code", ""),
                })

        if failed:
            return {
                "ok": False,
                "error": f"Failed to move {len(failed)} of {len(layout)} GH2 component(s). See 'failed' for details.",
                "error_code": "MOVE_PARTIAL_FAILURE",
                "moved": moved,
                "failed": failed,
            }

        groups_added = 0
        if group_clusters:
            for cluster in clusters:
                members = cluster.get("member_ids", [])
                if len(members) >= 2:
                    r = _gh_intel("gh2_add_group",
                                  {"instance_guids": members, "label": cluster.get("label", "")},
                                  rhino_id=rhino_id)
                    if r.get("ok"):
                        groups_added += 1

        after = _gh_intel("gh2_get_canvas_graph", {"sample_size": 0}, rhino_id=rhino_id)  # 0 = return all components
        crossings_after = 0
        if after.get("ok"):
            after_comps = {c.get("instance_guid", c.get("id", "")): c
                           for c in after.get("components", [])}
            after_wires = after.get("connections", after.get("wires", []))
            crossings_after = sum(
                1 for w in after_wires
                if (after_comps.get(w.get("from_instance", w.get("from_id", "")), {}).get("x", 0))
                > (after_comps.get(w.get("to_instance",   w.get("to_id",   "")), {}).get("x", 0))
            )

        return {
            "ok":               True,
            "moved":            moved,
            "groups_added":     groups_added,
            "crossings_before": crossings_before,
            "crossings_after":  crossings_after,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Migrate GH1 Definition to GH2", destructiveHint=True))
    def gh_migrate_to_gh2(
        confirm: bool = False,
        close_gh1: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Migrate the active GH1 definition to a new GH2 canvas.
        Requires Rhino 9 — GH2 is not available in stable Rhino 8.

        confirm: Must be True to execute (safety guard against accidental..."""
        if not confirm:
            return {
                "ok":         False,
                "error":      "Set confirm=True to execute the migration.",
                "error_code": "CONFIRMATION_REQUIRED",
            }

        # Step 1: export GH1 data
        export = _gh_intel("gh1_export_migration_data", {}, rhino_id=rhino_id)
        if not export.get("ok"):
            return export

        components = export.get("components", [])

        if not _GH1_TO_GH2_MAP:
            return {
                "ok": False,
                "error": (
                    "GH1→GH2 component map could not be loaded. "
                    f"Expected file: {_MAP_PATH}. "
                    "Check that the file exists, is readable, and is valid YAML. "
                    "See server logs for the specific load error."
                ),
                "error_code": "MAP_LOAD_FAILED",
            }

        # Step 2: map types via YAML
        mapped   = []
        unmapped = []
        for comp in components:
            type_guid = comp.get("type_guid", "").lower()
            gh2_name  = _GH1_TO_GH2_MAP.get(type_guid)
            if gh2_name:
                mapped.append({
                    "key":        comp["instance_guid"],
                    "type_name":  gh2_name,
                    "x":          comp.get("x", 0.0),
                    "y":          comp.get("y", 0.0),
                })
            else:
                unmapped.append({
                    "gh1_guid":  comp.get("type_guid", ""),
                    "nickname":  comp.get("nick_name", ""),
                    "reason":    "No GH2 equivalent in mapping table",
                })

        # Build wires for mapped components only
        mapped_keys = {c["key"] for c in mapped}
        wires = []
        for comp in components:
            if comp["instance_guid"] not in mapped_keys:
                continue
            for conn in comp.get("connections", []):
                to_key = conn.get("to_id", "")
                if to_key in mapped_keys:
                    wires.append({
                        "from_key":    comp["instance_guid"],
                        "from_output": conn.get("from_output", "0"),
                        "to_key":      to_key,
                        "to_input":    conn.get("to_input", "0"),
                    })

        # Step 3: ensure GH2 is open
        start = _gh_intel("gh2_start", {}, rhino_id=rhino_id)
        if not start.get("ok"):
            return start

        # Step 4: apply graph
        apply_result = _gh_intel(
            "gh2_apply_graph",
            {"components": mapped, "wires": wires},
            rhino_id=rhino_id,
        )
        if not apply_result.get("ok"):
            return {
                "ok": False,
                "error": (
                    apply_result.get("error")
                    or apply_result.get("message")
                    or "gh2_apply_graph returned an error with no message"
                ),
                "error_code": apply_result.get("error_code", "APPLY_GRAPH_FAILED"),
                "migrated": 0,
                "unmapped": unmapped,
                "gh2_errors": apply_result.get("errors", []),
            }
        gh2_errors = apply_result.get("errors", [])

        # Step 5: optionally close GH1
        gh1_closed = False
        if close_gh1:
            close_result = _gh_intel("gh_close_definition", {}, rhino_id=rhino_id)
            gh1_closed = close_result.get("ok", False)

        return {
            "ok":        True,
            "migrated":  len(mapped),
            "unmapped":  unmapped,
            "gh2_errors": gh2_errors,
            "gh1_closed": gh1_closed,
        }

    @mcp.tool(annotations=ToolAnnotations(title="Move GH2 Component", destructiveHint=True))
    def gh2_move_component(
        instance_guid: str,
        x: float,
        y: float,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Move a GH2 component to new canvas coordinates.
        Requires Rhino 9 — returns GH2_NOT_AVAILABLE on Rhino 8.

        instance_guid: UUID of the GH2 component to move.
        x, y: Target..."""
        return _gh_intel(
            "gh2_move_component",
            {"instance_guid": instance_guid, "x": x, "y": y},
            rhino_id=rhino_id,
        )

    @mcp.tool(annotations=ToolAnnotations(title="Add GH2 Group", destructiveHint=True))
    def gh2_add_group(
        instance_guids: list[str],
        label: str = "",
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Add a group containing the specified GH2 components.
        Requires Rhino 9 — returns GH2_NOT_AVAILABLE on Rhino 8.

        instance_guids: List of GH2 component UUIDs to include in the..."""
        return _gh_intel(
            "gh2_add_group",
            {"instance_guids": instance_guids, "label": label},
            rhino_id=rhino_id,
        )

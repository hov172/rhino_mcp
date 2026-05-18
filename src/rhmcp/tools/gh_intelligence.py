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
_GROUP_NAME_RE = re.compile(r'^[\w\s.\-]{1,64}$')  # used by gh_refactor_canvas for group label validation
_LAYER_W = 200.0    # horizontal spacing between layers
_NODE_H  = 120.0    # vertical spacing within a layer

# ---------------------------------------------------------------------------
# Layout utility (shared by GH1 and GH2 refactor)
# ---------------------------------------------------------------------------

def _compute_layout(
    components: list[dict],
    connections: list[dict],
) -> dict[str, dict]:
    """
    Topological sort → layer assignment → {id: {x, y}} positions.

    components: list of {id, x, y, name}
    connections: list of {from_id, to_id}
    Returns dict of {id: {x: float, y: float}} with left-to-right data flow.
    Nodes in cycles or unreachable nodes are placed at layer 0 with fresh coordinates.
    """
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
    """Load gh1_to_gh2_map.yml. Returns empty dict on any error."""
    try:
        with open(_MAP_PATH) as f:
            data = yaml.safe_load(f)
        result: dict[str, str] = {}
        for entry in data.get("mappings", []):
            gh1 = entry.get("gh1_guid", "")
            gh2 = entry.get("gh2_name", "")
            if gh1 and gh2:
                result[gh1.lower()] = gh2
        return result
    except Exception:
        return {}


_GH1_TO_GH2_MAP: dict[str, str] = _load_gh1_to_gh2_map()

# ---------------------------------------------------------------------------
# Plugin dispatch helper
# ---------------------------------------------------------------------------

def _gh_intel(
    command: str,
    params: dict[str, object],
    rhino_id: str | None = None,
) -> dict[str, object]:
    """Plugin-only dispatch with optional rhino_id routing."""
    try:
        return rhino.plugin_result(command, params, rhino_id=rhino_id)
    except OSError:
        return {"ok": False, "error": "Grasshopper plugin is not connected. Ensure Rhino is running with the RhinoMCP plugin loaded."}

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=ToolAnnotations(title="Analyze GH Canvas Complexity", readOnlyHint=True))
    def gh_analyze_canvas(rhino_id: str | None = None) -> dict[str, object]:
        """
        Analyze the active Grasshopper canvas and return complexity metrics.

        Returns component_count, connection_count, wire_crossing_estimate,
        cluster_count, ungrouped_component_count, isolated_component_count,
        complexity_score (0-100), canvas_bounds, and suggestions[].
        No side effects — safe to call at any time.
        """
        return _gh_intel("gh_get_canvas_analysis", {}, rhino_id=rhino_id)

    @mcp.tool(annotations=ToolAnnotations(title="Refactor GH1 Canvas Layout", destructiveHint=True))
    def gh_refactor_canvas(
        apply: bool = False,
        group_clusters: bool = True,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """
        Reorganise the active GH1 canvas to reduce wire crossings and add logical groups.

        apply: False (default) returns the layout plan without touching the canvas.
               True executes all moves and group additions.
        group_clusters: Add GH groups per detected cluster when apply=True (default True).

        Returns {ok, preview, moves[], groups_to_add, estimated_crossings_after} when apply=False.
        Returns {ok, moved, groups_added, crossings_before, crossings_after} when apply=True.
        """
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
        moved  = 0
        failed = []
        for id_, pos in layout.items():
            r = _gh_intel("gh_move_component",
                          {"instance_guid": id_, "x": pos["x"], "y": pos["y"]},
                          rhino_id=rhino_id)
            if r.get("ok"):
                moved += 1
            else:
                failed.append({"id": id_, "error": r.get("error", "")})

        if failed:
            return {"ok": False, "moved": moved, "failed": failed}

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

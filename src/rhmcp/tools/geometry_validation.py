"""
Tools for validating Rhino geometry quality — gaps, orthogonality, duplicates.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend as rhino


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Validate Rhino Geometry", readOnlyHint=False))
    def validate_rhino_geometry(
        object_ids: list[str] | None = None,
        gap_tolerance: float = 0.01,
        angle_tolerance: float = 1.0,
        auto_fix: bool = False,
        rhino_id: str | None = None,
    ) -> dict[str, object]:
        """Validate curve/line geometry in the Rhino document for common quality issues.

        Checks performed:
        - **zero_length**: curves shorter than 0.001 document units (error).
        -..."""
        code = (
            "_mcp_object_ids = {!r}\n"
            "_mcp_gap_tolerance = {!r}\n"
            "_mcp_angle_tolerance = {!r}\n"
            "_mcp_auto_fix = {!r}\n"
            "{}"
        ).format(object_ids, gap_tolerance, angle_tolerance, auto_fix, _VALIDATION_SCRIPT)
        return rhino.execute_python(code, rhino_id=rhino_id)


_VALIDATION_SCRIPT = r'''
import rhinoscriptsyntax as rs
import Rhino
import math

issues = []
fixed_count = 0

# ── 1. Collect objects ────────────────────────────────────────────────────────
if _mcp_object_ids is not None:
    obj_ids = [str(x) for x in _mcp_object_ids]
else:
    obj_ids = rs.ObjectsByType(4, select=False) or []  # 4 = curve
    obj_ids = [str(x) for x in obj_ids]

object_count = len(obj_ids)

# ── 2. Zero-length check ──────────────────────────────────────────────────────
valid_ids = []
for oid in obj_ids:
    try:
        length = rs.CurveLength(oid)
    except Exception:
        length = None
    if length is None:
        continue
    if length < 0.001:
        issues.append({
            "type": "zero_length",
            "severity": "error",
            "description": "Curve {} has zero or near-zero length ({:.6f}).".format(oid, length),
            "object_ids": [oid],
            "detail": {"length": length},
        })
    else:
        valid_ids.append(oid)

# ── 3. Collect endpoints ──────────────────────────────────────────────────────
endpoints = []  # list of (oid, 'start'|'end', [x,y,z])
for oid in valid_ids:
    try:
        sp = rs.CurveStartPoint(oid)
        ep = rs.CurveEndPoint(oid)
        if sp is not None:
            endpoints.append((oid, 'start', [sp.X, sp.Y, sp.Z]))
        if ep is not None:
            endpoints.append((oid, 'end', [ep.X, ep.Y, ep.Z]))
    except Exception:
        pass

def _dist(a, b):
    return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))

# ── 4. Gap check ──────────────────────────────────────────────────────────────
gap_pairs = set()  # frozenset of two (oid, role) tuples already reported
for i in range(len(endpoints)):
    oid_a, role_a, pt_a = endpoints[i]
    for j in range(i + 1, len(endpoints)):
        oid_b, role_b, pt_b = endpoints[j]
        if oid_a == oid_b:
            continue
        d = _dist(pt_a, pt_b)
        if 0 < d < _mcp_gap_tolerance:
            key = frozenset([(oid_a, role_a), (oid_b, role_b)])
            if key not in gap_pairs:
                gap_pairs.add(key)
                mid = [(pt_a[k] + pt_b[k]) / 2.0 for k in range(3)]
                issues.append({
                    "type": "gap",
                    "severity": "warning",
                    "description": "Gap of {:.4f} between {} ({}) and {} ({}).".format(
                        d, oid_a, role_a, oid_b, role_b),
                    "object_ids": [oid_a, oid_b],
                    "detail": {
                        "distance": d,
                        "point": mid,
                        "endpoint_a": {"object_id": oid_a, "role": role_a, "point": pt_a},
                        "endpoint_b": {"object_id": oid_b, "role": role_b, "point": pt_b},
                    },
                })
                # Auto-fix: move both endpoints to midpoint
                if _mcp_auto_fix:
                    try:
                        mid_pt = Rhino.Geometry.Point3d(mid[0], mid[1], mid[2])
                        crv_a = rs.coercecurve(oid_a)
                        crv_b = rs.coercecurve(oid_b)
                        if crv_a is not None and crv_b is not None:
                            if role_a == 'start':
                                crv_a.SetStartPoint(mid_pt)
                            else:
                                crv_a.SetEndPoint(mid_pt)
                            if role_b == 'start':
                                crv_b.SetStartPoint(mid_pt)
                            else:
                                crv_b.SetEndPoint(mid_pt)
                            rs.coercerhinoobject(oid_a).CommitChanges()
                            rs.coercerhinoobject(oid_b).CommitChanges()
                            fixed_count += 1
                    except Exception:
                        pass

# ── 5. Non-orthogonal check (lines only) ──────────────────────────────────────
ORTHO_ANGLES = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0]

for oid in valid_ids:
    try:
        if not rs.IsLine(oid):
            continue
        sp = rs.CurveStartPoint(oid)
        ep = rs.CurveEndPoint(oid)
        if sp is None or ep is None:
            continue
        dx = ep.X - sp.X
        dy = ep.Y - sp.Y
        angle_deg = math.degrees(math.atan2(dy, dx)) % 360.0
        # Find nearest orthogonal angle
        deviations = [abs(angle_deg - a) for a in ORTHO_ANGLES]
        min_dev = min(deviations)
        nearest = ORTHO_ANGLES[deviations.index(min_dev)]
        # Wrap nearest to [0,360)
        nearest = nearest % 360.0
        if min_dev > _mcp_angle_tolerance:
            issues.append({
                "type": "non_orthogonal",
                "severity": "warning",
                "description": "Line {} has angle {:.2f}° — {:.2f}° from nearest orthogonal ({:.0f}°).".format(
                    oid, angle_deg, min_dev, nearest),
                "object_ids": [oid],
                "detail": {
                    "angle_deg": angle_deg,
                    "nearest_orthogonal": nearest,
                    "deviation_deg": min_dev,
                },
            })
    except Exception:
        pass

# ── 6. Duplicate check ────────────────────────────────────────────────────────
# Build a lookup: oid -> (start_pt, end_pt)
pt_map = {}
for oid in valid_ids:
    try:
        sp = rs.CurveStartPoint(oid)
        ep = rs.CurveEndPoint(oid)
        if sp is not None and ep is not None:
            pt_map[oid] = ([sp.X, sp.Y, sp.Z], [ep.X, ep.Y, ep.Z])
    except Exception:
        pass

oid_list = list(pt_map.keys())
dup_reported = set()
to_delete = []

for i in range(len(oid_list)):
    oid_a = oid_list[i]
    if oid_a in dup_reported:
        continue
    sp_a, ep_a = pt_map[oid_a]
    for j in range(i + 1, len(oid_list)):
        oid_b = oid_list[j]
        if oid_b in dup_reported:
            continue
        sp_b, ep_b = pt_map[oid_b]
        # Same direction or reversed
        same_dir = (_dist(sp_a, sp_b) < _mcp_gap_tolerance and
                    _dist(ep_a, ep_b) < _mcp_gap_tolerance)
        rev_dir  = (_dist(sp_a, ep_b) < _mcp_gap_tolerance and
                    _dist(ep_a, sp_b) < _mcp_gap_tolerance)
        if same_dir or rev_dir:
            dup_reported.add(oid_b)
            issues.append({
                "type": "duplicate",
                "severity": "error",
                "description": "Objects {} and {} are duplicates.".format(oid_a, oid_b),
                "object_ids": [oid_a, oid_b],
                "detail": {},
            })
            if _mcp_auto_fix:
                to_delete.append(oid_b)

# Auto-fix: delete duplicates
for oid in to_delete:
    try:
        rs.DeleteObject(oid)
        fixed_count += 1
    except Exception:
        pass

# ── 7. Build result ───────────────────────────────────────────────────────────
issue_count = len(issues)
error_count   = sum(1 for i in issues if i["severity"] == "error")
warning_count = sum(1 for i in issues if i["severity"] == "warning")

if issue_count == 0:
    summary = "No issues found in {} object(s).".format(object_count)
else:
    parts = []
    if error_count:
        parts.append("{} error(s)".format(error_count))
    if warning_count:
        parts.append("{} warning(s)".format(warning_count))
    summary = "Found {} issue(s) ({}) in {} object(s).".format(
        issue_count, ", ".join(parts), object_count)
    if _mcp_auto_fix and fixed_count:
        summary += " {} fix(es) applied.".format(fixed_count)

result = {
    "ok": issue_count == 0,
    "object_count": object_count,
    "issue_count": issue_count,
    "issues": issues,
    "fixed_count": fixed_count,
    "summary": summary,
}
'''

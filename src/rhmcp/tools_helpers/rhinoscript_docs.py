"""
Compact RhinoScriptSyntax documentation index.

This is intentionally small and focused on high-value modeling functions. The
official RhinoScriptSyntax reference remains the exhaustive source.
"""

from __future__ import annotations

from typing import Any

RHINOSCRIPT_MODULES: list[dict[str, Any]] = [
    {
        "ModuleName": "curve",
        "functions": [
            {"Name": "AddCurve", "Signature": "AddCurve(points, degree=3)", "Description": "Adds an interpolated curve object.", "Returns": "Guid"},
            {"Name": "AddLine", "Signature": "AddLine(start, end)", "Description": "Adds a line curve.", "Returns": "Guid"},
            {"Name": "AddPolyline", "Signature": "AddPolyline(points)", "Description": "Adds a polyline curve.", "Returns": "Guid"},
            {"Name": "AddCircle", "Signature": "AddCircle(plane_or_center, radius)", "Description": "Adds a circle curve.", "Returns": "Guid"},
            {"Name": "AddEllipse", "Signature": "AddEllipse(plane, radius_x, radius_y)", "Description": "Adds an ellipse curve.", "Returns": "Guid"},
            {"Name": "AddArc3Pt", "Signature": "AddArc3Pt(start, end, point_on_arc)", "Description": "Adds an arc through three points.", "Returns": "Guid"},
            {"Name": "OffsetCurve", "Signature": "OffsetCurve(object_id, direction, distance, normal=None, style=1)", "Description": "Offsets a curve.", "Returns": "Guid or list"},
            {"Name": "SplitCurve", "Signature": "SplitCurve(curve_id, parameters, delete_input=False)", "Description": "Splits a curve at parameters.", "Returns": "List of Guids"},
            {"Name": "CurveCurveIntersection", "Signature": "CurveCurveIntersection(curve_a, curve_b, tolerance=None)", "Description": "Finds curve intersections.", "Returns": "Intersection event list"},
            {"Name": "ProjectCurveToSurface", "Signature": "ProjectCurveToSurface(curve_ids, surface_ids, direction)", "Description": "Projects curves to surfaces.", "Returns": "List of Guids"},
        ],
    },
    {
        "ModuleName": "surface",
        "functions": [
            {"Name": "AddLoftSrf", "Signature": "AddLoftSrf(object_ids, start=None, end=None, loft_type=0, simplify_method=0, value=0, closed=False)", "Description": "Creates loft surfaces through curves.", "Returns": "List of Guids"},
            {"Name": "AddSweep1", "Signature": "AddSweep1(rail, shapes, closed=False)", "Description": "Creates a one-rail sweep surface.", "Returns": "List of Guids"},
            {"Name": "ExtrudeCurveStraight", "Signature": "ExtrudeCurveStraight(curve_id, start, end)", "Description": "Extrudes a curve between two points.", "Returns": "Guid"},
            {"Name": "AddSrfPt", "Signature": "AddSrfPt(points)", "Description": "Creates a surface from corner points.", "Returns": "Guid"},
            {"Name": "AddPlaneSurface", "Signature": "AddPlaneSurface(plane, u_dir, v_dir)", "Description": "Creates a plane surface.", "Returns": "Guid"},
            {"Name": "CapPlanarHoles", "Signature": "CapPlanarHoles(surface_id)", "Description": "Caps planar holes in a surface/polysurface.", "Returns": "Guid"},
        ],
    },
    {
        "ModuleName": "solid",
        "functions": [
            {"Name": "AddBox", "Signature": "AddBox(corners)", "Description": "Adds a box from eight corner points.", "Returns": "Guid"},
            {"Name": "AddSphere", "Signature": "AddSphere(center, radius)", "Description": "Adds a sphere.", "Returns": "Guid"},
            {"Name": "AddCylinder", "Signature": "AddCylinder(base, height, radius, cap=True)", "Description": "Adds a cylinder.", "Returns": "Guid"},
            {"Name": "AddCone", "Signature": "AddCone(base, height, radius, cap=True)", "Description": "Adds a cone.", "Returns": "Guid"},
            {"Name": "AddTorus", "Signature": "AddTorus(base, major_radius, minor_radius)", "Description": "Adds a torus.", "Returns": "Guid"},
            {"Name": "BooleanUnion", "Signature": "BooleanUnion(input, delete_input=True)", "Description": "Unions solid objects.", "Returns": "List of Guids"},
            {"Name": "BooleanDifference", "Signature": "BooleanDifference(input0, input1, delete_input=True)", "Description": "Subtracts solids.", "Returns": "List of Guids"},
            {"Name": "BooleanIntersection", "Signature": "BooleanIntersection(input, delete_input=True)", "Description": "Intersects solids.", "Returns": "List of Guids"},
        ],
    },
    {
        "ModuleName": "object",
        "functions": [
            {"Name": "AllObjects", "Signature": "AllObjects(select=False, include_lights=False, include_grips=False)", "Description": "Returns all document object ids.", "Returns": "List of Guids"},
            {"Name": "SelectedObjects", "Signature": "SelectedObjects(include_lights=False, include_grips=False)", "Description": "Returns selected object ids.", "Returns": "List of Guids"},
            {"Name": "ObjectName", "Signature": "ObjectName(object_id, name=None)", "Description": "Gets or sets object name.", "Returns": "String"},
            {"Name": "ObjectLayer", "Signature": "ObjectLayer(object_id, layer=None)", "Description": "Gets or sets object layer.", "Returns": "String"},
            {"Name": "ObjectColor", "Signature": "ObjectColor(object_id, color=None)", "Description": "Gets or sets object color.", "Returns": "Color"},
            {"Name": "DeleteObjects", "Signature": "DeleteObjects(object_ids)", "Description": "Deletes objects.", "Returns": "Number"},
        ],
    },
    {
        "ModuleName": "transformation",
        "functions": [
            {"Name": "MoveObjects", "Signature": "MoveObjects(object_ids, translation)", "Description": "Moves objects.", "Returns": "List of Guids"},
            {"Name": "RotateObjects", "Signature": "RotateObjects(object_ids, center, angle, axis=None, copy=False)", "Description": "Rotates objects.", "Returns": "List of Guids"},
            {"Name": "ScaleObjects", "Signature": "ScaleObjects(object_ids, origin, scale, copy=False)", "Description": "Scales objects.", "Returns": "List of Guids"},
        ],
    },
    {
        "ModuleName": "layer",
        "functions": [
            {"Name": "AddLayer", "Signature": "AddLayer(name=None, color=None, visible=True, locked=False, parent=None)", "Description": "Creates a layer.", "Returns": "Layer name"},
            {"Name": "DeleteLayer", "Signature": "DeleteLayer(layer)", "Description": "Deletes a layer.", "Returns": "Boolean"},
            {"Name": "CurrentLayer", "Signature": "CurrentLayer(layer=None)", "Description": "Gets or sets current layer.", "Returns": "Layer name"},
            {"Name": "LayerNames", "Signature": "LayerNames(sort=False)", "Description": "Lists layer names.", "Returns": "List"},
        ],
    },
]


def search_functions(query: str, limit: int = 10) -> list[dict[str, Any]]:
    terms = query.lower().split()
    results: list[dict[str, Any]] = []
    for module in RHINOSCRIPT_MODULES:
        for func in module["functions"]:
            text = "{} {} {}".format(func["Name"], func.get("Signature", ""), func.get("Description", "")).lower()
            score = sum(text.count(term) for term in terms)
            if score:
                results.append({**func, "module": module["ModuleName"], "_score": score})
    results.sort(key=lambda item: (-int(item["_score"]), str(item["Name"])))
    for item in results:
        item.pop("_score", None)
    return results[:limit]


def get_function(function_name: str) -> dict[str, Any] | None:
    for module in RHINOSCRIPT_MODULES:
        for func in module["functions"]:
            if str(func["Name"]).lower() == function_name.lower():
                return {**func, "module": module["ModuleName"]}
    return None

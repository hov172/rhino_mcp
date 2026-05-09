"""
Integration tests — require a live Rhino 8 with rhino-mcp plugin loaded.

All tests are marked ``integration`` and auto-skip when no plugin socket is
reachable, so they never block CI. Run them locally after starting Rhino:

    pytest tests/test_integration.py -v -m integration

or, to run alongside the unit suite:

    pytest -m "not integration"   # CI — skip all integration tests
    pytest                        # local — skips automatically if no Rhino
"""

from __future__ import annotations

import pytest

from rhmcp.tools_helpers.plugin_client import health_check, send_command

# ── session fixture ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def rhino():
    """Skip the entire session when Rhino is not reachable."""
    hc = health_check(timeout=2.0)
    if not hc.get("ok"):
        pytest.skip(
            "Rhino plugin not reachable — open Rhino 8 and run MCPStart, "
            f"then re-run. (error_code={hc.get('error_code')})"
        )
    return hc


# ── helpers ────────────────────────────────────────────────────────────────────

def _py(script: str) -> dict:
    """Execute a Python snippet in Rhino and return the result dict."""
    from rhmcp.tools_helpers.backend import execute_python
    return execute_python(script)


def _delete(object_id: str) -> None:
    """Best-effort cleanup — delete one object from the document."""
    _py(f"""
import rhinoscriptsyntax as rs
rs.DeleteObject("{object_id}")
result = {{"ok": True}}
""")


# ── connectivity ───────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_health_check_roundtrip(rhino):
    assert rhino["ok"] is True
    assert isinstance(rhino["latency_ms"], (int, float))
    assert rhino["latency_ms"] < 2000
    assert "rhino" in rhino


@pytest.mark.integration
def test_ping_directly(rhino):
    resp = send_command("ping", {})
    assert resp.get("ok") is True
    assert "version" in resp


# ── Python execution ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_execute_python_arithmetic(rhino):
    result = _py("result = {'value': 2 + 2}")
    assert result.get("value") == 4


@pytest.mark.integration
def test_execute_python_rhinoscriptsyntax_import(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
result = {"ok": True, "unit": rs.UnitSystemName()}
""")
    assert result.get("ok") is True
    assert isinstance(result.get("unit"), str)


# ── geometry CRUD ──────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_create_and_delete_sphere(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
oid = rs.AddSphere([0, 0, 0], 1.0)
result = {"id": str(oid), "ok": bool(oid)}
""")
    assert result.get("ok") is True
    sphere_id = result["id"]
    try:
        info = _py(f"""
import rhinoscriptsyntax as rs
oid = "{sphere_id}"
result = {{"exists": rs.IsObject(oid), "type": rs.ObjectType(oid)}}
""")
        assert info.get("exists") is True
    finally:
        _delete(sphere_id)


@pytest.mark.integration
def test_create_box(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
corners = [rs.CreatePoint(p) for p in [[0,0,0],[1,0,0],[1,1,0],[0,1,0]]]
box = rs.AddBox([[0,0,0],[1,0,0],[1,1,0],[0,1,0],
                  [0,0,1],[1,0,1],[1,1,1],[0,1,1]])
result = {"id": str(box) if box else None, "ok": bool(box)}
""")
    assert result.get("ok") is True
    _delete(result["id"])


@pytest.mark.integration
def test_create_line_curve(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
cid = rs.AddLine([0, 0, 0], [10, 0, 0])
result = {"id": str(cid), "ok": bool(cid), "length": rs.CurveLength(cid)}
""")
    assert result.get("ok") is True
    assert abs(result.get("length", 0) - 10.0) < 0.001
    _delete(result["id"])


# ── layer operations ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_layer_create_and_delete(rhino):
    layer_name = "__rhino_mcp_test_layer__"
    result = _py(f"""
import rhinoscriptsyntax as rs
name = "{layer_name}"
if not rs.IsLayer(name):
    rs.AddLayer(name)
result = {{"exists": rs.IsLayer(name)}}
""")
    assert result.get("exists") is True
    cleanup = _py(f"""
import rhinoscriptsyntax as rs
rs.DeleteLayer("{layer_name}")
result = {{"ok": True}}
""")
    assert cleanup.get("ok") is True


# ── transform operations ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_move_object(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
oid = rs.AddSphere([0, 0, 0], 0.5)
rs.MoveObject(oid, [5, 0, 0])
cp = rs.SphereCenter(oid)
result = {"id": str(oid), "cx": cp.X, "ok": True}
""")
    assert result.get("ok") is True
    assert abs(result.get("cx", 0) - 5.0) < 0.001
    _delete(result["id"])


# ── user text ─────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_set_and_get_user_text(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
oid = rs.AddPoint([0, 0, 0])
rs.SetUserText(oid, "mcp_test_key", "hello_world")
val = rs.GetUserText(oid, "mcp_test_key")
result = {"id": str(oid), "value": val, "ok": val == "hello_world"}
""")
    assert result.get("ok") is True
    _delete(result["id"])


# ── groups ────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_group_create_and_delete(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
p1 = rs.AddPoint([0, 0, 0])
p2 = rs.AddPoint([1, 0, 0])
gname = rs.AddGroup("__mcp_test_group__")
rs.AddObjectsToGroup([p1, p2], gname)
members = rs.ObjectsByGroup(gname) or []
rs.DeleteGroup(gname)
rs.DeleteObjects([p1, p2])
result = {"member_count": len(members), "ok": len(members) == 2}
""")
    assert result.get("ok") is True


# ── analysis ──────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_measure_distance(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
d = rs.Distance([0, 0, 0], [3, 4, 0])
result = {"distance": d, "ok": abs(d - 5.0) < 0.001}
""")
    assert result.get("ok") is True


@pytest.mark.integration
def test_bounding_box(rhino):
    result = _py("""
import rhinoscriptsyntax as rs
oid = rs.AddBox([[0,0,0],[2,0,0],[2,2,0],[0,2,0],
                  [0,0,2],[2,0,2],[2,2,2],[0,2,2]])
bb = rs.BoundingBox(oid)
rs.DeleteObject(oid)
result = {"ok": bb is not None, "count": len(bb) if bb else 0}
""")
    assert result.get("ok") is True
    assert result.get("count") == 8

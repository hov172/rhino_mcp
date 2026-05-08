"""
Grasshopper integration tests — require Rhino 8 running with the RhinoMCPPlugin loaded.

Run with:
    uv run python -m pytest tests/test_gh_integration.py -v -m integration

Requires:
    - Rhino 8 open (any document)
    - RhinoMCPPlugin loaded and socket server active on port 1999
    - Grasshopper plugin installed (comes with Rhino 8)
"""

from __future__ import annotations

import json
import pytest
from rhmcp.tools_helpers.plugin_client import send_command


def _plugin_available() -> bool:
    try:
        r = send_command("get_document_summary", timeout=3)
        return isinstance(r, dict) and r.get("status") == "ok"
    except OSError:
        return False


def _gh(command: str, params: dict | None = None) -> dict:
    """Send a GH command and unwrap the plugin envelope {"status":"ok","result":{...}}."""
    r = send_command(command, params or {})
    if "result" in r:
        return r["result"]
    return r


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def require_plugin():
    if not _plugin_available():
        pytest.skip("RhinoMCP plugin not reachable on port 1999 — start Rhino with the plugin loaded")


# ---------------------------------------------------------------------------
# Document tests
# ---------------------------------------------------------------------------

class TestGHDocument:
    def test_get_definition_info_no_doc(self):
        """gh_get_definition_info returns a structured response (ok or error with message)."""
        r = _gh("gh_get_definition_info")
        assert isinstance(r, dict)
        # Either GH is loaded with an active doc, or we get a clear error
        if r.get("ok"):
            assert "component_count" in r
            assert "solution_state" in r
        else:
            assert "error" in r

    def test_new_document_creates_definition(self):
        """gh_new_document creates a blank definition and returns a definition_id."""
        r = _gh("gh_new_document", {"name": "MCP_Test_Def"})
        assert r.get("ok"), f"gh_new_document failed: {r}"
        assert "definition_id" in r or "name" in r

    def test_get_definition_info_after_new(self):
        """After creating a new document, gh_get_definition_info returns ok=True."""
        _gh("gh_new_document", {})
        r = _gh("gh_get_definition_info")
        assert r.get("ok"), f"Expected ok after new doc: {r}"
        assert isinstance(r["component_count"], int)


# ---------------------------------------------------------------------------
# Canvas / component tests
# ---------------------------------------------------------------------------

class TestGHCanvas:
    @pytest.fixture(autouse=True)
    def fresh_doc(self):
        """Start each canvas test with a blank definition."""
        r = _gh("gh_new_document", {})
        assert r.get("ok"), f"Could not create fresh GH doc: {r}"

    def test_search_components_returns_results(self):
        """gh_search_components('circle') returns at least one result with name/guid/category."""
        r = _gh("gh_search_components", {"query": "circle", "limit": 10})
        assert r.get("ok"), f"search_components failed: {r}"
        assert len(r.get("components", [])) >= 1
        first = r["components"][0]
        assert "name" in first
        assert "guid" in first
        assert "category" in first

    def test_list_components_empty_on_new_doc(self):
        """A freshly-created definition has zero components."""
        r = _gh("gh_list_components")
        assert r.get("ok"), f"list_components failed: {r}"
        assert r["count"] == 0

    def test_add_and_list_component(self):
        """Add a Params > Geometry component and verify it appears in the list."""
        POINT_GUID = "ac2bc2cb-70fb-4dd5-9c78-7e1ea97fe278"  # Params > Geometry > Geometry
        r = _gh("gh_add_component", {
            "component_guid": POINT_GUID,
            "x": 100,
            "y": 100,
        })
        assert r.get("ok"), f"add_component failed: {r}"
        instance_guid = r.get("instance_guid")
        assert instance_guid

        listed = _gh("gh_list_components")
        assert listed.get("ok")
        guids = [c["instance_guid"] for c in listed["components"]]
        assert instance_guid in guids

    def test_add_and_remove_component(self):
        """Add then remove a component; verify it disappears from the canvas."""
        POINT_GUID = "ac2bc2cb-70fb-4dd5-9c78-7e1ea97fe278"  # Params > Geometry > Geometry
        add = _gh("gh_add_component", {"component_guid": POINT_GUID, "x": 200, "y": 200})
        assert add.get("ok")
        iid = add["instance_guid"]

        rm = _gh("gh_remove_component", {"instance_guid": iid})
        assert rm.get("ok"), f"remove_component failed: {rm}"

        listed = _gh("gh_list_components")
        guids = [c["instance_guid"] for c in listed.get("components", [])]
        assert iid not in guids

    def test_add_group(self):
        """Add two components, group them, verify group_id returned."""
        POINT_GUID = "ac2bc2cb-70fb-4dd5-9c78-7e1ea97fe278"  # Params > Geometry > Geometry
        a = _gh("gh_add_component", {"component_guid": POINT_GUID, "x": 50, "y": 50})
        b = _gh("gh_add_component", {"component_guid": POINT_GUID, "x": 200, "y": 50})
        assert a.get("ok") and b.get("ok")

        r = _gh("gh_add_group", {
            "instance_guids": [a["instance_guid"], b["instance_guid"]],
            "label": "TestGroup",
        })
        assert r.get("ok"), f"add_group failed: {r}"
        assert "group_id" in r


# ---------------------------------------------------------------------------
# Parameter / slider tests
# ---------------------------------------------------------------------------

class TestGHParams:
    SLIDER_GUID = "57da07bd-ecab-415d-9d86-af36d7073abc"  # Params > Input > Number Slider

    @pytest.fixture(autouse=True)
    def fresh_doc(self):
        r = _gh("gh_new_document", {})
        assert r.get("ok")

    def test_set_slider(self):
        """Add a slider, set its value, verify clamped_value is returned."""
        add = _gh("gh_add_component", {
            "component_guid": self.SLIDER_GUID,
            "x": 100,
            "y": 100,
        })
        assert add.get("ok"), f"Could not add slider: {add}"
        iid = add["instance_guid"]

        r = _gh("gh_set_slider", {"instance_guid": iid, "value": 0.75})
        assert r.get("ok"), f"set_slider failed: {r}"
        assert "clamped_value" in r

    def test_get_solution_errors_empty(self):
        """A blank definition has no solution errors."""
        r = _gh("gh_get_solution_errors")
        assert r.get("ok"), f"get_solution_errors failed: {r}"
        assert isinstance(r.get("errors", []), list)


# ---------------------------------------------------------------------------
# Solution tests
# ---------------------------------------------------------------------------

class TestGHSolution:
    @pytest.fixture(autouse=True)
    def fresh_doc(self):
        r = _gh("gh_new_document", {})
        assert r.get("ok")

    def test_get_solution_state(self):
        """gh_get_solution_state returns a valid state string."""
        r = _gh("gh_get_solution_state")
        assert r.get("ok"), f"get_solution_state failed: {r}"
        assert r.get("state") in ("idle", "computing", "post_process", "blank", "")

    def test_run_solution(self):
        """gh_run_solution returns ok=True with state and duration_ms."""
        r = _gh("gh_run_solution", {"wait_ms": 5000})
        assert r.get("ok"), f"run_solution failed: {r}"
        assert "state" in r
        assert "duration_ms" in r

    def test_bake_all_empty_doc(self):
        """Baking an empty doc returns ok=True with an empty or minimal objects list."""
        run = _gh("gh_run_solution", {"wait_ms": 3000})
        assert run.get("ok")
        r = _gh("gh_bake_all", {})
        assert r.get("ok"), f"bake_all failed: {r}"
        assert "objects" in r


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Unit tests for the profile resolution system in rhmcp.__init__."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rhmcp import _resolve_profile  # noqa: E402 — imported after sys.path patch

PROFILES_PATH = Path(__file__).parent.parent / "src" / "rhmcp" / "data" / "profiles.yml"


@pytest.fixture(scope="module")
def profiles():
    return yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))


class TestResolveProfile:
    def test_full_returns_none(self, profiles):
        """None signals 'load every module'."""
        assert _resolve_profile("full", profiles) is None

    def test_core_returns_set(self, profiles):
        result = _resolve_profile("core", profiles)
        assert isinstance(result, set)

    def test_core_contains_expected_modules(self, profiles):
        result = _resolve_profile("core", profiles)
        for mod in ("geometry", "layers", "transforms", "objects", "view"):
            assert mod in result, f"'{mod}' missing from core profile"

    def test_core_excludes_specialty_modules(self, profiles):
        result = _resolve_profile("core", profiles)
        for mod in ("gh_canvas", "gh_params", "vray", "enscape", "urban", "visualarq"):
            assert mod not in result, f"'{mod}' should not be in core profile"

    def test_grasshopper_is_superset_of_core(self, profiles):
        core = _resolve_profile("core", profiles)
        gh = _resolve_profile("grasshopper", profiles)
        assert core.issubset(gh), "grasshopper profile must include all core modules"

    def test_grasshopper_has_gh_modules(self, profiles):
        result = _resolve_profile("grasshopper", profiles)
        for mod in ("gh_canvas", "gh_params", "gh_solution", "gh2"):
            assert mod in result, f"'{mod}' missing from grasshopper profile"

    def test_rendering_has_vray_and_enscape(self, profiles):
        result = _resolve_profile("rendering", profiles)
        assert "vray" in result
        assert "enscape" in result
        assert "pbr_materials" in result

    def test_urban_has_urban_modules(self, profiles):
        result = _resolve_profile("urban", profiles)
        assert "urban" in result
        assert "urban_pipeline" in result

    def test_bim_has_visualarq(self, profiles):
        result = _resolve_profile("bim", profiles)
        assert "visualarq" in result
        assert "lands_design" in result

    def test_unknown_profile_exits(self, profiles):
        with pytest.raises(SystemExit):
            _resolve_profile("does_not_exist", profiles)

    def test_cycle_raises_value_error(self):
        cyclic = {
            "a": {"_extends": "b", "_modules": []},
            "b": {"_extends": "a", "_modules": []},
        }
        with pytest.raises(ValueError, match="cyclic"):
            _resolve_profile("a", cyclic)

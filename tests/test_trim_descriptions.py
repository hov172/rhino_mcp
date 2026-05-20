# tests/test_trim_descriptions.py
"""Unit tests for the description trimming logic in scripts/trim_descriptions.py."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

# Load the script as a module (it lives in scripts/, not a package)
_SCRIPT = Path(__file__).parent.parent / "scripts" / "trim_descriptions.py"


def _load_trim():
    spec = importlib.util.spec_from_file_location("trim_descriptions", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def trim_mod():
    return _load_trim()


class TestTrimFunction:
    def test_strips_parameters_section(self, trim_mod):
        doc = (
            "Create a sphere.\n\n"
            "Parameters\n"
            "----------\n"
            "radius:\n"
            "    The sphere radius.\n"
        )
        result = trim_mod.trim(doc)
        assert result == "Create a sphere."
        assert "Parameters" not in result

    def test_strips_args_section(self, trim_mod):
        doc = (
            "Do a thing.\n\n"
            "Args\n"
            "----\n"
            "x:\n"
            "    Some value.\n"
        )
        result = trim_mod.trim(doc)
        assert result == "Do a thing."

    def test_strips_notes_section(self, trim_mod):
        doc = (
            "Export geometry.\n\n"
            "Notes\n"
            "-----\n"
            "Requires Rhino 8.\n"
        )
        result = trim_mod.trim(doc)
        assert result == "Export geometry."

    def test_keeps_short_description_unchanged(self, trim_mod):
        doc = "Create a sphere."
        assert trim_mod.trim(doc) == "Create a sphere."

    def test_caps_at_200_chars(self, trim_mod):
        doc = "A very long summary " + "word " * 50
        result = trim_mod.trim(doc)
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")

    def test_strips_and_caps_combined(self, trim_mod):
        long_summary = "Word " * 60
        doc = long_summary + "\n\nParameters\n----------\nx:\n    val\n"
        result = trim_mod.trim(doc)
        assert len(result) <= 203
        assert "Parameters" not in result

    def test_no_section_no_cap_when_short(self, trim_mod):
        doc = "Short description without sections."
        assert trim_mod.trim(doc) == "Short description without sections."


class TestProcessFile:
    def test_rewrites_function_docstring(self, trim_mod):
        src = '''\
def foo():
    """Summary line.

    Parameters
    ----------
    x:
        The x param.
    """
    pass
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            before, after = trim_mod.process_file(tmp)
            result = tmp.read_text()
            assert "Parameters" not in result
            assert 'Summary line.' in result
            assert before > after
        finally:
            tmp.unlink()

    def test_does_not_touch_non_docstring_triple_quoted_strings(self, trim_mod):
        src = '''\
SCRIPT = """
some long script text
Parameters
----------
this should not be trimmed
"""

def foo():
    """Short."""
    pass
'''
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            tmp = Path(f.name)
        try:
            trim_mod.process_file(tmp)
            result = tmp.read_text()
            # SCRIPT must be untouched
            assert "this should not be trimmed" in result
        finally:
            tmp.unlink()

    def test_does_not_rewrite_file_when_nothing_changes(self, trim_mod):
        src = 'def foo():\n    """Already short."""\n    pass\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            tmp = Path(f.name)
        mtime_before = tmp.stat().st_mtime
        try:
            trim_mod.process_file(tmp)
            mtime_after = tmp.stat().st_mtime
            assert mtime_before == mtime_after
        finally:
            tmp.unlink()

# Token Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce rhino-mcp MCP tool schema token footprint from ~62k to ~28k tokens via description trimming, a profile system, and a trim script.

**Architecture:** (1) A one-time script rewrites tool docstrings in-place using AST to locate function docstrings and strip everything from the first `Parameters`/`Args`/`Notes` section. (2) A `profiles.yml` data file defines named module sets. (3) `__init__.py` gains a `--profile` CLI flag that filters which tool modules are loaded at startup.

**Tech Stack:** Python stdlib (`ast`, `re`, `argparse`), PyYAML (already a dependency), pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `scripts/trim_descriptions.py` | Create | One-time script: AST-targeted docstring trimmer |
| `tests/test_trim_descriptions.py` | Create | Unit tests for trim logic |
| `src/rhmcp/data/profiles.yml` | Create | Named profile → module list definitions |
| `src/rhmcp/__init__.py` | Modify | Add `--profile` arg + module filter + `_resolve_profile()` |
| `tests/test_profiles.py` | Create | Unit tests for profile resolver |

---

## Task 1: Write failing tests for the trim logic

**Files:**
- Create: `tests/test_trim_descriptions.py`

- [ ] **Step 1: Create the test file**

```python
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
```

- [ ] **Step 2: Run the tests — they must fail (script doesn't exist yet)**

```bash
cd /Users/helpdesk/Developer/GitHub/rhino_mcp
uv run pytest tests/test_trim_descriptions.py -v 2>&1 | head -20
```

Expected: `ERROR` — `FileNotFoundError` or `ModuleNotFoundError` because `scripts/trim_descriptions.py` doesn't exist.

---

## Task 2: Implement scripts/trim_descriptions.py

**Files:**
- Create: `scripts/trim_descriptions.py`

- [ ] **Step 1: Create the script**

```python
#!/usr/bin/env python3
"""
Trim verbose docstring sections from MCP tool functions.

Run once to strip Parameters/Args/Returns/Notes/Examples/Raises sections
from function docstrings in src/rhmcp/tools/*.py. Only actual function
docstrings are touched (identified via AST); module-level constants and
multi-line strings used as script templates are left alone.

Usage:
    python scripts/trim_descriptions.py                 # default: src/rhmcp/tools/
    python scripts/trim_descriptions.py path/to/tools/  # custom directory
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(
    r"\n[ \t]*(?:Parameters|Args|Returns|Notes|Examples|Raises)[ \t]*\n[ \t]*[-=]{3,}",
    re.MULTILINE,
)
MAX_DESC = 200


def trim(doc: str) -> str:
    """Return only the first paragraph of *doc*, capped at MAX_DESC chars."""
    m = SECTION_RE.search(doc)
    text = doc[: m.start()].strip() if m else doc.strip()
    if len(text) > MAX_DESC:
        text = text[:MAX_DESC].rsplit(None, 1)[0] + "..."
    return text


def process_file(path: Path) -> tuple[int, int]:
    """Trim all function docstrings in *path*. Returns (before_chars, after_chars)."""
    source = path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, 0

    # Build byte-offset lookup: line index (0-based) → start offset
    lines = source.splitlines(keepends=True)
    line_offsets = [0]
    for line in lines:
        line_offsets.append(line_offsets[-1] + len(line))

    # Collect all function docstring AST constant nodes
    docstring_nodes: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                docstring_nodes.append(node.body[0].value)

    if not docstring_nodes:
        return 0, 0

    before_total = after_total = 0
    replacements: list[tuple[int, int, str]] = []

    for const in docstring_nodes:
        value: str = const.value
        before_total += len(value)
        trimmed = trim(value)
        after_total += len(trimmed)

        if trimmed == value.strip():
            continue  # no change needed

        start = line_offsets[const.lineno - 1] + const.col_offset
        end = line_offsets[const.end_lineno - 1] + const.end_col_offset

        raw_token = source[start:end]
        quote = '"""' if raw_token.startswith('"""') else "'''"
        replacements.append((start, end, f"{quote}{trimmed}{quote}"))

    if not replacements:
        return before_total, after_total

    # Apply in reverse order so earlier offsets stay valid
    new_source = source
    for start, end, replacement in sorted(replacements, key=lambda t: t[0], reverse=True):
        new_source = new_source[:start] + replacement + new_source[end:]

    path.write_text(new_source, encoding="utf-8")
    return before_total, after_total


def main(tools_dir: Path) -> None:
    total_before = total_after = files_changed = 0

    for path in sorted(tools_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        before, after = process_file(path)
        total_before += before
        total_after += after
        if before != after:
            files_changed += 1
            pct = 100 * (before - after) / before if before else 0
            print(f"  {path.name}: {before:,} → {after:,} chars  ({pct:.0f}% saved)")

    saved = total_before - total_after
    pct = 100 * saved / total_before if total_before else 0
    print(f"\nTotal description chars: {total_before:,} → {total_after:,}")
    print(f"Saved: {saved:,} chars  (~{saved // 4:,} tokens,  {pct:.0f}%)")
    print(f"Files changed: {files_changed}")


if __name__ == "__main__":
    tools_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).parent.parent / "src" / "rhmcp" / "tools"
    )
    main(tools_dir)
```

- [ ] **Step 2: Run the tests**

```bash
uv run pytest tests/test_trim_descriptions.py -v
```

Expected output:
```
tests/test_trim_descriptions.py::TestTrimFunction::test_strips_parameters_section PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_strips_args_section PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_strips_notes_section PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_keeps_short_description_unchanged PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_caps_at_200_chars PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_strips_and_caps_combined PASSED
tests/test_trim_descriptions.py::TestTrimFunction::test_no_section_no_cap_when_short PASSED
tests/test_trim_descriptions.py::TestProcessFile::test_rewrites_function_docstring PASSED
tests/test_trim_descriptions.py::TestProcessFile::test_does_not_touch_non_docstring_triple_quoted_strings PASSED
tests/test_trim_descriptions.py::TestProcessFile::test_does_not_rewrite_file_when_nothing_changes PASSED
10 passed
```

- [ ] **Step 3: Commit**

```bash
git add scripts/trim_descriptions.py tests/test_trim_descriptions.py
git commit -m "feat(scripts): add trim_descriptions.py with tests"
```

---

## Task 3: Run trim script on the codebase

**Files:**
- Modify: `src/rhmcp/tools/*.py` (all 57 tool files — via script)

- [ ] **Step 1: Run the trim script**

```bash
uv run python scripts/trim_descriptions.py
```

Expected: output listing files changed and token savings (~40–46% of description chars).

- [ ] **Step 2: Run the full test suite to confirm nothing broke**

```bash
uv run pytest tests/test_tools_unit.py -v
```

Expected: all tests that passed before still pass. The unit tests don't check description text, only parameter validation logic.

- [ ] **Step 3: Spot-check two files manually**

```bash
grep -A3 'def create_rhino_geometry' src/rhmcp/tools/geometry.py | head -6
grep -A3 'def create_pbr_material' src/rhmcp/tools/pbr_materials.py | head -6
```

Expected: docstrings now show only a short summary line with no `Parameters` section.

- [ ] **Step 4: Measure actual token reduction**

```bash
uv run python -c "
import json, sys, pkgutil, importlib
sys.path.insert(0, 'src')
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('rhino-mcp')
tools_pkg = importlib.import_module('rhmcp.tools')
for _, modname, _ in pkgutil.iter_modules(tools_pkg.__path__):
    mod = importlib.import_module(f'rhmcp.tools.{modname}')
    if hasattr(mod, 'register'):
        mod.register(mcp)
tools = mcp._tool_manager._tools
total = sum(len(json.dumps({'name': n, 'description': t.description or '', 'inputSchema': t.parameters or {}})) for n, t in tools.items())
print(f'Post-trim full schema: {total:,} chars (~{total//4:,} tokens)')
" 2>&1 | grep -v Warning
```

Expected: ~185,000 chars / ~46,000 tokens (down from ~248k / ~62k).

- [ ] **Step 5: Commit**

```bash
git add src/rhmcp/tools/
git commit -m "refactor(tools): trim verbose Parameters sections from tool docstrings (~9k tokens saved)"
```

---

## Task 4: Create profiles.yml

**Files:**
- Create: `src/rhmcp/data/profiles.yml`

- [ ] **Step 1: Create the profiles file**

```yaml
# src/rhmcp/data/profiles.yml
#
# Named tool profiles for rhino-mcp.
# Select with: --profile <name>  or  RHMCP_PROFILE=<name>
#
# Format:
#   <name>: [list of module names]           # flat list
#   <name>:                                  # dict with inheritance
#     _extends: <base-profile>
#     _modules: [additional modules]
#   full: null                               # null = load everything

core:
  - advanced_geometry
  - analysis
  - annotations
  - blocks
  - boolean_operations
  - curve_operations
  - docs
  - document
  - documents
  - export_cad
  - export_images
  - export_native
  - export_print
  - export_visual
  - geometry
  - geometry_validation
  - groups
  - layers
  - materials
  - mesh_ops
  - objects
  - plugin_socket
  - plugins
  - python
  - reference_compat
  - session
  - slots
  - surface_ops
  - transforms
  - undo
  - userdata
  - view

grasshopper:
  _extends: core
  _modules:
    - gh2
    - gh_anemone
    - gh_canvas
    - gh_document
    - gh_human_elefront
    - gh_intelligence
    - gh_kangaroo
    - gh_ladybug
    - gh_lunchbox
    - gh_params
    - gh_pufferfish
    - gh_solution
    - gh_weaverbird

rendering:
  _extends: core
  _modules:
    - asset_libraries
    - enscape
    - pbr_materials
    - vray

urban:
  _extends: core
  _modules:
    - ai_generation
    - urban
    - urban_design_language
    - urban_pipeline
    - urban_prompt
    - urban_renders
    - urban_report

bim:
  _extends: core
  _modules:
    - lands_design
    - visualarq

full: null
```

- [ ] **Step 2: Commit**

```bash
git add src/rhmcp/data/profiles.yml
git commit -m "feat(data): add profiles.yml with core/grasshopper/rendering/urban/bim/full profiles"
```

---

## Task 5: Write failing tests for the profile resolver

**Files:**
- Create: `tests/test_profiles.py`

- [ ] **Step 1: Create the test file**

```python
# tests/test_profiles.py
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
```

- [ ] **Step 2: Run — must fail (function not defined yet)**

```bash
uv run pytest tests/test_profiles.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name '_resolve_profile' from 'rhmcp'`

---

## Task 6: Add `_resolve_profile` and `--profile` to `__init__.py`

**Files:**
- Modify: `src/rhmcp/__init__.py`

- [ ] **Step 1: Add `_resolve_profile` as a module-level function**

Insert this function at module level in `__init__.py`, after the `_TRANSPORTS` line (around line 24):

```python
def _resolve_profile(
    name: str,
    profiles: dict,
    _depth: int = 0,
) -> set[str] | None:
    """
    Resolve a profile name to a set of module names, or None for 'load all'.

    Raises SystemExit for unknown profiles; ValueError for cycles.
    """
    if _depth > 3:
        raise ValueError(
            f"Profile inheritance too deep or cyclic near {name!r}"
        )
    if name not in profiles:
        valid = ", ".join(sorted(profiles))
        print(
            f"rhino-mcp: unknown profile {name!r}. Valid: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)
    profile = profiles[name]
    if profile is None:
        return None
    if isinstance(profile, list):
        return set(profile)
    if isinstance(profile, dict):
        base_name = profile.get("_extends")
        extra: list[str] = profile.get("_modules", [])
        base: set[str] = (
            _resolve_profile(base_name, profiles, _depth + 1)
            if base_name
            else set()
        )
        if base is None:  # extends 'full' → full
            return None
        return base | set(extra)
    raise ValueError(f"Invalid profile definition for {name!r}")
```

- [ ] **Step 2: Add `--profile` argument to the parser**

In `main()`, after the existing `--port` argument (around line 38), add:

```python
    parser.add_argument(
        "--profile",
        default=os.environ.get("RHMCP_PROFILE", "full"),
        metavar="PROFILE",
        help=(
            "Tool profile to load: core, grasshopper, rendering, urban, bim, full. "
            "Env: RHMCP_PROFILE. Default: full."
        ),
    )
```

- [ ] **Step 3: Load profiles.yml and resolve the active profile**

In `main()`, after the `prompts.yml` block (after line 43), add:

```python
    with open(os.path.join(data_dir, "profiles.yml"), encoding="utf-8") as fh:
        profiles_data = yaml.safe_load(fh)

    active_modules = _resolve_profile(args.profile, profiles_data)
```

- [ ] **Step 4: Filter module loading**

Replace the existing tool-loading loop (lines 82–87):

```python
    import rhmcp.tools as tools_pkg

    for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
        if modname.startswith("_"):
            continue
        mod = importlib.import_module("rhmcp.tools.{:s}".format(modname))
        if hasattr(mod, "register"):
            mod.register(mcp)
```

With:

```python
    import rhmcp.tools as tools_pkg

    _loaded = []
    for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
        if modname.startswith("_"):
            continue
        if active_modules is not None and modname not in active_modules:
            continue
        mod = importlib.import_module("rhmcp.tools.{:s}".format(modname))
        if hasattr(mod, "register"):
            mod.register(mcp)
            _loaded.append(modname)

    if args.profile != "full":
        print(
            f"Rhino MCP: profile '{args.profile}' — {len(_loaded)} modules loaded",
            file=sys.stderr,
        )
```

- [ ] **Step 5: Run the profile tests**

```bash
uv run pytest tests/test_profiles.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 6: Run the full test suite**

```bash
uv run pytest tests/test_tools_unit.py tests/test_trim_descriptions.py tests/test_profiles.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/rhmcp/__init__.py
git commit -m "feat(server): add --profile flag and RHMCP_PROFILE env var for token-efficient tool loading"
```

---

## Task 7: Final verification

- [ ] **Step 1: Verify core profile token count**

```bash
uv run python -c "
import json, sys, pkgutil, importlib, os, yaml
sys.path.insert(0, 'src')
from mcp.server.fastmcp import FastMCP
from rhmcp import _resolve_profile

profiles = yaml.safe_load(open('src/rhmcp/data/profiles.yml'))
mcp = FastMCP('rhino-mcp')
tools_pkg = importlib.import_module('rhmcp.tools')
active = _resolve_profile('core', profiles)
for _, modname, _ in pkgutil.iter_modules(tools_pkg.__path__):
    if active is None or modname in active:
        mod = importlib.import_module(f'rhmcp.tools.{modname}')
        if hasattr(mod, 'register'):
            mod.register(mcp)

tools = mcp._tool_manager._tools
total = sum(len(json.dumps({'name': n, 'description': t.description or '', 'inputSchema': t.parameters or {}})) for n, t in tools.items())
print(f'core profile post-trim: {len(tools)} tools, {total:,} chars (~{total//4:,} tokens)')
" 2>&1 | grep -v Warning
```

Expected: ~194 tools, ~110,000 chars, ~27,000 tokens (down from ~248k / ~62k for full/pre-trim).

- [ ] **Step 2: Verify full profile still works**

```bash
uv run python -c "
import json, sys, pkgutil, importlib
sys.path.insert(0, 'src')
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('rhino-mcp')
tools_pkg = importlib.import_module('rhmcp.tools')
for _, modname, _ in pkgutil.iter_modules(tools_pkg.__path__):
    mod = importlib.import_module(f'rhmcp.tools.{modname}')
    if hasattr(mod, 'register'):
        mod.register(mcp)
print(f'full profile: {len(mcp._tool_manager._tools)} tools')
" 2>&1 | grep -v Warning
```

Expected: 358 tools (count unchanged — only descriptions were trimmed, not tools removed).

- [ ] **Step 3: Verify `--profile unknown` exits with error**

```bash
uv run python -m rhmcp --profile nonexistent 2>&1 | head -3
```

Expected: `rhino-mcp: unknown profile 'nonexistent'. Valid: bim, core, full, grasshopper, rendering, urban`

- [ ] **Step 4: Run all tests one final time**

```bash
uv run pytest tests/test_tools_unit.py tests/test_trim_descriptions.py tests/test_profiles.py -v --tb=short
```

Expected: all tests pass, zero failures.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify token reduction complete — core profile ~27k tokens (was ~62k)"
```

---

## Summary

| Change | Tokens saved | Method |
|--------|-------------|--------|
| Description trim | ~9,000 | One-time script, permanent source change |
| `core` profile | ~19,000 additional | Runtime filter, 164 tools skipped |
| **Combined (core + trim)** | **~35,000 (~55%)** | Both active |

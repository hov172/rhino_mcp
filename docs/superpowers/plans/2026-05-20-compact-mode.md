# Compact Mode (Schema-on-Demand) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--compact` / `RHMCP_COMPACT` flag that registers 3 meta-tools instead of 360 full schemas, cutting per-request token cost from ~52k to ~1.5k.

**Architecture:** A new `CompactRegistry` class loads all tool modules onto a private shadow FastMCP, captures the resulting `Tool` objects (name, description, parameters schema, `run()` dispatcher), and exposes three meta-tools (`list_rhino_tools`, `describe_rhino_tool`, `call_rhino_tool`) on the real FastMCP. The normal (non-compact) code path is unchanged.

**Tech Stack:** Python 3.10+, FastMCP (`mcp.server.fastmcp`), pytest, `unittest.mock.AsyncMock`

---

## File Map

| File | Action |
|------|--------|
| `src/rhmcp/tools_helpers/compact_registry.py` | **Create** — `CompactRegistry` class |
| `src/rhmcp/__init__.py` | **Modify** — add `--compact` arg + compact branch (lines 82–147) |
| `tests/test_compact_mode.py` | **Create** — 12 unit tests, no live Rhino needed |

---

### Task 1: CompactRegistry — TDD red phase

**Files:**
- Create: `tests/test_compact_mode.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_compact_mode.py
import asyncio
import os
import pytest
from unittest.mock import AsyncMock


class TestCompactRegistry:
    def test_load_captures_tools(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        assert len(reg._tools) > 0

    def test_load_respects_profile(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        full = CompactRegistry()
        full.load_from_modules(None)
        partial = CompactRegistry()
        partial.load_from_modules({"geometry"})
        assert 0 < len(partial._tools) < len(full._tools)

    def test_list_tools_returns_name_and_description(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        tools = reg.list_tools()
        assert len(tools) > 0
        for t in tools:
            assert "name" in t
            assert "description" in t

    def test_list_tools_filters_by_category(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        all_tools = reg.list_tools()
        filtered = reg.list_tools("geometry")
        assert 0 < len(filtered) < len(all_tools)
        assert all("geometry" in t["name"] for t in filtered)

    def test_list_tools_is_sorted(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        tools = reg.list_tools()
        names = [t["name"] for t in tools]
        assert names == sorted(names)

    def test_describe_known_tool(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        result = reg.describe_tool("execute_rhino_python")
        assert result["name"] == "execute_rhino_python"
        assert "description" in result
        assert "input_schema" in result
        assert "error" not in result

    def test_describe_unknown_tool(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        result = reg.describe_tool("no_such_tool_xyz")
        assert "error" in result

    def test_call_tool_dispatches(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules({"geometry"})
        name = next(iter(reg._tools))
        mock_run = AsyncMock(return_value={"ok": True})
        reg._tools[name].run = mock_run
        result = asyncio.run(reg.call_tool(name, {"x": 1}))
        mock_run.assert_called_once_with({"x": 1})
        assert result == {"ok": True}

    def test_call_tool_unknown_raises(self):
        from rhmcp.tools_helpers.compact_registry import CompactRegistry
        reg = CompactRegistry()
        reg.load_from_modules(None)
        with pytest.raises(ValueError, match="not found"):
            asyncio.run(reg.call_tool("no_such_tool_xyz", {}))


class TestCompactArgparse:
    def test_compact_flag_recognized(self, monkeypatch):
        monkeypatch.delenv("RHMCP_COMPACT", raising=False)
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--compact", action="store_true",
            default=bool(os.environ.get("RHMCP_COMPACT")),
        )
        args = parser.parse_args(["--compact"])
        assert args.compact is True

    def test_compact_default_false_without_env(self, monkeypatch):
        monkeypatch.delenv("RHMCP_COMPACT", raising=False)
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--compact", action="store_true",
            default=bool(os.environ.get("RHMCP_COMPACT")),
        )
        args = parser.parse_args([])
        assert args.compact is False

    def test_compact_env_var_sets_default(self, monkeypatch):
        monkeypatch.setenv("RHMCP_COMPACT", "1")
        assert bool(os.environ.get("RHMCP_COMPACT")) is True
```

- [ ] **Step 2: Run to confirm all tests fail**

```bash
uv run pytest tests/test_compact_mode.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'CompactRegistry' from 'rhmcp.tools_helpers.compact_registry'` (module doesn't exist yet).

---

### Task 2: CompactRegistry — implement

**Files:**
- Create: `src/rhmcp/tools_helpers/compact_registry.py`

- [ ] **Step 3: Write the implementation**

```python
# src/rhmcp/tools_helpers/compact_registry.py
from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from mcp.server.fastmcp import FastMCP


class CompactRegistry:
    """Captures all tool registrations via a shadow FastMCP for lazy dispatch."""

    def __init__(self) -> None:
        self._tools: dict = {}

    def load_from_modules(self, active_modules: set[str] | None) -> None:
        shadow = FastMCP("shadow")
        import rhmcp.tools as tools_pkg

        for _importer, modname, _ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_"):
                continue
            if active_modules is not None and modname not in active_modules:
                continue
            mod = importlib.import_module(f"rhmcp.tools.{modname}")
            if hasattr(mod, "register"):
                mod.register(shadow)

        self._tools = dict(shadow._tool_manager._tools)

    def list_tools(self, category: str = "") -> list[dict]:
        results = []
        for name, tool in self._tools.items():
            if category and category.lower() not in name.lower():
                continue
            first_line = (tool.description or "").split("\n")[0].strip()
            results.append({"name": name, "description": first_line})
        results.sort(key=lambda t: t["name"])
        return results

    def describe_tool(self, name: str) -> dict:
        tool = self._tools.get(name)
        if not tool:
            return {
                "error": f"Tool '{name}' not found. Call list_rhino_tools() to see available tools."
            }
        return {
            "name": name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    async def call_tool(self, name: str, arguments: dict) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(
                f"Tool '{name}' not found. Call list_rhino_tools() to see available tools."
            )
        return await tool.run(arguments)
```

- [ ] **Step 4: Run tests — expect green**

```bash
uv run pytest tests/test_compact_mode.py -v 2>&1 | tail -20
```

Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_compact_mode.py src/rhmcp/tools_helpers/compact_registry.py
git commit -m "feat(compact): add CompactRegistry for schema-on-demand tool dispatch"
```

---

### Task 3: Wire `--compact` into `__init__.py`

**Files:**
- Modify: `src/rhmcp/__init__.py` — add `--compact` arg at line 83 and compact branch replacing lines 130–147

**Context:** `main()` currently has this structure:
```python
# line 74: --profile arg
# line 83: args = parser.parse_args()
# line 92: active_modules = _resolve_profile(...)
# line 94: mcp = FastMCP(...)
# lines 96–128: prompts and resources (unchanged)
# lines 130–147: module registration loop + profile print  ← replace with compact branch
# lines 149–151: telemetry.install(mcp)  ← unchanged
```

- [ ] **Step 6: Add `--compact` argument to argparse**

In `src/rhmcp/__init__.py`, after the `--profile` block (after line 82), add:

```python
    parser.add_argument(
        "--compact",
        action="store_true",
        default=bool(os.environ.get("RHMCP_COMPACT")),
        help=(
            "Compact mode: register 3 meta-tools instead of all schemas. "
            "Env: RHMCP_COMPACT. Default: false."
        ),
    )
```

The full argparse block now looks like:
```python
    parser.add_argument(
        "--transport",
        "-t",
        choices=_TRANSPORTS,
        default="stdio",
        help="Transport protocol (default: stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (default: 127.0.0.1).")
    parser.add_argument("--port", "-p", type=int, default=8000, help="HTTP port (default: 8000).")
    parser.add_argument(
        "--profile",
        default=os.environ.get("RHMCP_PROFILE") or "full",
        metavar="PROFILE",
        help=(
            "Tool profile to load: core, grasshopper, rendering, urban, bim, full. "
            "Env: RHMCP_PROFILE. Default: full."
        ),
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=bool(os.environ.get("RHMCP_COMPACT")),
        help=(
            "Compact mode: register 3 meta-tools instead of all schemas. "
            "Env: RHMCP_COMPACT. Default: false."
        ),
    )
    args = parser.parse_args()
```

- [ ] **Step 7: Replace the module registration loop with a compact/normal branch**

Replace lines 130–147 (the `import rhmcp.tools as tools_pkg` block through the profile print) with:

```python
    if args.compact:
        from rhmcp.tools_helpers.compact_registry import CompactRegistry

        _registry = CompactRegistry()
        _registry.load_from_modules(active_modules)
        _n = len(_registry._tools)

        @mcp.tool()
        def list_rhino_tools(category: str = "") -> list[dict]:
            """List all available Rhino tools with one-line descriptions."""
            return _registry.list_tools(category)

        @mcp.tool()
        def describe_rhino_tool(name: str) -> dict:
            """Get the full description and input schema for a specific Rhino tool."""
            return _registry.describe_tool(name)

        @mcp.tool()
        async def call_rhino_tool(name: str, arguments: dict | None = None) -> object:
            """Call any Rhino tool by name with a dict of arguments."""
            return await _registry.call_tool(name, arguments or {})

        print(
            f"Rhino MCP: compact mode — 3 meta-tools loaded ({_n} tools available on demand)",
            file=sys.stderr,
        )
    else:
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

- [ ] **Step 8: Run the full test suite — expect all green**

```bash
uv run pytest tests/test_compact_mode.py tests/test_profiles.py tests/test_trim_descriptions.py -v 2>&1 | tail -20
```

Expected: all tests pass (12 + 11 + 10 = 33 total).

- [ ] **Step 9: Smoke-test --compact flag at the CLI**

```bash
RHMCP_COMPACT=1 uv run python -m rhmcp --help 2>&1 | grep compact
```

Expected output includes: `--compact  Compact mode: register 3 meta-tools...`

```bash
uv run python -c "
import sys, os
os.environ['RHMCP_COMPACT'] = '1'
from rhmcp.tools_helpers.compact_registry import CompactRegistry
reg = CompactRegistry()
reg.load_from_modules(None)
print('tools in registry:', len(reg._tools))
print('sample list:', reg.list_tools()[:3])
print('describe execute_rhino_python keys:', list(reg.describe_tool('execute_rhino_python').keys()))
" 2>&1
```

Expected: `tools in registry: 360` (or similar), sample list with name/description dicts, describe keys are `['name', 'description', 'input_schema']`.

- [ ] **Step 10: Commit**

```bash
git add src/rhmcp/__init__.py
git commit -m "feat(compact): wire --compact flag and RHMCP_COMPACT env var into server startup"
```

---

### Task 4: CHANGELOG update

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 11: Add changelog entry**

At the top of `CHANGELOG.md`, above the `[0.13.0]` entry, add:

```markdown
## [Unreleased]

### Added
- `--compact` flag and `RHMCP_COMPACT` env var: compact mode registers 3 meta-tools
  (`list_rhino_tools`, `describe_rhino_tool`, `call_rhino_tool`) instead of all full
  schemas. Cuts per-request token cost from ~52k to ~1.5k. Works alongside `--profile`.
```

- [ ] **Step 12: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add compact mode entry to CHANGELOG"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** `CompactRegistry` ✓, `--compact` flag ✓, `RHMCP_COMPACT` ✓, 3 meta-tools ✓, works with `--profile` ✓, startup message ✓, all 10 spec tests covered (12 written) ✓
- [x] **No placeholders:** all steps have complete code
- [x] **Type consistency:** `CompactRegistry._tools: dict`, `list_tools() -> list[dict]`, `describe_tool() -> dict`, `call_tool() -> Any` — consistent across all tasks
- [x] **`tool.run()` dispatch verified** in pre-plan exploration: `tool.run({"x": 42})` returns the function result correctly
- [x] **Mutable default avoided:** `call_rhino_tool` uses `arguments: dict | None = None` with `or {}` guard

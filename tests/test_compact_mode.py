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
            "--compact", action=argparse.BooleanOptionalAction,
            default=os.environ.get("RHMCP_COMPACT", "1") not in ("0", "false", "no"),
        )
        args = parser.parse_args(["--no-compact"])
        assert args.compact is False

    def test_compact_default_true_without_env(self, monkeypatch):
        monkeypatch.delenv("RHMCP_COMPACT", raising=False)
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--compact", action=argparse.BooleanOptionalAction,
            default=os.environ.get("RHMCP_COMPACT", "1") not in ("0", "false", "no"),
        )
        args = parser.parse_args([])
        assert args.compact is True

    def test_compact_env_var_zero_disables(self, monkeypatch):
        monkeypatch.setenv("RHMCP_COMPACT", "0")
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--compact", action=argparse.BooleanOptionalAction,
            default=os.environ.get("RHMCP_COMPACT", "1") not in ("0", "false", "no"),
        )
        args = parser.parse_args([])
        assert args.compact is False

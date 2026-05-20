# tests/test_security_gates.py
"""Unit tests for execution safety gates and remote host guard."""
import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# check_execution_gate
# ---------------------------------------------------------------------------

class TestCheckExecutionGate:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ENABLE_RHINOSCRIPT", raising=False)
        from rhmcp.tools_helpers.security import check_execution_gate
        assert check_execution_gate("RHINO_MCP_ENABLE_RHINOSCRIPT", "tool") is None

    def test_enabled_explicitly(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RHINOSCRIPT", "1")
        from rhmcp.tools_helpers.security import check_execution_gate
        assert check_execution_gate("RHINO_MCP_ENABLE_RHINOSCRIPT", "tool") is None

    def test_disabled_by_zero(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RHINOSCRIPT", "0")
        from rhmcp.tools_helpers.security import check_execution_gate
        result = check_execution_gate("RHINO_MCP_ENABLE_RHINOSCRIPT", "my_tool")
        assert result is not None
        assert result["ok"] is False
        assert result["error_code"] == "TOOL_DISABLED"
        assert "my_tool" in result["error"]
        assert "RHINO_MCP_ENABLE_RHINOSCRIPT" in result["error"]

    def test_disabled_by_false(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_CSHARP", "false")
        from rhmcp.tools_helpers.security import check_execution_gate
        assert check_execution_gate("RHINO_MCP_ENABLE_CSHARP", "t") is not None

    def test_disabled_by_no(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RUN_COMMAND", "no")
        from rhmcp.tools_helpers.security import check_execution_gate
        assert check_execution_gate("RHINO_MCP_ENABLE_RUN_COMMAND", "t") is not None

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RHINOSCRIPT", "FALSE")
        from rhmcp.tools_helpers.security import check_execution_gate
        assert check_execution_gate("RHINO_MCP_ENABLE_RHINOSCRIPT", "t") is not None


# ---------------------------------------------------------------------------
# check_remote_allowed
# ---------------------------------------------------------------------------

class TestCheckRemoteAllowed:
    def test_loopback_127_always_allowed(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.security import check_remote_allowed
        check_remote_allowed("127.0.0.1")  # must not raise

    def test_localhost_always_allowed(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.security import check_remote_allowed
        check_remote_allowed("localhost")

    def test_ipv6_loopback_always_allowed(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.security import check_remote_allowed
        check_remote_allowed("::1")

    def test_remote_blocked_by_default(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.security import check_remote_allowed
        with pytest.raises(PermissionError, match="RHINO_MCP_ALLOW_REMOTE"):
            check_remote_allowed("host.docker.internal")

    def test_remote_blocked_when_zero(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ALLOW_REMOTE", "0")
        from rhmcp.tools_helpers.security import check_remote_allowed
        with pytest.raises(PermissionError):
            check_remote_allowed("192.168.1.100")

    def test_remote_allowed_when_set(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ALLOW_REMOTE", "1")
        from rhmcp.tools_helpers.security import check_remote_allowed
        check_remote_allowed("host.docker.internal")  # must not raise

    def test_remote_allowed_true_string(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ALLOW_REMOTE", "true")
        from rhmcp.tools_helpers.security import check_remote_allowed
        check_remote_allowed("10.0.0.5")  # must not raise


# ---------------------------------------------------------------------------
# plugin_client.connection_settings integrates the remote guard
# ---------------------------------------------------------------------------

class TestConnectionSettingsRemoteGuard:
    def test_loopback_host_passes(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        monkeypatch.delenv("RHINO_MCP_HOST", raising=False)
        from rhmcp.tools_helpers.plugin_client import connection_settings
        host, port, _ = connection_settings(host="127.0.0.1")
        assert host == "127.0.0.1"

    def test_remote_host_blocked_by_default(self, monkeypatch):
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.plugin_client import connection_settings
        with pytest.raises(PermissionError):
            connection_settings(host="192.168.1.50")

    def test_remote_host_env_var_blocked(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_HOST", "10.0.0.1")
        monkeypatch.delenv("RHINO_MCP_ALLOW_REMOTE", raising=False)
        from rhmcp.tools_helpers.plugin_client import connection_settings
        with pytest.raises(PermissionError):
            connection_settings()

    def test_remote_host_allowed_with_flag(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ALLOW_REMOTE", "1")
        from rhmcp.tools_helpers.plugin_client import connection_settings
        host, _, _ = connection_settings(host="host.docker.internal")
        assert host == "host.docker.internal"


# ---------------------------------------------------------------------------
# execute_rhino_python gate
# ---------------------------------------------------------------------------

class TestExecuteRhinoPythonGate:
    def _register(self):
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        import rhmcp.tools.python as m
        m.register(mcp)
        return {t.name: t for t in mcp._tool_manager.list_tools()}

    def test_gate_off_returns_error(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RHINOSCRIPT", "0")
        tools = self._register()
        import asyncio
        result = asyncio.run(tools["execute_rhino_python"].run({"code": "x=1"}))
        assert result["ok"] is False
        assert result["error_code"] == "TOOL_DISABLED"

    def test_gate_on_proceeds(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RHINOSCRIPT", "1")
        tools = self._register()
        import asyncio
        with patch("rhmcp.tools_helpers.backend.execute_python", return_value={"ok": True}):
            result = asyncio.run(tools["execute_rhino_python"].run({"code": "x=1"}))
        assert result.get("ok") is True or "api_warning" in result


# ---------------------------------------------------------------------------
# execute_rhino_csharp gate
# ---------------------------------------------------------------------------

class TestExecuteRhinoCsharpGate:
    def _register(self):
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        import rhmcp.tools.python as m
        m.register(mcp)
        return {t.name: t for t in mcp._tool_manager.list_tools()}

    def test_gate_off_returns_error(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_CSHARP", "0")
        tools = self._register()
        import asyncio
        result = asyncio.run(tools["execute_rhino_csharp"].run({"code": "// cs"}))
        assert result["ok"] is False
        assert result["error_code"] == "TOOL_DISABLED"

    def test_gate_on_proceeds(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_CSHARP", "1")
        tools = self._register()
        import asyncio
        with patch("rhmcp.tools_helpers.backend.execute_script", return_value={"ok": True}):
            result = asyncio.run(tools["execute_rhino_csharp"].run({"code": "// cs"}))
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# run_rhino_command gate
# ---------------------------------------------------------------------------

class TestRunRhinoCommandGate:
    def _register(self):
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        import rhmcp.tools.session as m
        m.register(mcp)
        return {t.name: t for t in mcp._tool_manager.list_tools()}

    def test_gate_off_returns_error(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RUN_COMMAND", "0")
        tools = self._register()
        import asyncio
        result = asyncio.run(tools["run_rhino_command"].run({"command": "_Circle"}))
        assert result["ok"] is False
        assert result["error_code"] == "TOOL_DISABLED"

    def test_gate_on_proceeds(self, monkeypatch):
        monkeypatch.setenv("RHINO_MCP_ENABLE_RUN_COMMAND", "1")
        tools = self._register()
        import asyncio
        with patch("rhmcp.tools_helpers.backend.run_command", return_value={"ok": True}):
            result = asyncio.run(tools["run_rhino_command"].run({"command": "_Circle"}))
        assert result["ok"] is True

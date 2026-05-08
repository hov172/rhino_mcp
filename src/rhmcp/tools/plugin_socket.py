"""
Compatibility bridge for the rhinomcp plug-in socket protocol.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Send RhinoMCP Plugin Command", destructiveHint=True))
    def send_rhinomcp_plugin_command(
        command_type: str,
        params: dict[str, Any] | None = None,
        host: str | None = None,
        port: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        """
        Send a raw JSON command to the reference RhinoMCP plug-in socket server.

        Use this when Rhino 7 or an existing `rhinomcp` plug-in workflow is
        required instead of the Rhino 8.11+ `rhinocode` backend.
        """
        return plugin_client.send_command(command_type, params, host=host, port=port, timeout=timeout)

"""Generic Rhino plugin introspection and command execution tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="List Installed Plugins", readOnlyHint=True))
    def list_installed_plugins() -> dict[str, object]:
        """List all installed Rhino plugins with name, GUID, loaded status, and path."""
        return plugin_client.send_command("list_plugins", {})

    @mcp.tool(annotations=ToolAnnotations(title="Get Plugin Commands", readOnlyHint=True))
    def get_plugin_commands(
        plugin_name: str | None = None,
        plugin_id: str | None = None,
    ) -> dict[str, object]:
        """
        List all Rhino commands registered by a specific plugin.
        Provide plugin_name (partial, case-insensitive) or plugin_id (GUID).
        """
        return plugin_client.send_command(
            "get_plugin_commands",
            {"plugin_name": plugin_name, "plugin_id": plugin_id},
        )

    @mcp.tool(annotations=ToolAnnotations(title="Run Plugin Command", destructiveHint=True))
    def run_plugin_command(command: str, options_string: str = "") -> dict[str, object]:
        """
        Run any Rhino command string, including commands from third-party plugins.
        options_string is appended after the command name (e.g. '_Enter' to confirm prompts).
        """
        full = f"{command} {options_string}".strip()
        return plugin_client.send_command("run_command", {"command": full})

    @mcp.tool(annotations=ToolAnnotations(title="Check Plugin Loaded", readOnlyHint=True))
    def check_plugin_loaded(plugin_name: str) -> dict[str, object]:
        """
        Check whether a plugin is installed and loaded in Rhino.
        Returns {loaded: bool, message: str, plugin: {...}} .
        """
        result = plugin_client.send_command("list_plugins", {})
        plugins = result.get("result", {}).get("plugins", [])
        match = next(
            (p for p in plugins if plugin_name.lower() in p["name"].lower()), None
        )
        if match is None:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is not installed. Install it via the Rhino Package Manager or the plugin vendor.",
            }
        if not match["loaded"]:
            return {
                "loaded": False,
                "message": f"'{plugin_name}' is installed but not loaded. Use load_plugin to load it.",
            }
        return {"loaded": True, "plugin": match}

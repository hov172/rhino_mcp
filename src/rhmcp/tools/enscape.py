"""Enscape real-time rendering tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("Enscape" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Enscape is not installed or not loaded. Install from enscape3d.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Start", destructiveHint=True))
    def enscape_start() -> dict[str, object]:
        """Launch the Enscape real-time rendering window."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_Start")
        return {"success": True, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Screenshot", destructiveHint=True))
    def enscape_screenshot(
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> dict[str, object]:
        """Capture a screenshot from the current Enscape view."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_Screenshot {output_path!r}")
        return {"success": True, "output_path": output_path, "width": width, "height": height, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Panorama", destructiveHint=True))
    def enscape_export_panorama(
        output_path: str,
        resolution: str = "4K",
    ) -> dict[str, object]:
        """Export a 360° panorama image from Enscape. resolution: 2K | 4K | 8K."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_ExportPanorama {output_path!r}")
        return {"success": True, "output_path": output_path, "resolution": resolution, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Standalone", destructiveHint=True))
    def enscape_export_standalone(output_path: str) -> dict[str, object]:
        """Export the scene as an Enscape standalone executable (.exe)."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_ExportStandalone {output_path!r}")
        return {"success": True, "output_path": output_path, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Set Time of Day", destructiveHint=True))
    def enscape_set_time_of_day(hour: int = 12, minute: int = 0) -> dict[str, object]:
        """Set the sun time of day in Enscape. hour: 0-23, minute: 0-59."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_TimeOfDay {hour} {minute}")
        return {"success": True, "hour": hour, "minute": minute, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Set Atmosphere", destructiveHint=True))
    def enscape_set_atmosphere(
        cloud_density: float = 0.3,
        wind_speed: float = 0.0,
        precipitation_type: str = "none",
    ) -> dict[str, object]:
        """
        Configure Enscape atmosphere settings.
        cloud_density: 0.0-1.0. precipitation_type: none | rain | snow.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_VisualSettings")
        return {"success": True, "cloud_density": cloud_density, "wind_speed": wind_speed, "precipitation_type": precipitation_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Create View", destructiveHint=True))
    def enscape_create_view(name: str) -> dict[str, object]:
        """Save the current Enscape camera position as a named view."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_CreateView {name!r}")
        return {"success": True, "name": name, "result": result}

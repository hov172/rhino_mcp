"""Enscape real-time rendering tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import backend
from rhmcp.tools_helpers import plugin_client
from rhmcp.tools_helpers.security import sanitise_rhino_path


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("Enscape" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Enscape is not installed or not loaded. Install from enscape3d.com."
    return None


def _run(command: str) -> dict:
    return backend.run_command(command)


def _outcome(res: dict) -> tuple[bool, str | None]:
    """Extract (ok, error) from a backend response so failures propagate."""
    ok = bool(res.get("ok"))
    if ok:
        return True, None
    return False, str(res.get("error") or res.get("message") or "Rhino command failed")


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Start", destructiveHint=True))
    def enscape_start() -> dict[str, object]:
        """Launch the Enscape real-time rendering window."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_Start")
        ok, error = _outcome(result)
        out: dict[str, object] = {"success": ok, "result": result}
        if error:
            out["error"] = error
        return out

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
        safe_path = sanitise_rhino_path(output_path)
        result = _run('Enscape_Screenshot "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"output_path": output_path, "width": width, "height": height},
            "note": (
                "Enscape_Screenshot may open an interactive save dialog; width and "
                "height are configured in Enscape's visual settings and were not "
                "applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Panorama", destructiveHint=True))
    def enscape_export_panorama(
        output_path: str,
        resolution: str = "4K",
    ) -> dict[str, object]:
        """Export a 360° panorama image from Enscape. resolution: 2K | 4K | 8K."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('Enscape_ExportPanorama "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"output_path": output_path, "resolution": resolution},
            "note": (
                "Enscape_ExportPanorama may open an interactive export dialog; the "
                "resolution setting was not applied programmatically."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Standalone", destructiveHint=True))
    def enscape_export_standalone(output_path: str) -> dict[str, object]:
        """Export the scene as an Enscape standalone executable (.exe)."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('Enscape_ExportStandalone "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"output_path": output_path},
            "note": "Enscape_ExportStandalone may open an interactive export dialog.",
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Set Time of Day", destructiveHint=True))
    def enscape_set_time_of_day(hour: int = 12, minute: int = 0) -> dict[str, object]:
        """Set the sun time of day in Enscape. hour: 0-23, minute: 0-59."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"Enscape_TimeOfDay {hour} {minute}")
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"hour": hour, "minute": minute},
            "result": result,
        }
        if error:
            out["error"] = error
        return out

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
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": (
                "Enscape_VisualSettings opens an interactive dialog; cloud_density, "
                "wind_speed, and precipitation_type could not be applied "
                "programmatically. Adjust them in the dialog."
            ),
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Create View", destructiveHint=True))
    def enscape_create_view(name: str) -> dict[str, object]:
        """Save the current Enscape camera position as a named view."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_name = sanitise_rhino_path(name)
        result = _run('Enscape_CreateView "' + safe_name + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {"success": ok, "name": name, "result": result}
        if error:
            out["error"] = error
        return out

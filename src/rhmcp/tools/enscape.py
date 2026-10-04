"""Enscape real-time rendering tools for Rhino.

Enscape exposes no scripting API beyond its Rhino commands, so these tools
only launch those commands.  Values such as image size, panorama
resolution and atmosphere are configured in Enscape's own dialogs.
"""

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
    def enscape_screenshot(output_path: str) -> dict[str, object]:
        """Run ``Enscape_Screenshot`` for the current Enscape view.

        The command may open an interactive save dialog. Image size is an
        Enscape visual setting and cannot be scripted, so no size parameters
        are offered.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('Enscape_Screenshot "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"output_path": output_path},
            "note": "Enscape_Screenshot may open an interactive save dialog.",
            "result": result,
        }
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Enscape: Export Panorama", destructiveHint=True))
    def enscape_export_panorama(output_path: str) -> dict[str, object]:
        """Run ``Enscape_ExportPanorama`` to export a 360° panorama.

        The command may open an interactive export dialog. Panorama
        resolution is an Enscape setting and cannot be scripted, so no
        resolution parameter is offered.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('Enscape_ExportPanorama "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "requested": {"output_path": output_path},
            "note": "Enscape_ExportPanorama may open an interactive export dialog.",
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
    def enscape_set_atmosphere() -> dict[str, object]:
        """Open Enscape's Visual Settings dialog (``Enscape_VisualSettings``).

        Atmosphere values (clouds, wind, precipitation) have no scripting
        interface and must be adjusted in the dialog, so no parameters are
        offered and nothing is applied programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("Enscape_VisualSettings")
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "note": "Enscape_VisualSettings opens an interactive dialog; adjust atmosphere there.",
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

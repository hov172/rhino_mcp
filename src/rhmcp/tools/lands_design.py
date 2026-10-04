"""Lands Design landscape and terrain tools for Rhino.

Lands Design has no public scripting API and its ``la*`` commands are
interactive: each placement tool below only launches the command, which
then expects mouse input.  Nothing about the plant, position or geometry
can be passed programmatically, so those parameters are not offered.
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
    if not any("Lands" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Lands Design is not installed or not loaded. Install from lands-design.com."
    return None


def _run(command: str) -> dict:
    return backend.run_command(command)


def _outcome(res: dict) -> tuple[bool, str | None]:
    """Extract (ok, error) from a backend response so failures propagate."""
    ok = bool(res.get("ok"))
    if ok:
        return True, None
    return False, str(res.get("error") or res.get("message") or "Rhino command failed")


def _interactive(command: str, **extra: object) -> dict[str, object]:
    result = _run(command)
    ok, error = _outcome(result)
    out: dict[str, object] = {
        "success": ok,
        "command": command,
        "note": (
            f"{command} is an interactive Lands Design command that expects mouse "
            "input; nothing can be applied programmatically."
        ),
        "result": result,
    }
    out.update(extra)
    if error:
        out["error"] = error
    return out


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Plant", destructiveHint=True))
    def lands_place_plant() -> dict[str, object]:
        """Launch the interactive ``_laPlant`` command.

        Lands Design has no scripting API: species, position and size are
        chosen with the mouse; nothing can be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laPlant", applied={}, not_applied={})

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Tree", destructiveHint=True))
    def lands_place_tree() -> dict[str, object]:
        """Launch the interactive ``_laPlant`` command (trees are plants in Lands Design).

        Species, position and size are chosen with the mouse; nothing can be
        passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laPlant")

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Terrain", destructiveHint=True))
    def lands_create_terrain() -> dict[str, object]:
        """Launch the interactive ``_laTerrain`` command.

        Boundary and source geometry are picked with the mouse; nothing can be
        passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laTerrain")

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Path", destructiveHint=True))
    def lands_create_path() -> dict[str, object]:
        """Launch the interactive ``_laPath`` command.

        Centerline, width and surface are chosen with the mouse; nothing can
        be passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laPath")

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Water Feature", destructiveHint=True))
    def lands_create_water() -> dict[str, object]:
        """Launch the interactive ``_laWater`` command.

        Boundary and water level are chosen with the mouse; nothing can be
        passed programmatically.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laWater")

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Open Plant Database", readOnlyHint=True))
    def lands_get_plant_database() -> dict[str, object]:
        """Open the interactive ``_laPlantDatabase`` window.

        No plant list is returned and no filtering can be scripted.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        return _interactive("_laPlantDatabase")

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Set Season", destructiveHint=True))
    def lands_set_season(season: str = "summer") -> dict[str, object]:
        """
        Set the display season for Lands Design plants and trees.
        season: spring | summer | autumn | winter.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        valid = {"spring", "summer", "autumn", "winter"}
        if season.lower() not in valid:
            return {"success": False, "message": f"Invalid season '{season}'. Valid: {', '.join(sorted(valid))}"}
        result = _run(f"_laSeason {season}")
        ok, error = _outcome(result)
        out: dict[str, object] = {"success": ok, "season": season, "result": result}
        if error:
            out["error"] = error
        return out

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Export Plant List", destructiveHint=True))
    def lands_export_plant_list(output_path: str) -> dict[str, object]:
        """Export a plant schedule from the current Lands Design model.

        The output format follows the file extension of ``output_path``
        (e.g. ``.csv`` or ``.xlsx``); the command has no separate format option.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        safe_path = sanitise_rhino_path(output_path)
        result = _run('_laExportPlantList "' + safe_path + '"')
        ok, error = _outcome(result)
        out: dict[str, object] = {
            "success": ok,
            "output_path": output_path,
            "result": result,
        }
        if error:
            out["error"] = error
        return out

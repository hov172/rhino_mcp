"""Lands Design landscape and terrain tools for Rhino."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from rhmcp.tools_helpers import plugin_client


def _check() -> str | None:
    result = plugin_client.send_command("list_plugins", {})
    plugins = result.get("result", {}).get("plugins", [])
    if not any("Lands" in p.get("name", "") and p.get("loaded") for p in plugins):
        return "Lands Design is not installed or not loaded. Install from lands-design.com."
    return None


def _run(command: str) -> dict:
    return plugin_client.send_command("run_command", {"command": command})


def _py(code: str) -> dict:
    return plugin_client.send_command("execute_rhinoscript_python_code", {"code": code})


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Plant", destructiveHint=True))
    def lands_place_plant(
        plant_name: str,
        position: list[float],
        rotation_degrees: float = 0.0,
        scale: float = 1.0,
    ) -> dict[str, object]:
        """Place a plant from the Lands Design library at a position."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlant")
        return {"success": True, "plant_name": plant_name, "position": position, "rotation_degrees": rotation_degrees, "scale": scale, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Place Tree", destructiveHint=True))
    def lands_place_tree(
        species_name: str,
        position: list[float],
        trunk_height: float = 2.0,
        canopy_radius: float = 3.0,
    ) -> dict[str, object]:
        """Place a tree from the Lands Design species library at a position."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlant")
        return {"success": True, "species_name": species_name, "position": position, "trunk_height": trunk_height, "canopy_radius": canopy_radius, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Terrain", destructiveHint=True))
    def lands_create_terrain(
        boundary_curve_id: str,
        source_type: str = "contours",
        source_id: str | None = None,
    ) -> dict[str, object]:
        """
        Create a Lands Design terrain from curves or a point cloud.
        source_type: contours | points.
        source_id: GUID of the source geometry object.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laTerrain")
        return {"success": True, "boundary_curve_id": boundary_curve_id, "source_type": source_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Path", destructiveHint=True))
    def lands_create_path(
        centerline_curve_id: str,
        width: float = 2.0,
        surface_type: str = "Asphalt",
    ) -> dict[str, object]:
        """Create a Lands Design path or road along a curve."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPath")
        return {"success": True, "centerline_curve_id": centerline_curve_id, "width": width, "surface_type": surface_type, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Create Water Feature", destructiveHint=True))
    def lands_create_water(
        boundary_curve_id: str,
        water_level_z: float = 0.0,
    ) -> dict[str, object]:
        """Create a Lands Design water surface within a boundary curve."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laWater")
        return {"success": True, "boundary_curve_id": boundary_curve_id, "water_level_z": water_level_z, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Get Plant Database", readOnlyHint=True))
    def lands_get_plant_database(
        search_query: str = "",
        category: str = "",
    ) -> dict[str, object]:
        """List available plants and species in the Lands Design database."""
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run("_laPlantDatabase")
        return {"success": True, "search_query": search_query, "category": category, "result": result}

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
        return {"success": True, "season": season, "result": result}

    @mcp.tool(annotations=ToolAnnotations(title="Lands: Export Plant List", destructiveHint=True))
    def lands_export_plant_list(
        output_path: str,
        format: str = "csv",
    ) -> dict[str, object]:
        """
        Export a plant schedule from the current Lands Design model.
        format: csv | xlsx.
        """
        err = _check()
        if err:
            return {"success": False, "message": err}
        result = _run(f"_laExportPlantList {output_path!r}")
        return {"success": True, "output_path": output_path, "format": format, "result": result}

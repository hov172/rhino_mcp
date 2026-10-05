"""Fail if a skills/**/*.md file names a tool that does not exist in src/rhmcp/tools/."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL_LIKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")  # snake_case with at least one underscore
# Snake-case words that appear in backticks but are params, keys, or deliberately named broken tools.
NOT_TOOLS = {
    "script_result", "error_code", "result_ids", "result_id", "instance_guid", "step_log",
    "loop_start_instance_guid", "loop_end_instance_guid", "type_name", "far_target", "office_pct",
    "emission_multiplier", "enable_ground_plane",
    "ground_plane_altitude", "delete_input", "delete_sources", "rotate_center",
    "scale_origin", "verified_functions", "clear_objects", "scale_hint", "real_units_per_px",
    "real_units_per_point", "layer_prefix", "max_dimension", "all_objects", "wait_ms", "timed_out",
    "error_count", "output_format", "north_angle", "run_energy", "job_id", "light_style",
    "set_material_", "textures_applied", "far_within_2pct", "recommended_params", "missing_fields",
    "component_guid", "from_guid", "to_guid", "from_output", "to_input", "object_ids", "object_id",
    "rhino_id", "u_count", "v_count", "max_loops", "goal_type", "epw_file_path", "room_name",
    "user_text", "name_filter", "user_text_key", "rhino_object_id", "image_paths", "not_applied", "warning_count", "file_type", "export_texture_coordinates", "use_for_background", "use_for_lighting", "use_for_reflections", "quality_preset", "allow_partial", "from_instance", "to_instance", "from_key", "to_key", "api_key",
    "site_origin", "site_width", "site_depth", "analysis_type", "geometry_layer", "climate_zone",
    "epw_path", "analysis_period", "style_hints", "project_name", "scheme_name", "include_solar",
    "render_views", "skip_steps", "version_name", "material_name", "base_color", "asset_type",
    "asset_id", "display_mode", "transparent_background", "return_base64", "output_path",
    "source_path", "rhino_version", "autocad_version", "draco_compression", "header_row",
    "include_raw", "render_png", "include_tables", "max_paragraphs", "extract_text", "max_pages",
    "pixel_point_1", "pixel_point_2", "real_distance", "real_unit", "min_length_px", "include_hidden",
    "plane_origin", "plane_normal", "corner_style", "loft_type", "base_point", "curve_ids",
    "curve_id", "base_id", "subtract_ids", "rail_id", "profile_ids", "rail1_id", "rail2_id",
    "brep_id", "mesh_id", "u_spans", "v_spans", "block_name", "font_size", "diffuse_color",
    "profile_id", "radius_x", "radius_y", "radius_z", "major_radius", "minor_radius", "start_angle",
    "end_angle", "point_on_arc", "is_diameter", "snap_to_grid", "geometry_type", "layer_color",
    "plugin_name", "file_path", "wired", "placed",
    # geometry type strings, typology names, pipeline step names, and result keys
    "plane_surface", "nurbs_curve", "block_insert", "clipping_plane", "dimension_linear",
    "dimension_radial", "podium_tower", "perimeter_block", "street_grid", "design_language",
    "instance_count", "tri_panels", "diamond_panels", "hex_panels",
}


def known_tools() -> set[str]:
    names = set()
    for path in (ROOT / "src/rhmcp/tools").glob("*.py"):
        src = path.read_text()
        # Every nested def in a tool module; helpers are harmless extra names.
        names.update(re.findall(r"^\s+(?:async\s+)?def\s+([a-z0-9_]+)\(", src, re.M))
    names.update(re.findall(r"\| `([a-z0-9_]+)`", (ROOT / "README.md").read_text()))
    return names


def main() -> int:
    known = known_tools()
    bad = 0
    for path in sorted((ROOT / "skills").rglob("*.md")):
        for token in sorted(set(re.findall(r"`([a-z0-9_]+)(?:\(|`)", path.read_text()))):
            if TOOL_LIKE.match(token) and token not in known and token not in NOT_TOOLS:
                print(f"{path.relative_to(ROOT)}: unknown tool `{token}`")
                bad += 1
    print("ok" if not bad else f"{bad} unknown tool name(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

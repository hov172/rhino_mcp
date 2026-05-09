"""
FastMCP prompt resource: urban_brief

Claude reads this prompt before any urban massing generation. It provides a
structured intake template that ensures all mandatory parameters are collected
before the first tool call is made.

Auto-discovered by the pkgutil loop in src/rhmcp/__init__.py, like the other
tool modules. No registration changes are needed.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_BRIEF_TEMPLATE = """\
# Urban Massing Brief

You are about to generate a 3D urban massing in Rhino. Collect the following
parameters from the user before calling urban_generate_massing. Ask for missing
mandatory fields one at a time. Confirm collected values before proceeding.

## Mandatory fields (always ask if not provided)

- **site_width** (metres): Width of the site footprint.
- **site_depth** (metres): Depth of the site footprint.
- **far_target**: Target floor area ratio (e.g. 3.5 = 3.5x the site area as GFA).

## Optional fields (use defaults if not provided)

- **site_origin** [x, y, z]: Corner of the site in Rhino world coordinates.
  Default: [0, 0, 0].
- **typology**: One of "tower", "podium_tower", "courtyard", "perimeter_block",
  "street_grid". If not specified, recommend the best fit based on FAR and
  program mix:
    - FAR < 1.5: perimeter_block or courtyard
    - 1.5 <= FAR < 3.0: courtyard or podium_tower
    - FAR >= 3.0: podium_tower or tower
    - Large multi-block site: street_grid first, then place typologies on plots
- **residential_pct** (0-100): Percentage residential floor area. Default: 70.
- **office_pct** (0-100): Percentage office floor area. Default: 20.
- **retail_pct** (0-100): Percentage retail floor area. Default: 10.
  (residential_pct + office_pct + retail_pct should sum to <= 100)
- **climate_zone**: One of London, New York, Dubai, Tokyo, Sydney, Singapore,
  Berlin. Required only if the user asks for solar analysis. Default: London.
- **epw_path**: Absolute path to a custom .epw weather file. Overrides
  climate_zone. Leave blank unless the user provides a file path.

## Workflow after collecting parameters

1. Confirm: "I'll generate a {typology} massing, {site_width}x{site_depth}m,
   FAR {far_target}, {residential_pct}% residential / {office_pct}% office /
   {retail_pct}% retail. Proceeding..."
2. Call: urban_generate_massing(typology, site_origin, site_width, site_depth,
   params={far_target, residential_pct, office_pct, retail_pct})
3. Call: urban_capture_and_evaluate() to show the image and report metrics.
4. Offer next steps: "Want to adjust any parameters, try a different typology,
   or run solar analysis?"

## Amendment loop

After the first generation, accept free-form amendments:
- "Make the tower 5 floors taller": urban_update_param("floor_count", current+5)
- "Try a courtyard instead": urban_clear_massing(), then urban_generate_massing(typology="courtyard", ...)
- "Run solar analysis": urban_run_analysis(analysis_type="solar", ...)
- Always call urban_capture_and_evaluate() after any geometry change.
"""


def register(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="urban_brief",
        description=(
            "Structured intake for urban massing generation. "
            "Read this before calling any urban_* tool."
        ),
    )
    def urban_brief() -> str:
        return _BRIEF_TEMPLATE

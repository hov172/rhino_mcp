# `urban_generate_massing` slider names by typology

Keys in `params` must match exactly. Unknown keys are ignored without error.

| Typology | Sliders |
|---|---|
| `tower` | site_width, site_depth, tower_count, floor_count, floor_height, footprint_width, footprint_depth, setback, residential_pct, retail_floors |
| `podium_tower` | site_width, site_depth, podium_floors, podium_setback, tower_floors, tower_count, floor_height, residential_pct, retail_pct |
| `courtyard` | site_width, site_depth, wing_width, floor_count, floor_height, corner_opening_width, residential_pct, retail_pct |
| `perimeter_block` | site_width, site_depth, block_width, floor_count, floor_height, residential_pct, retail_pct |
| `street_grid` | site_width, site_depth, block_width, block_depth, road_width, grid_rotation |

`optimize_plan` adjusts: tower → floor_count (5 to 80); podium_tower → tower_floors (5 to 60), podium_floors, podium_setback; courtyard → floor_count (≤12); perimeter_block → floor_count (≤10); street_grid → fixed 80/60/12.

Typology auto-selection in `parse_urban_prompt` when no keyword is present: FAR below 1.5 → perimeter_block, below 3 → courtyard, below 5 → podium_tower, otherwise tower. No FAR → podium_tower.

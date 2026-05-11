# Knicks vs 76ers Crushing Animation

**Date:** 2026-05-10  
**Type:** Rhino 3D Python viewport animation script

## Logos

| Team | Logo | Colors |
|---|---|---|
| NY Knicks | Blue/orange triangular shield with "KNICKS" text | `#006BB6` blue, `#F58426` orange |
| Philadelphia 76ers | Retro "76" numeral + shooting star | `#C0102E` red, `#002B5C` navy |

## Geometry Strategy

- **Knicks shield** — hand-coded bezier polyline (5-point pentagon shield silhouette), extruded 0.4 units, "KNICKS" text via `Rhino.Geometry.TextEntity` outline curves extruded on face
- **76ers "76"** — `TextEntity` outline curves for "76" in a bold slab-serif approximation, extruded 0.4 units; shooting star as a 5-point star polygon + trailing arc, extruded 0.2 units
- All geometry converted to meshes per frame for animation via mesh replacement

## Camera

Low ground-level perspective, slightly off-center (right side), looking up at a ~25° angle toward the Knicks shield. Fixed base position with shake vector added on impact frames.

## Animation Phases

| Phase | Frames | Duration | Action |
|---|---|---|---|
| Establish | 0–30 | 1.0s | Both logos stationary facing off, camera locks |
| Anticipation | 30–50 | 0.67s | Knicks shield translates back –0.5 units (wind-up) |
| Charge | 50–90 | 1.33s | Shield accelerates +Z toward 76ers, ease-in curve |
| Impact | 90–100 | 0.33s | Contact — both logos squash on collision axis, camera shake ±0.4 units |
| Crush | 100–150 | 1.67s | 76ers scale_x collapses 1.0→0.08, widens in Y; Knicks holds |
| Hold | 150–180 | 1.0s | Final pose, camera shake damps to zero |

**Total:** 180 frames @ 30 fps = 6 seconds

## Layers

- `KN_Shield` — Knicks blue
- `KN_Text` — Knicks orange  
- `PHI_76` — 76ers red
- `PHI_Star` — 76ers navy
- `Court` — hardwood tan `#C28C4F`

## Technical Notes

- Mesh replacement per frame (same pattern as `bouncing_ball.py`)
- `Rhino.RhinoApp.Wait()` after each redraw to pump the message queue
- Camera shake: random offset vector scaled by shake_intensity, decays after frame 110
- 76ers crush applied as non-uniform `rg.Transform.Scale` about the back face of the "76" mesh
- Knicks shield charge position driven by ease-in cubic: `t³` for acceleration feel

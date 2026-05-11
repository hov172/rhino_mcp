"""
Bouncing Ball - Rhino 3D Python Script
Creates a UV sphere at Z=10 and plays back a physics-based bounce with
squash-and-stretch deformation in the Rhino viewport.

NOTE: Bongo is NOT installed on this system. Keyframe animation requires Bongo 2+.
      This script uses live viewport playback via mesh replacement each frame.

Run from: Rhino > Tools > PythonScript > Run
"""

import rhinoscriptsyntax as rs
import Rhino
import Rhino.Geometry as rg
import scriptcontext as sc
import System
import math
import time

# ── Configuration ──────────────────────────────────────────────────────────────
RADIUS      = 1.0    # sphere radius (Rhino units)
START_Z     = 10.0   # initial drop height
GRAVITY     = 9.8    # acceleration (units/s²)
RESTITUTION = 0.65   # energy kept per bounce  (0 = dead stop, 1 = perfect)
FPS         = 30     # viewport playback rate
DURATION    = 7.0    # total seconds to simulate
U_SEGS      = 24     # UV sphere longitude divisions
V_SEGS      = 16     # UV sphere latitude divisions
# ──────────────────────────────────────────────────────────────────────────────


def compute_frames(start_z, radius, gravity, restitution, duration, fps):
    """
    Return list of (t, z, scale_xy, scale_z) for every frame.
    Squash/stretch is driven by normalised impact speed.
    """
    dt     = 1.0 / fps
    frames = []
    z, vz, t = start_z, 0.0, 0.0

    max_speed = math.sqrt(2.0 * gravity * start_z)   # free-fall from start_z

    while t <= duration:
        speed_norm = min(abs(vz) / max_speed, 1.0) if max_speed > 0 else 0.0

        at_ground = (z <= radius + 1e-4) and (vz <= 0)

        if at_ground:
            # Squash: flatten vertically, widen horizontally
            sq    = 0.35 * speed_norm
            sxy   = 1.0 + sq
            sz    = max(1.0 - sq, 0.35)
        else:
            # Stretch in flight: elongate in direction of travel
            st    = 0.18 * speed_norm
            sxy   = 1.0 - st * 0.4
            sz    = 1.0 + st

        frames.append((t, z, sxy, sz))

        # Euler integration
        vz -= gravity * dt
        z  += vz * dt

        if z <= radius:
            z  = radius
            vz = abs(vz) * restitution
            if vz < 0.25:                    # ball has effectively stopped
                rest_frames = int((duration - t) * fps)
                for k in range(rest_frames):
                    frames.append((t + k / fps, radius, 1.0, 1.0))
                break

        t += dt

    return frames


def make_sphere_mesh(z, sxy, sz):
    """
    Build a UV sphere mesh centred at (0, 0, z) with non-uniform scale
    applied about the contact point so squash pushes outward from the floor.
    """
    # Unit sphere at origin
    sphere = rg.Sphere(rg.Point3d.Origin, RADIUS)
    mesh   = rg.Mesh.CreateFromSphere(sphere, U_SEGS, V_SEGS)

    # Scale about the bottom of the sphere (contact point when z == RADIUS)
    contact = rg.Point3d(0, 0, -(RADIUS))          # bottom of unit sphere
    scale   = rg.Transform.Scale(
        rg.Plane(contact, rg.Vector3d.ZAxis),
        sxy, sxy, sz
    )
    mesh.Transform(scale)

    # Translate so ball centre sits at z
    move = rg.Transform.Translation(0, 0, z)
    mesh.Transform(move)

    return mesh


def clear_layer(layer_name):
    layer = sc.doc.Layers.FindName(layer_name)
    if layer is None:
        return
    objs = sc.doc.Objects.FindByLayer(layer)
    if objs:
        for obj in objs:
            sc.doc.Objects.Delete(obj.Id, True)


def setup_scene():
    if not rs.IsLayer("BB_Ground"):
        rs.AddLayer("BB_Ground", System.Drawing.Color.FromArgb(180, 180, 180))
    if not rs.IsLayer("BB_Ball"):
        rs.AddLayer("BB_Ball", System.Drawing.Color.FromArgb(220, 80, 30))

    clear_layer("BB_Ball")

    ground_layer = sc.doc.Layers.FindName("BB_Ground")
    existing = sc.doc.Objects.FindByLayer(ground_layer) if ground_layer else None
    if not existing:
        rs.CurrentLayer("BB_Ground")
        size = 14.0
        corners = [
            rg.Point3d(-size, -size, 0),
            rg.Point3d( size, -size, 0),
            rg.Point3d( size,  size, 0),
            rg.Point3d(-size,  size, 0),
        ]
        srf = rg.NurbsSurface.CreateFromCorners(*corners)
        sc.doc.Objects.AddSurface(srf)

    rs.CurrentLayer("BB_Ball")


def run():
    rs.EnableRedraw(False)
    setup_scene()
    rs.EnableRedraw(True)
    rs.Command("_SetDisplayMode _Mode=Shaded", False)
    rs.ZoomExtents(None, True)

    frames = compute_frames(START_Z, RADIUS, GRAVITY, RESTITUTION, DURATION, FPS)
    print(f"Bouncing ball: {len(frames)} frames @ {FPS} fps  —  press Esc in Rhino to abort")

    ball_id = None   # GUID of current ball mesh in document

    for i, (t, z, sxy, sz) in enumerate(frames):
        frame_start = time.time()

        mesh    = make_sphere_mesh(z, sxy, sz)
        new_id  = sc.doc.Objects.AddMesh(mesh)

        # Set layer/colour on the new object
        obj = sc.doc.Objects.Find(new_id)
        if obj:
            attr = obj.Attributes.Duplicate()
            attr.LayerIndex = sc.doc.Layers.FindName("BB_Ball").Index
            attr.ColorSource = Rhino.DocObjects.ObjectColorSource.ColorFromLayer
            sc.doc.Objects.ModifyAttributes(obj, attr, True)

        # Remove previous frame's mesh
        if ball_id is not None:
            sc.doc.Objects.Delete(ball_id, True)

        ball_id = new_id
        sc.doc.Views.Redraw()

        # Pace to target FPS
        elapsed = time.time() - frame_start
        wait    = (1.0 / FPS) - elapsed
        if wait > 0:
            time.sleep(wait)

    print("Playback complete.  Final resting ball remains in the scene.")
    rs.ZoomExtents(None, True)


run()

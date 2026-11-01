"""Test stills for look development. Not part of the final render.

Usage: blender -b -P blender/lookdev.py -- <out-prefix> [samples]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy

import lib
from pcb import BoardBuilder

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
samples = int(argv[1]) if len(argv) > 1 else 24

s = lib.reset()
lib.render_setup(s, samples=samples, motion_blur=False)
lib.threads(s)
lib.studio(s)
mats = lib.Mats()
b = BoardBuilder(mats, "reflowed")
root = b.build()
root.location.z = 0.4
stand = lib.obj("stand", lib.rbox("stand", 9, 6, 0.24, 0.02, 1, mat=mats.grey_panel))

shots = {
    "hero": (65, 5.6, (9.5, -13.5, 8.6), (0.4, -0.3, 0.45)),
    "macro": (100, 8, (5.6, -4.4, 1.25), (3.1, -2.0, 0.42)),
}
cam, target = lib.camera(s)
for name, (lens, fstop, pos, aim) in shots.items():
    cam.data.lens = lens
    cam.data.dof.aperture_fstop = fstop
    cam.location = pos
    target.location = aim
    s.render.filepath = f"{out}_{name}.jpg"
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"RENDER {name}: {time.time() - t:.1f}s", flush=True)

"""Render one shot: frames plus the screen position of its labelled 3D points.

blender -b --factory-startup -P blender/render.py -- --shot NAME --frames 96 --out DIR
    [--step 2] [--samples 8] [--res 1280x720] [--only 1,48,96] [--still]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

import lib
from shots import SHOTS, Ctx

ap = argparse.ArgumentParser()
ap.add_argument("--shot", required=True)
ap.add_argument("--frames", type=int, required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--step", type=int, default=2)
ap.add_argument("--samples", type=int, default=8)
ap.add_argument("--res", default="1280x720")
ap.add_argument("--only", default="")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])

res = tuple(int(v) for v in args.res.split("x"))
s = lib.reset()
lib.render_setup(s, samples=args.samples, res=res, motion_blur=False)
lib.threads(s)
ctx = Ctx(s, args.frames)
SHOTS[args.shot](ctx)
s.frame_start, s.frame_end = 1, args.frames
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)

frames = [int(v) for v in args.only.split(",") if v] or list(range(1, args.frames + 1, args.step))
if frames[-1] != args.frames and not args.only:
    frames.append(args.frames)

# Label anchors are recorded for every frame so overlays stay glued to the model.
track = {}
if ctx.anchors:
    for f in range(1, args.frames + 1):
        s.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for name, target in ctx.anchors.items():
            p = world_to_camera_view(s, s.camera, Vector(target))
            track.setdefault(name, []).append([round(p.x * res[0], 1), round((1 - p.y) * res[1], 1)])
    (out / "anchors.json").write_text(json.dumps(track), encoding="utf-8")

for i, f in enumerate(frames):
    done = out / f"f{f:05d}.jpg"
    if done.exists():
        continue
    s.frame_set(f)
    s.render.filepath = str(done)
    bpy.ops.render.render(write_still=True)
    print(f"DONE {args.shot} {f}", flush=True)

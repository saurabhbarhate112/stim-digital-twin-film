"""Render orchestration for GitHub Actions. Every finished 3D shot goes to a 'render-cache'
release under a content hash, so re-runs resume and unchanged shots are never rendered twice.

  ci.py plan N           list what still needs rendering, as N balanced shards
  ci.py render SHARD     render that shard's items, uploading each as it finishes
  ci.py fetch            download all cached items into build/
  ci.py finish           concatenate segments, mix audio, burn captions, encode
"""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
TAG = "render-cache"
BLENDER = os.environ.get("BLENDER", "blender")
SAMPLES = 8
PLATE_SAMPLES = 24
# Fast mechanical motion gets every frame; slow camera moves can interpolate cleanly.
EVERY_FRAME = {"pnp_macro", "nozzle_drop", "squeegee", "wipe", "test_probe", "melt"}
HEAVY = ("line", "twin", "ordinary", "oven")


def sh(*args, **kw):
    return subprocess.run([str(a) for a in args], check=True, **kw)


def out(*args):
    return subprocess.check_output([str(a) for a in args]).decode()


def shared_hash():
    h = hashlib.sha256()
    for f in ("lib.py", "pcb.py", "machines.py", "twin.py", "layout.py", "render.py"):
        h.update((ROOT / "blender" / f).read_bytes())
    for f in ("pcb_maps.py", "textures.py"):
        h.update((ROOT / "tools" / f).read_bytes())
    return h.hexdigest()


def function_sources():
    src = (ROOT / "blender" / "shots.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    return {n.name: ast.get_source_segment(src, n) for n in tree.body if isinstance(n, ast.FunctionDef)}, src


def manifest():
    tl = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    fns, whole = function_sources()
    base = shared_hash()
    # Helpers are hashed with everything, shot functions individually: a tweak to one shot re-renders one shot.
    shots = {s["src"]: s for s in tl["shots"] if s["kind"] != "stock"}
    helpers = "".join(v for k, v in sorted(fns.items()) if k not in shots)
    items = {}
    for s in tl["shots"]:
        if s["kind"] == "stock" or s["src"] in items:
            continue
        still = s["kind"] == "plate"
        frames = 1 if still else s["frames"]
        step = 1 if still or s["src"] in EVERY_FRAME else 2
        samples = PLATE_SAMPLES if still else SAMPLES
        sig = json.dumps([base, helpers, fns.get(s["src"], ""), frames, step, samples])
        items[s["src"]] = {"src": s["src"], "frames": frames, "step": step, "samples": samples, "still": still,
                           "key": s["src"] + "-" + hashlib.sha256(sig.encode()).hexdigest()[:12]}
    return list(items.values())


def assets():
    if subprocess.run(["gh", "release", "view", TAG], capture_output=True).returncode:
        sh("gh", "release", "create", TAG, "--prerelease", "--title", "Render cache", "--notes", "Shot cache. Safe to delete.")
    data = json.loads(out("gh", "release", "view", TAG, "--json", "assets"))
    return {a["name"] for a in data["assets"]}


def done(item, have):
    return f"{item['key']}.{'jpg' if item['still'] else 'mp4'}" in have


def cost(i):
    c = max(1, i["frames"] // i["step"]) * (i["samples"] / 8)
    return c * (1.7 if any(h in i["src"] for h in HEAVY) else 1.0)


def plan(n):
    have = assets()
    items = manifest()
    todo = [i for i in items if not done(i, have)]
    shards = [[] for _ in range(n)]
    loads = [0.0] * n
    for i in sorted(todo, key=cost, reverse=True):
        k = loads.index(min(loads))
        shards[k].append(i["src"])
        loads[k] += cost(i)
    (BUILD / "shards.json").write_text(json.dumps(shards), encoding="utf-8")
    used = [k for k, s in enumerate(shards) if s]
    frames = sum(max(1, i["frames"] // i["step"]) for i in todo)
    print(f"{len(items)} items, {len(todo)} to render, {frames} frames")
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"shards={json.dumps(used)}\n")
            f.write(f"any={'true' if used else 'false'}\n")


def render(shard):
    shards = json.loads((BUILD / "shards.json").read_text(encoding="utf-8"))
    items = {i["src"]: i for i in manifest()}
    have = assets()
    for src in shards[shard]:
        i = items[src]
        if done(i, have):
            continue
        work = BUILD / "work" / src
        sh(BLENDER, "-b", "--factory-startup", "--python-exit-code", 1, "-P", ROOT / "blender" / "render.py", "--", "--shot", src,
           "--frames", i["frames"], "--out", work, "--step", i["step"], "--samples", i["samples"], stdout=subprocess.DEVNULL)
        files = []
        if i["still"]:
            f = BUILD / f"{i['key']}.jpg"
            shutil.copy(next(work.glob("f*.jpg")), f)
            files.append(f)
        else:
            f = BUILD / f"{i['key']}.mp4"
            encode(work, f, i)
            files.append(f)
        a = work / "anchors.json"
        if a.exists():
            f2 = BUILD / f"{i['key']}.json"
            shutil.copy(a, f2)
            files.insert(0, f2)
        # The clip uploads last: its presence is what marks the shot as done.
        for x in files:
            sh("gh", "release", "upload", TAG, x, "--clobber")
        shutil.rmtree(work)


def encode(work, dest, i):
    frames = sorted(work.glob("f*.jpg"))
    lst = work / "seq"
    lst.mkdir(exist_ok=True)
    for n, f in enumerate(frames):
        os.link(f, lst / f"{n:05d}.jpg")
    fps = 24 / i["step"]
    vf = ["fps=24"] if i["step"] == 1 else ["minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"]
    sh("ffmpeg", "-y", "-v", "error", "-framerate", fps, "-i", lst / "%05d.jpg", "-vf", ",".join(vf + ["format=yuv420p"]),
       "-frames:v", i["frames"], "-c:v", "libx264", "-preset", "medium", "-crf", 14, dest)


def fetch():
    items = manifest()
    for d in ("bg", "plates", "anchors"):
        (BUILD / d).mkdir(parents=True, exist_ok=True)
    tmp = BUILD / "dl"
    tmp.mkdir(exist_ok=True)
    have = assets()
    want = [f"{i['key']}{e}" for i in items for e in (".mp4", ".jpg", ".json") if f"{i['key']}{e}" in have]
    missing = [i["src"] for i in items if not done(i, have)]
    if missing:
        sys.exit("not rendered: " + ", ".join(missing))
    for n in want:
        sh("gh", "release", "download", TAG, "--pattern", n, "--dir", tmp, "--clobber")
    for i in items:
        k = i["key"]
        if i["still"]:
            shutil.move(tmp / f"{k}.jpg", BUILD / "plates" / f"{i['src']}.jpg")
        else:
            shutil.move(tmp / f"{k}.mp4", BUILD / "bg" / f"{i['src']}.mp4")
        j = tmp / f"{k}.json"
        if j.exists():
            shutil.move(j, BUILD / "anchors" / f"{i['src']}.json")
    for s in (ROOT / "assets" / "stock").glob("*.mp4"):
        shutil.copy(s, BUILD / "bg" / s.name)


def finish():
    tl = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    sh(sys.executable, ROOT / "tools" / "captions.py")
    sh(sys.executable, ROOT / "tools" / "mix.py")
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file 'seg/{s['id']}.mp4'\n" for s in tl["shots"]), encoding="utf-8")
    sh("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", BUILD / "picture.mp4")
    dest = ROOT / "output"
    dest.mkdir(exist_ok=True)
    grade = "noise=alls=2:allf=t,vignette=angle=PI/8"
    enc = ["-c:v", "libx264", "-preset", "slow", "-crf", 19, "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", 24,
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest"]
    for name, vf in (("stim-digital-twin-720p-captioned.mp4", f"{grade},ass=build/captions.ass:fontsdir=assets/fonts"),
                     ("stim-digital-twin-720p-clean.mp4", grade)):
        sh("ffmpeg", "-y", "-v", "error", "-i", BUILD / "picture.mp4", "-i", BUILD / "audio.wav", "-vf", vf, *enc, dest / name, cwd=ROOT)
        print(out("ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate:stream=codec_name,width,height,r_frame_rate",
                  "-of", "compact", dest / name))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "plan":
        plan(int(sys.argv[2]))
    elif cmd == "render":
        render(int(sys.argv[2]))
    elif cmd == "fetch":
        fetch()
    elif cmd == "finish":
        finish()

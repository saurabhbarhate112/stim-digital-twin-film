"""Turn the narration timings into the film's edit: every shot's frame range,
its source, and word cues, written to build/timeline.json.

kind 3d    rendered in Blender then interpolated (step = render every Nth frame)
kind plate one Blender still, moved and annotated in the compositor
kind stock trimmed footage from assets/stock
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 24
TEMPO = 1.04  # Pitch-preserving trim applied in the mix, so no line is re-voiced.
TARGET = 240.0
GAP = 0.32  # Breath between lines.
TAIL = 3.2  # Logo hold after the last word.

# (shot id, kind, source, line, first spoken words of the shot)
SHOTS = [
    ("line_wide", "3d", "line_wide", "hook", "right now"),
    ("paste_macro", "3d", "paste_macro", "hook", "you can't see it"),
    ("aoi_pass", "3d", "aoi_pass", "hook", "the inspection camera"),
    ("fail_clock", "plate", "plate_chip", "hook", "and in a few hours"),
    ("question", "plate", "plate_chip", "hook", "so how do you catch"),
    ("twin_reveal", "3d", "twin_reveal", "hook", "you build a second"),
    ("cockpit", "stock", "cockpit", "flight", "pilots"),
    ("cockpit2", "stock", "cockpit2", "flight", "in there"),
    ("twin_orbit", "3d", "twin_orbit", "flight", "a digital twin is"),
    ("board_twin", "3d", "board_twin", "mirror", "but it isn't"),
    ("map_phone", "3d", "map_phone", "mirror", "a paper map"),
    ("board_feed", "3d", "board_feed", "mirror", "a twin is the traffic"),
    ("line_change", "plate", "plate_line", "mirror", "when the line"),
    ("line_track", "3d", "line_track", "print", "follow one board"),
    ("paste_spheres", "3d", "paste_spheres", "print", "first solder paste"),
    ("squeegee", "3d", "squeegee", "print", "a squeegee drives"),
    ("spi_scan", "3d", "spi_scan", "print", "and each deposit"),
    ("pnp_wide", "3d", "pnp_wide", "place", "next pick"),
    ("pnp_macro", "3d", "pnp_macro", "place", "some boards take"),
    ("oven_cut", "3d", "oven_cut", "reflow", "then the reflow"),
    ("melt", "3d", "melt", "reflow", "near 217"),
    ("joint_macro", "3d", "joint_macro", "reflow", "then it cools"),
    ("profile", "plate", "plate_oven", "reflow", "every zone's"),
    ("aoi_cam", "3d", "aoi_cam", "inspect", "finally"),
    ("xray", "3d", "xray", "inspect", "x-rays"),
    ("test_probe", "3d", "test_probe", "inspect", "and an electrical"),
    ("diaries", "plate", "plate_line", "diaries", "data was never"),
    ("diary_trace", "plate", "plate_twin", "diaries", "the twin lines"),
    ("dashboard", "plate", "plate_twin", "forecast", "on its own"),
    ("ml_pattern", "plate", "plate_line", "forecast", "machine learning"),
    ("aperture_dry", "3d", "aperture_dry", "drift", "paste is drying"),
    ("drift_chart", "plate", "plate_line", "drift", "each board is still"),
    ("xray_weak", "plate", "xray_weak", "drift", "and weak joints"),
    ("flag_chart", "plate", "plate_twin", "drift", "but the twin"),
    ("wipe", "3d", "wipe", "drift", "an operator"),
    ("clean_deposit", "3d", "clean_deposit", "drift", "and that bad"),
    ("aoi_grid", "plate", "plate_chip", "aoi", "inspection gets"),
    ("inspector", "stock", "inspector", "aoi", "a trained inspector"),
    ("q_twin", "plate", "plate_twin", "whatif", "a twin can also"),
    ("cost_compare", "plate", "plate_line", "whatif", "on a live line"),
    ("heatmap", "3d", "heatmap", "whatif", "a twin that models"),
    ("shortlist", "plate", "plate_twin", "whatif", "engineers still"),
    ("nozzle_drop", "3d", "nozzle_drop", "nozzle", "same with"),
    ("reject_chart", "plate", "plate_chip", "nozzle", "one extra reject"),
    ("schedule", "plate", "plate_line", "nozzle", "the twin does"),
    ("silo", "plate", "plate_line", "limits", "none of this"),
    ("engineer", "stock", "engineer", "limits", "and an engineer"),
    ("nist", "plate", "plate_twin", "limits", "the standards"),
    ("ordinary", "3d", "ordinary", "close", "here's the strange"),
    ("no_items", "plate", "plate_line", "close", "no scrap"),
    ("final_pull", "3d", "final_pull", "close", "the most valuable"),
]

# Captions keep the written form of words the voice spells differently.
SHOW = {"4,812": "4,812"}


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))


def main():
    cfg = json.loads((ROOT / "script" / "narration.json").read_text(encoding="utf-8"))
    lines = [json.loads((ROOT / "assets" / "vo" / f"{l['id']}.json").read_text(encoding="utf-8")) for l in cfg["lines"]]
    speech = sum(l["duration"] for l in lines) / TEMPO
    gap = max(0.2, (TARGET - TAIL - 0.5 - speech) / (len(lines) - 1))
    print(f"speech {speech:.1f}s, gap {gap:.2f}s")

    cursor = 0.5
    words = []
    starts = {}
    for ln in lines:
        starts[ln["id"]] = cursor
        for i, w in enumerate(ln["words"]):
            words.append({"line": ln["id"], "i": i, "w": w["w"], "s": cursor + w["s"] / TEMPO, "e": cursor + w["e"] / TEMPO})
        cursor += ln["duration"] / TEMPO + gap
    total = cursor - gap + TAIL
    total_frames = round(total * FPS)

    def find(line, phrase):
        toks = [norm(t) for t in phrase.split()]
        lw = [w for w in words if w["line"] == line]
        for i in range(len(lw) - len(toks) + 1):
            if all(norm(lw[i + j]["w"]).startswith(toks[j]) or norm(lw[i + j]["w"]) == toks[j] for j in range(len(toks))):
                return lw[i]["s"]
        raise SystemExit(f"cue not found: {line}: {phrase}")

    cuts = []
    seen = set()
    for sid, kind, src, line, phrase in SHOTS:
        t = find(line, phrase) - (0.12 if line in seen else gap * 0.6)
        seen.add(line)
        cuts.append(max(0.0, t))
    cuts[0] = 0.0
    frames = [round(t * FPS) for t in cuts] + [total_frames]

    out = []
    for i, (sid, kind, src, line, phrase) in enumerate(SHOTS):
        a, b = frames[i], frames[i + 1]
        out.append({"id": sid, "kind": kind, "src": src, "line": line, "start": a, "frames": b - a,
                    "words": [{"w": w["w"], "f": round(w["s"] * FPS) - a} for w in words if a <= w["s"] * FPS < b]})
    data = {"fps": FPS, "tempo": TEMPO, "total": total_frames, "shots": out, "words": words,
            "lines": [{"id": l["id"], "start": starts[l["id"]]} for l in lines]}
    dest = ROOT / "build" / "timeline.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(data), encoding="utf-8")
    print(f"total {total:.2f}s, {total_frames} frames, {len(out)} shots, avg {total / len(out):.1f}s")
    print(f"3D frames at step 2: {sum(s['frames'] for s in out if s['kind'] == '3d') // 2}")
    for s in out:
        print(f"  {s['start'] / FPS:6.1f}  {s['frames'] / FPS:5.1f}s {s['kind']:5} {s['id']}")


if __name__ == "__main__":
    main()

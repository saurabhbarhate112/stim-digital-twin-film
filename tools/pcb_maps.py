"""Bake the board's copper / silkscreen / via masks into one PNG the shader reads.

R = copper under solder mask, G = silkscreen, B = drilled holes and via annulus.
Two maps: the full board, and a 4x sharper patch around U1 for macro shots.
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "blender"))
import layout  # noqa: E402

OUT = ROOT / "build" / "maps"
FONT = ROOT / "assets" / "fonts" / "IBMPlexMono-SemiBold.ttf"


def bake(data, name, cx, cy, span_w, span_h, px_w):
    scale = px_w / span_w
    px_h = round(span_h * scale)
    size = (px_w, px_h)

    def P(x, y):
        return (x - cx + span_w / 2) * scale, (span_h / 2 - (y - cy)) * scale

    copper = Image.new("L", size, 0)
    silk = Image.new("L", size, 0)
    holes = Image.new("L", size, 0)
    c, s, h = ImageDraw.Draw(copper), ImageDraw.Draw(silk), ImageDraw.Draw(holes)

    # Ground pour on every margin, with a clearance halo round pads and traces.
    pour = Image.new("L", size, 150)
    pd = ImageDraw.Draw(pour)
    for t in data["traces"]:
        pd.line([P(*q) for q in t["pts"]], fill=0, width=max(1, round((t["w"] + 0.5) * scale)), joint="curve")
    for p in data["pads"]:
        x0, y0 = P(p["x"] - p["w"] / 2 - 0.35, p["y"] + p["h"] / 2 + 0.35)
        x1, y1 = P(p["x"] + p["w"] / 2 + 0.35, p["y"] - p["h"] / 2 - 0.35)
        pd.rectangle((x0, y0, x1, y1), fill=0)
    copper.paste(pour)
    c = ImageDraw.Draw(copper)
    for t in data["traces"]:
        c.line([P(*q) for q in t["pts"]], fill=255, width=max(1, round(t["w"] * scale)), joint="curve")

    for x, y in data["vias"]:
        px, py = P(x, y)
        r, d = 0.32 * scale, 0.16 * scale
        c.ellipse((px - r, py - r, px + r, py + r), fill=255)
        h.ellipse((px - d, py - d, px + d, py + d), fill=255)
    for x, y in data["holes"]:
        px, py = P(x, y)
        r = 1.6 * scale
        h.ellipse((px - r, py - r, px + r, py + r), fill=255)
        s.ellipse((px - 3.0 * scale, py - 3.0 * scale, px + 3.0 * scale, py + 3.0 * scale), outline=255, width=round(0.15 * scale))

    font = ImageFont.truetype(str(FONT), round(1.25 * scale))
    tiny = ImageFont.truetype(str(FONT), round(0.85 * scale))

    def outline(x, y, w, d):
        x0, y0 = P(x - w / 2, y + d / 2)
        x1, y1 = P(x + w / 2, y - d / 2)
        s.rectangle((x0, y0, x1, y1), outline=255, width=max(1, round(0.14 * scale)))

    for part in data["parts"]:
        kind, ref = part["kind"], part["ref"]
        x, y = part["x"], part["y"]
        if kind == "qfn":
            outline(x, y, 6.6, 6.6)
            px, py = P(x - 4.0, y + 3.9)
            r = 0.35 * scale
            s.ellipse((px - r, py - r, px + r, py + r), fill=255)
            s.text(P(x - 3.3, y + 5.6), ref, fill=255, font=font)
        elif kind == "tqfp":
            outline(x, y, 11.6, 11.6)
            s.text(P(x - 5.8, y + 8.8), ref, fill=255, font=font)
        elif kind == "soic":
            w, d = part["body"]
            outline(x, y, w + 0.6, d + 0.6)
            s.text(P(x - w / 2, y + 4.8), ref, fill=255, font=font)
        elif kind in ("crystal", "inductor", "elco"):
            s.text(P(x - 2.0, y + (4.2 if kind == "crystal" else 7.0)), ref, fill=255, font=font)
        elif kind == "chip" and part["pkg"] in ("0603", "0805", "1206"):
            s.text(P(x - 1.2, y + 2.0), ref[:4], fill=255, font=tiny)

    # Board markings; the unit serial matches the board named in the narration.
    s.text(P(-46.0, -21.0), "STIM", fill=255, font=ImageFont.truetype(str(FONT), round(3.4 * scale)))
    s.text(P(-46.0, -24.8), "SN 4812  REV C", fill=255, font=tiny)
    for x, y in data["fiducials"]:
        r = 2.0 * scale
        px, py = P(x, y)
        s.ellipse((px - r, py - r, px + r, py + r), outline=255, width=max(1, round(0.12 * scale)))

    copper = copper.filter(ImageFilter.GaussianBlur(0.6))
    Image.merge("RGB", (copper, silk, holes)).save(OUT / f"{name}.png", compress_level=1)
    print(name, size)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = layout.build()
    (OUT / "layout.json").write_text(json.dumps(data), encoding="utf-8")
    bake(data, "board", 0, 0, layout.BOARD_W, layout.BOARD_H, 8000)
    # Sharper patch around U1: 24 x 24 mm for the macro shots.
    bake(data, "detail", 31.0, -20.0, 24.0, 24.0, 4096)


if __name__ == "__main__":
    main()

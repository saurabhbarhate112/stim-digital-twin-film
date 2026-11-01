"""Extra baked textures: thermal-lag map, paper road map, traffic-app screen."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "maps"
MONO = str(ROOT / "assets" / "fonts" / "IBMPlexMono-SemiBold.ttf")


def heat():
    """Copper plus heavy parts, blurred: 1 = slowest to warm. Pure physics cartoon, not a simulation result."""
    r = Image.open(OUT / "board.png").getchannel("R").resize((1400, 980))
    d = ImageDraw.Draw(r)
    w = 14.0
    for x, y, rad in ((36, 8, 6), (37, 23, 5), (-38, 22, 4), (-6, 6, 7), (24, 14, 4)):
        px, py = (x + 50) * w, (35 - y) * w
        d.ellipse((px - rad * w, py - rad * w, px + rad * w, py + rad * w), fill=255)
    # The heavy ground plane the narration names, under the power section.
    d.rectangle(((10 + 50) * w, (35 - 30) * w, (46 + 50) * w, (35 - 2) * w), fill=235)
    r = r.filter(ImageFilter.GaussianBlur(48)).point(lambda v: int(v * 0.55))
    r.save(OUT / "heat.png")


ROADS = [(120, 300, 1900, 240), (300, 60, 380, 1400), (700, 40, 760, 1400), (1200, 40, 1140, 1400),
         (1650, 40, 1720, 1400), (60, 760, 2000, 820), (60, 1120, 2000, 1060), (60, 520, 2000, 480)]
HIGHWAY = [(0, 980), (500, 930), (1000, 960), (1500, 890), (2048, 910)]


def paper_map():
    im = Image.new("RGB", (2048, 1448), (236, 226, 202))
    d = ImageDraw.Draw(im)
    rng = random.Random(3)
    for _ in range(26):
        x, y = rng.randint(0, 1900), rng.randint(0, 1300)
        d.rectangle((x, y, x + rng.randint(80, 240), y + rng.randint(60, 200)), fill=(207, 222, 184))
    d.line([(1450, 0), (1400, 500), (1560, 900), (1500, 1448)], fill=(170, 205, 226), width=46)
    for a in ROADS:
        d.line(a, fill=(255, 255, 250), width=20)
        d.line(a, fill=(214, 198, 168), width=2)
    d.line(HIGHWAY, fill=(238, 176, 60), width=30, joint="curve")
    d.line(HIGHWAY, fill=(205, 130, 30), width=3, joint="curve")
    font = ImageFont.truetype(MONO, 38)
    d.rounded_rectangle((470, 880, 560, 930), 8, fill=(255, 255, 255), outline=(60, 60, 60), width=3)
    d.text((484, 882), "401", fill=(30, 30, 30), font=font)
    d.text((1040, 700), "KEELE ST", fill=(120, 110, 96), font=ImageFont.truetype(MONO, 24))
    for x in (682, 1365):
        d.line((x, 0, x, 1448), fill=(214, 204, 180), width=4)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    im.save(OUT / "paper_map.png")


def phone_ui():
    im = Image.new("RGB", (700, 1500), (236, 240, 240))
    d = ImageDraw.Draw(im)
    for a in ROADS:
        pts = [(a[0] * 0.5 - 150, a[1] * 1.1 - 200), (a[2] * 0.5 - 150, a[3] * 1.1 - 200)]
        d.line(pts, fill=(255, 255, 255), width=18)
    hw = [(x * 0.5 - 150, y * 1.1 - 300) for x, y in HIGHWAY]
    d.line(hw, fill=(46, 196, 100), width=26, joint="curve")
    seg = hw[1:3]
    d.line(seg, fill=(226, 60, 50), width=26)
    d.line([hw[2], hw[3]], fill=(242, 160, 30), width=26)
    bold = ImageFont.truetype(MONO, 40)
    small = ImageFont.truetype(MONO, 28)
    d.rounded_rectangle((36, 60, 664, 280), 30, fill=(255, 255, 255))
    d.rounded_rectangle((64, 92, 136, 164), 16, fill=(226, 60, 50))
    d.text((88, 96), "!", fill=(255, 255, 255), font=bold)
    d.text((160, 88), "Traffic jam ahead", fill=(20, 30, 26), font=ImageFont.truetype(MONO, 36))
    d.text((160, 140), "401 E at Keele", fill=(80, 96, 88), font=small)
    d.text((64, 200), "Live, from phones nearby", fill=(8, 120, 68), font=small)
    d.ellipse((330, 830, 370, 870), fill=(47, 123, 239), outline=(255, 255, 255), width=6)
    d.rounded_rectangle((36, 1250, 664, 1440), 30, fill=(255, 255, 255))
    d.text((64, 1280), "+18 min", fill=(226, 60, 50), font=ImageFont.truetype(MONO, 54))
    d.text((64, 1356), "Faster route available", fill=(80, 96, 88), font=small)
    im.save(OUT / "phone_ui.png")


def hmi():
    """A plausible machine screen: state, a live trace and a parameter table."""
    im = Image.new("RGB", (960, 600), (9, 26, 21))
    d = ImageDraw.Draw(im)
    big, small = ImageFont.truetype(MONO, 34), ImageFont.truetype(MONO, 22)
    d.rectangle((0, 0, 960, 70), fill=(8, 120, 68))
    d.text((24, 14), "LINE 2   RUNNING", fill=(255, 255, 255), font=big)
    rng = random.Random(9)
    pts = [(40 + i * 8, 250 - int(50 * rng.random()) - i // 3) for i in range(70)]
    d.rectangle((24, 96, 600, 330), outline=(60, 110, 90), width=2)
    d.line(pts, fill=(44, 203, 127), width=4)
    for i, (k, v) in enumerate((("CYCLE", "28.4 s"), ("YIELD", "99.7 %"), ("BOARD", "4812"), ("ZONE 7", "245 C"))):
        d.text((630, 110 + i * 56), k, fill=(150, 190, 170), font=small)
        d.text((770, 104 + i * 56), v, fill=(255, 255, 255), font=small)
    for i in range(8):
        h = rng.randint(50, 170)
        d.rectangle((40 + i * 110, 570 - h, 110 + i * 110, 570), fill=(44, 203, 127) if i % 3 else (240, 170, 40))
    im.save(OUT / "hmi.png")


if __name__ == "__main__":
    hmi()
    heat()
    paper_map()
    phone_ui()
    print("textures ok")

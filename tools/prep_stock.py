"""One-off: trim the licensed Pexels originals to 720p24 clips kept in the repo.

Originals are not stored here. Sources and licences are listed in CREDITS.md.
Usage: python tools/prep_stock.py <folder-with-originals>
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "stock"
GRADE = "eq=contrast=1.05:saturation=1.06:gamma=1.04"
# name: (pexels id, start, length, speed, crop)
CLIPS = {
    "cockpit": ("38132855", 21.0, 5.0, 1.0, None),
    "cockpit2": ("38132855", 41.0, 5.0, 1.0, None),
    "inspector": ("2376866", 9.0, 4.5, 0.9, None),
    "engineer": ("39014670", 4.0, 5.5, 1.0, "crop=2160:1215:0:1320"),
}


def main():
    src = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (cid, ss, length, speed, crop) in CLIPS.items():
        vf = [f"setpts=PTS/{speed}"]
        if crop:
            vf.append(crop)
        vf += ["scale=1280:720:force_original_aspect_ratio=increase", "crop=1280:720", "fps=24", GRADE]
        subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-t", str(length * speed), "-i", str(src / f"{cid}.mp4"),
                               "-an", "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                               str(OUT / f"{name}.mp4")])
        print(name)


if __name__ == "__main__":
    main()

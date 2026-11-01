"""Captions from the spoken script and Speechify word timings: SRT, VTT and a styled ASS for burn-in.

Text comes from the script, so spelling and punctuation are exact; only the timing comes from the voice.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
MAX_CHARS = 44
MAX_SECS = 5.0


def tokens(ssml):
    return re.sub(r"<[^>]+>", " ", ssml).split()


def cues():
    cfg = json.loads((ROOT / "script" / "narration.json").read_text(encoding="utf-8"))
    tl = json.loads((ROOT / "build" / "timeline.json").read_text(encoding="utf-8"))
    result = []
    for line in cfg["lines"]:
        marks = [w for w in tl["words"] if w["line"] == line["id"]]
        toks = tokens(line["ssml"])
        if len(toks) != len(marks):
            raise SystemExit(f"{line['id']}: {len(toks)} script words, {len(marks)} timed words")
        cur = []
        for tok, m in zip(toks, marks):
            cur.append((tok, m["s"], m["e"]))
            text = " ".join(t for t, *_ in cur)
            ends_sentence = tok[-1] in ".?!"
            soft = tok[-1] in ",:" and len(text) > 24
            nxt = len(text) >= MAX_CHARS - 8
            if ends_sentence or soft or nxt or cur[-1][2] - cur[0][1] > MAX_SECS:
                result.append((cur[0][1], cur[-1][2], text))
                cur = []
        if cur:
            result.append((cur[0][1], cur[-1][2], " ".join(t for t, *_ in cur)))
    # Hold each caption until the next begins, within reason, so it can be read.
    fixed = []
    for i, (s, e, t) in enumerate(result):
        nxt = result[i + 1][0] if i + 1 < len(result) else e + 1.5
        fixed.append((s, min(max(e + 0.25, s + 1.0), nxt - 0.02), t))
    return fixed


def stamp(t, sep):
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def ass_time(t):
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DM Sans,29,&H00FFFFFF,&H00FFFFFF,&H40201A0D,&H40201A0D,0,0,0,0,100,100,0.2,0,3,9,0,2,120,120,26,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main():
    OUT.mkdir(exist_ok=True)
    cs = cues()
    srt = "\n".join(f"{i + 1}\n{stamp(s, ',')} --> {stamp(e, ',')}\n{t}\n" for i, (s, e, t) in enumerate(cs))
    vtt = "WEBVTT\n\n" + "\n".join(f"{stamp(s, '.')} --> {stamp(e, '.')}\n{t}\n" for s, e, t in cs)
    ass = ASS_HEAD + "".join(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{t}\n" for s, e, t in cs)
    (OUT / "stim-digital-twin.srt").write_text(srt, encoding="utf-8")
    (OUT / "stim-digital-twin.vtt").write_text(vtt, encoding="utf-8")
    (ROOT / "build" / "captions.ass").write_text(ass, encoding="utf-8")
    print(f"{len(cs)} captions, longest {max(len(t) for *_, t in cs)} chars")


if __name__ == "__main__":
    main()

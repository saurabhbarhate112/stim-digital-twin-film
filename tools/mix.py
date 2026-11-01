"""Final sound mix: tempo-trimmed narration, music ducked under the voice, sparse SFX.

Writes build/audio.wav at 48 kHz stereo, normalised to -14 LUFS for YouTube and LinkedIn.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
SFX = ROOT / "assets" / "sfx"
MUSIC = ROOT / "assets" / "music" / "inspiring_cinematic_ambient.mp3"
SPLICE = 126.0  # The track is 190 s; repeat its middle so its real ending lands on the logo.


def ff(*args):
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", *map(str, args)])


def cue_table(tl):
    shot = {s["id"]: s for s in tl["shots"]}
    fps = tl["fps"]

    def at(sid, offset=0.0):
        return shot[sid]["start"] / fps + offset

    def word(sid, w, n=1):
        seen = 0
        for x in shot[sid]["words"]:
            if x["w"].lower().strip(".,?!").startswith(w):
                seen += 1
                if seen == n:
                    return at(sid) + x["f"] / fps
        return at(sid)

    cues = [
        (at("paste_macro"), "tech_slide", -18),
        (at("aoi_pass", 0.45), "ui_click", -20), (at("aoi_pass", 0.9), "ui_click", -21),
        (at("aoi_pass", 1.35), "ui_click", -22), (at("aoi_pass", 1.8), "ui_click", -21),
        (at("fail_clock"), "quick_glitch", -22),
        (at("question"), "air_woosh", -22),
        (word("twin_reveal", "second") - 0.5, "power_up", -14),
        (at("twin_orbit"), "deep_impact", -19),
        (at("board_twin"), "fast_whoosh", -20),
        (at("board_feed"), "computer_calc", -24),
        (at("paste_spheres"), "air_woosh", -21),
        (at("spi_scan"), "tech_select", -22),
        (at("pnp_wide"), "tech_slide", -20),
        (at("oven_cut"), "air_woosh", -21),
        (at("melt", 3.2), "tech_select", -21),
        (at("xray"), "bleep", -24),
        (at("test_probe", 1.7), "bleep_confirm", -21),
        (at("diary_trace"), "fast_whoosh", -21),
        (at("drift_chart"), "tech_slide", -21),
        (at("xray_weak"), "device_fail", -21),
        (word("flag_chart", "flags"), "tech_alert", -18),
        (at("clean_deposit"), "bleep_confirm", -19),
        (at("q_twin"), "computer_calc", -24),
        (at("cost_compare"), "tech_slide", -21),
        (at("heatmap"), "air_woosh", -22),
        (at("nozzle_drop", 1.9), "negative_tap", -20),
        (at("schedule"), "tech_slide", -21),
        (at("nist"), "air_woosh", -22),
        (word("no_items", "scrap"), "ui_click", -18), (word("no_items", "alarm"), "ui_click", -18),
        (word("no_items", "investigation"), "ui_click", -18),
        (tl["total"] / fps - 2.7, "logo_impact", -7),
    ]
    # Machine hum under the factory shots gives the room a sense of place.
    beds = [(at(s), shot[s]["frames"] / fps) for s in ("line_wide", "line_track", "pnp_wide", "ordinary") ]
    return cues, beds


def main():
    tl = json.loads((BUILD / "timeline.json").read_text(encoding="utf-8"))
    total = tl["total"] / tl["fps"]
    cfg = json.loads((ROOT / "script" / "narration.json").read_text(encoding="utf-8"))
    tempo = tl["tempo"]

    inputs, parts = [], []
    for i, line in enumerate(tl["lines"]):
        inputs += ["-i", ROOT / "assets" / "vo" / f"{line['id']}.mp3"]
        ms = round(line["start"] * 1000)
        parts.append(f"[{i}:a]aresample=48000,atempo={tempo},adelay={ms}:all=1[v{i}]")
    fc = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(len(tl["lines"])))
    fc += f"amix=inputs={len(tl['lines'])}:normalize=0,highpass=f=70,equalizer=f=3200:t=q:w=1.2:g=2,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,aformat=channel_layouts=stereo[o]"
    ff(*inputs, "-filter_complex", fc, "-map", "[o]", "-ar", 48000, "-t", total, BUILD / "voice.wav")

    dur = ffprobe(MUSIC)
    second = total - SPLICE + 6
    ff("-i", MUSIC, "-filter_complex",
       f"[0:a]atrim=0:{SPLICE},asetpts=PTS-STARTPTS[a];[0:a]atrim={dur - second}:{dur},asetpts=PTS-STARTPTS[b];"
       f"[a][b]acrossfade=d=6:c1=qsin:c2=qsin,aresample=48000,aformat=channel_layouts=stereo,"
       f"afade=t=in:d=2.0,afade=t=out:st={total - 2.5}:d=2.5[o]",
       "-map", "[o]", "-t", total, BUILD / "music.wav")

    cues, beds = cue_table(tl)
    inputs, parts = [], []
    for i, (t, name, gain) in enumerate(cues):
        inputs += ["-i", SFX / f"{name}.mp3"]
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,adelay={round(t * 1000)}:all=1[s{i}]")
    n = len(cues)
    for j, (t, d) in enumerate(beds):
        inputs += ["-stream_loop", "-1", "-i", SFX / "machine_hum.mp3"]
        k = n + j
        parts.append(f"[{k}:a]atrim=0:{d},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume=-29dB,"
                     f"afade=t=in:d=0.5,afade=t=out:st={max(0, d - 0.7)}:d=0.7,adelay={round(t * 1000)}:all=1[s{k}]")
    count = n + len(beds)
    fc = ";".join(parts) + ";" + "".join(f"[s{i}]" for i in range(count)) + f"amix=inputs={count}:normalize=0[o]"
    ff(*inputs, "-filter_complex", fc, "-map", "[o]", "-t", total, BUILD / "sfx.wav")

    fc = ("[1:a]volume=-17dB[m];[0:a]volume=6dB,asplit=2[vk][vm];"
          "[m][vk]sidechaincompress=threshold=0.04:ratio=5:attack=40:release=450:makeup=1[md];"
          "[vm][md][2:a]amix=inputs=3:normalize=0,alimiter=limit=0.93[o]")
    ff("-i", BUILD / "voice.wav", "-i", BUILD / "music.wav", "-i", BUILD / "sfx.wav", "-filter_complex", fc,
       "-map", "[o]", "-ar", 48000, BUILD / "premaster.wav")
    ff("-i", BUILD / "premaster.wav", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", 48000, BUILD / "audio.wav")
    print("audio ok", round(ffprobe(BUILD / "audio.wav"), 2))


def ffprobe(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).decode())


if __name__ == "__main__":
    main()

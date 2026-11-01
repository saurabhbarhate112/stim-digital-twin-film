"""Synthesize one Speechify clip per script line, keeping word timings.

Each clip is cached under assets/vo/<id>.mp3 + .json, keyed by a hash of its
SSML, voice, model and rate, so an unchanged line never spends another credit.

Key comes from the SPEECHIFY_API_KEY environment variable (a GitHub Secret in
CI) or a local, git-ignored .env file.

Usage: python tools/narrate.py [line-id ...]
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "vo"
URL = "https://api.sws.speechify.com/v1/audio/speech"


def api_key():
    key = os.environ.get("SPEECHIFY_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("SPEECHIFY_API_KEY"):
                key = line.split("=", 1)[1].strip().strip('"')
    if not key:
        sys.exit("SPEECHIFY_API_KEY is not set")
    return key


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(path)])
    return float(out.decode().strip())


def main():
    cfg = json.loads((ROOT / "script" / "narration.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    key = None
    for line in cfg["lines"]:
        if only and line["id"] not in only:
            continue
        rate = line.get("rate", cfg["rate"])
        sig = hashlib.sha256(json.dumps([line["ssml"], cfg["voice_id"], cfg["model"], rate]).encode()).hexdigest()[:16]
        mp3, meta = OUT / f"{line['id']}.mp3", OUT / f"{line['id']}.json"
        if mp3.exists() and meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("sig") == sig:
            continue
        key = key or api_key()
        body = {"input": f'<speak><prosody rate="{rate}">{line["ssml"]}</prosody></speak>',
                "voice_id": cfg["voice_id"], "model": cfg["model"], "audio_format": "mp3",
                "loudness_normalization": True}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            res = json.load(urllib.request.urlopen(req, timeout=180))
        except urllib.error.HTTPError as err:
            sys.exit(f"{line['id']}: HTTP {err.code} {err.read()[:300]!r}")
        mp3.write_bytes(base64.b64decode(res["audio_data"]))
        words = [{"w": c["value"], "s": c["start_time"] / 1000, "e": c["end_time"] / 1000}
                 for c in res["speech_marks"]["chunks"] if c.get("type") == "word"]
        meta.write_text(json.dumps({"id": line["id"], "sig": sig, "duration": duration(mp3), "words": words}, indent=1),
                        encoding="utf-8")
        print(f"{line['id']}: {duration(mp3):.2f}s, {len(words)} words, {res.get('billable_characters_count')} chars")

    done = [json.loads((OUT / f"{l['id']}.json").read_text(encoding="utf-8")) for l in cfg["lines"]
            if (OUT / f"{l['id']}.json").exists()]
    print(f"{len(done)}/{len(cfg['lines'])} lines, {sum(d['duration'] for d in done):.1f}s of speech")
    planned = sum(len(re.sub(r"<[^>]+>", " ", l["ssml"]).split()) for l in cfg["lines"])
    print(f"script: {planned} words")


if __name__ == "__main__":
    main()

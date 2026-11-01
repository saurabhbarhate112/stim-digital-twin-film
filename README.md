# STIM digital twin film

A four-minute, 720p documentary built from code: procedural Blender 3D, canvas motion graphics, Speechify narration, rendered on GitHub Actions.

## Render

```bash
gh workflow run render.yml
```

The finished MP4s and captions appear on a private release named `film-<run>`.

`SPEECHIFY_API_KEY` is only needed if a line of `script/narration.json` changes. Existing narration is cached in `assets/vo`. To set it:

```bash
gh secret set SPEECHIFY_API_KEY
```

## How it fits together

| Step | Source | Result |
|---|---|---|
| Script | `script/narration.json` | one clip per line in `assets/vo`, cached by text hash |
| Edit | `tools/timeline.py` | every cut timed to the spoken word |
| 3D | `blender/shots.py` | one clip per shot, cached on the `render-cache` release |
| Graphics | `compositor/overlays.js` | labels and charts, one function per shot |
| Sound and captions | `tools/mix.py`, `tools/captions.py` | ducked mix at -14 LUFS, SRT and VTT |
| Delivery | `tools/ci.py` | captioned and clean MP4 |

## Changing things cheaply

- Change a shot in `blender/shots.py`: only that shot re-renders.
- Change labels or charts in `compositor/overlays.js`: no 3D re-renders.
- Change one script line: one line re-voices, and the affected cuts re-time.
- Changes to `blender/lib.py`, `pcb.py`, `machines.py` or `twin.py` invalidate all 3D, so test those first with `tools/qa.ps1`.

Local test frames need Blender 4.5 in `build/`. Final rendering belongs on Actions.

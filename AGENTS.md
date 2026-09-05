# Reels Agent

This repository turns raw vertical footage into a publishable Reel: transcript,
dead-air removal, word-level captions, and a hook placed where the platform
will not crop it.

**The full working instructions live in
[`skills/reels-editor/SKILL.md`](skills/reels-editor/SKILL.md). Read that file
before editing any video — it defines the stages, the questions to ask, and the
rules you must not break.**

## Quick orientation

| Stage | Script |
|---|---|
| Detect what this machine can do | `skills/reels-editor/scripts/check_env.py` |
| Transcribe with word timestamps | `skills/reels-editor/scripts/transcribe.py` |
| Cut pauses, remap caption timings | `skills/reels-editor/scripts/cut_silence.py` |
| Burn captions (ASS or Remotion) | `skills/reels-editor/scripts/burn_captions.py` |
| Place the hook in the safe zone | `skills/reels-editor/scripts/hook_overlay.py` |
| Measure a reference Reel | `skills/reels-editor/scripts/analyze_reference.py` |

Run `check_env.py` first. It reports whether you are in `light` mode (ffmpeg
with libass) or `openmontage` mode, and refuses to proceed if something
essential is missing.

## Rules you must not break

1. **Never publish.** Hand the file over; posting is the user's decision.
2. **Never render the final without showing a preview first.**
3. **Never invent facts** — dates, names, prices. Ask.
4. **Never place text outside `y 480…1350`** — the profile grid crops 240 px off
   the top and bottom of a 1080×1920 frame.
5. **Always verify audio** — target −14 LUFS, peak below −1 dBFS.
6. **Always read proper nouns back to the user.** Whisper mangles names.

## User profile

Style, pacing, goals and past results live in `profiles/user.json`
(schema: `profiles/example.json`). Read it before editing; update it after
every delivered Reel. That file is what makes the agent improve.

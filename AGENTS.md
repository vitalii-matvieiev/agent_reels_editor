# Reels Agent

This repository turns raw vertical footage into a publishable Reel: transcript,
dead-air removal, word-level captions, and a hook placed where the platform
will not crop it.

**The full working instructions live in
[`skills/matvieiev-agent_reels-editor/SKILL.md`](skills/matvieiev-agent_reels-editor/SKILL.md). Read that file
before editing any video — it defines the stages, the questions to ask, and the
rules you must not break.**

## Quick orientation

| Stage | Script |
|---|---|
| Detect what this machine can do | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/check_env.py` |
| Transcribe with word timestamps | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/transcribe.py` |
| Cut pauses, remap caption timings | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/cut_silence.py` |
| Burn captions (ASS or Pillow) | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/burn_captions.py` |
| Place the hook in the safe zone | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/hook_overlay.py` |
| Measure a reference Reel | `skills/matvieiev-agent_matvieiev-agent_reels-editor/scripts/analyze_reference.py` |

Run `check_env.py` first. It reports whether you are in `light` mode (ffmpeg
with libass) or `standalone` mode (captions drawn with Pillow). Both produce
the same result; nothing extra needs installing either way.

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

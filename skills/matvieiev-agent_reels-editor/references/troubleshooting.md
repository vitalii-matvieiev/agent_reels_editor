# Troubleshooting

## ffmpeg has no libass

**Symptom:** `No such filter: 'ass'` or `No such filter: 'subtitles'`.

**Check:**

```bash
ffmpeg -hide_banner -filters | grep -E "^ .. (ass|subtitles) "
```

Some Homebrew builds ship without `libass`, `libfreetype` and `fontconfig` —
the build that produced this plugin was one of them. Without them ffmpeg cannot
burn subtitles or draw text at all.

**This is handled automatically.** `check_env.py` detects the missing filter
and switches to `standalone` mode, where `render_captions_png.py` draws the
caption strip with Pillow and ffmpeg composites it with `overlay`. Same result,
nothing to install.

If you would rather have libass anyway: `brew reinstall ffmpeg`, then verify
with the check above.

## Whisper mangles proper nouns

Names, brands and place names are the least reliable part of any transcript.
Real example from this plugin's own build: **«Дмитром» → «Митром»**, in an
announcement post naming a guest.

Always read names back to the user. Store fixes in the profile's `corrections`
map so the same name is never wrong twice.

Non-words are the other tell — «речуємося» is not Ukrainian; in context it was
«харчуємося». If a word does not exist, it is a misrecognition, not a coinage.

## Captions drift after cutting

**Cause:** the video was cut but subtitle timings were not remapped.

`cut_silence.py` writes `transcript_tight.json` for exactly this. Feed *that*
file to `burn_captions.py`, never the original `transcript.json`.

## Words run together in captions

**Symptom:** `невиходить.І` instead of `не виходить. І`.

**Cause:** `display: inline-block` collapses a trailing space in CSS-rendered
captions.

**Fix:** `white-space: pre` on the word span. In OpenMontage this lives in
`remotion-composer/src/components/CaptionOverlay.tsx`. This bug breaks captions
for every space-delimited language, not just Ukrainian.

## Transcription is slow

`large-v3` on CPU runs roughly 15–20× slower than real time — a one-minute clip
takes 15–20 minutes. Options:

- `--model medium` — noticeably faster, slightly worse on names
- Let it run in the background and do the audio and hook work meanwhile
- The 2.7 GB model downloads once and is cached

## Output file is huge

Do not hand over 4K. Platforms re-compress to 1080×1920 regardless, so a 257 MB
upload buys nothing over a 63 MB one at the same visible quality.

Target ~10–12 Mbit/s: `-crf 21 -maxrate 12M -bufsize 16M`.

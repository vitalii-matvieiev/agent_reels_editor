#!/usr/bin/env python3
"""Burns word-level captions. Picks ASS or Remotion depending on the machine.

    python burn_captions.py in.mp4 out.mp4 transcript.json [--profile ../../profiles/user.json]

Three words per screen, active word in the accent colour. Captions sit at 22%
of frame height from the bottom on vertical video — clear of the platform's
button column. See references/safe-zones.md for why.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tools  # noqa: E402
from _tools import FFMPEG, FFPROBE  # noqa: E402

_tools.reexec_in_venv()

from check_env import ffmpeg_filters, find_openmontage  # noqa: E402


WORDS_PER_PAGE = 3
DEFAULTS = {"accent": "#FFC93C", "text": "#FFFFFF", "font": "Arial Black", "font_size": 76}


def load_profile(path):
    path = path or _tools.profile_path()
    cfg = dict(DEFAULTS)
    if path and Path(path).exists():
        p = json.load(open(path))
        for k in ("accent", "text", "font", "font_size"):
            if p.get("style", {}).get(k):
                cfg[k] = p["style"][k]
        cfg["corrections"] = p.get("corrections", {})
    cfg.setdefault("corrections", {})
    return cfg


def apply_corrections(word, corrections):
    core = re.sub(r"[^\w'’-]", "", word, flags=re.UNICODE)
    for wrong, right in corrections.items():
        if core.lower() == wrong.lower():
            return word.replace(core, right)
    return word


def group_words(words):
    """Break on punctuation first, then on pauses, then at WORDS_PER_PAGE."""
    groups, cur = [], []
    for w in words:
        cur.append(w)
        last = w["word"].rstrip()[-1:]
        if last in ".?!…:" or (last == "," and len(cur) >= 2) or len(cur) >= WORDS_PER_PAGE:
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)

    out = []
    for g in groups:
        buf = [g[0]]
        for a, b in zip(g, g[1:]):
            if b["start"] - a["end"] > 0.7:
                out.append(buf); buf = []
            buf.append(b)
        if buf:
            out.append(buf)
    return [g for g in out if g]


def hex_to_ass(h):
    """ASS colour literal: &HAABBGGRR& — the trailing & is required, without it
    libass prints stray characters into the caption."""
    h = h.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}&"


def ts(x):
    h, m = int(x // 3600), int((x % 3600) // 60)
    return f"{h}:{m:02d}:{x % 60:05.2f}"


def build_ass(words, cfg, height, width, path):
    margin_v = round(height * 0.22) if height > width else 80
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{cfg['font']},{cfg['font_size']},{hex_to_ass(cfg["text"]).rstrip("&")},{hex_to_ass(cfg["text"]).rstrip("&")},&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,1,7,4,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    active, idle = f"{{\\c{hex_to_ass(cfg['accent'])}}}", f"{{\\c{hex_to_ass(cfg['text'])}}}"
    lines = []
    groups = group_words(words)
    for gi, g in enumerate(groups):
        # Hold the last word a moment longer — but never into the next group,
        # or libass stacks two captions on top of each other.
        gend = g[-1]["end"] + 0.12
        if gi + 1 < len(groups):
            gend = min(gend, groups[gi + 1][0]["start"] - 0.01)
        for i, _ in enumerate(g):
            st = g[i]["start"]
            en = g[i + 1]["start"] if i + 1 < len(g) else gend
            if en <= st:
                continue
            txt = " ".join((active if j == i else idle) + w["word"] for j, w in enumerate(g))
            lines.append(f"Dialogue: 0,{ts(st)},{ts(en)},Cap,,0,0,0,,{{\\fad(60,60)}}{txt}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def probe_fps(video):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", video],
        capture_output=True, text=True).stdout.strip()
    try:
        n, d = out.split("/")
        return round(int(n) / int(d))
    except Exception:
        return 30


def probe_duration(video):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", video],
        capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def probe_dims(video):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video],
        capture_output=True, text=True).stdout.strip()
    w, h = out.split("x")[:2]
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("output"); ap.add_argument("transcript")
    ap.add_argument("--profile", default=None)
    a = ap.parse_args()

    cfg = load_profile(a.profile)
    for f in (a.input, a.transcript):
        if not Path(f).exists():
            sys.exit(f"файлу немає: {f}\n"
                     "Субтитрам потрібне порізане відео і transcript_tight.json,\n"
                     "який лишає після себе cut_silence.py.")
    d = json.load(open(a.transcript, encoding="utf-8"))
    words = [{"word": apply_corrections(w["word"].strip(), cfg["corrections"]),
              "start": w["start"], "end": w["end"]}
             for s in d["segments"] for w in s["words"] if w["word"].strip()]
    if not words:
        sys.exit("transcript has no word timestamps — re-run transcribe.py")

    filters = ffmpeg_filters()
    if "ass" in filters or "subtitles" in filters:
        w, h = probe_dims(a.input)
        ass_path = Path(a.output).with_suffix(".ass")
        n = build_ass(words, cfg, h, w, ass_path)
        filt = "ass" if "ass" in filters else "subtitles"
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-i", a.input,
             "-vf", f"{filt}=f={ass_path}",
             "-c:v", "libx264", "-preset", "slow", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "copy",
             "-movflags", "+faststart", a.output], check=True)
        print(json.dumps({"method": "ass", "cues": n, "words": len(words),
                          "output": a.output}, indent=2))
        return

    # No libass: render the caption strip ourselves with Pillow and composite it.
    # This keeps the plugin self-contained — no OpenMontage, no AGPL code.
    try:
        from render_captions_png import render_sequence, STRIP_H
    except ImportError:
        render_sequence = None

    if render_sequence is not None:
        import shutil, tempfile
        w, h = probe_dims(a.input)
        fps = probe_fps(a.input)
        dur = probe_duration(a.input)
        groups = group_words(words)
        tmp = tempfile.mkdtemp(prefix="caps_")
        try:
            frames, uniq = render_sequence(groups, w, h, fps, dur, cfg, tmp)
            y = round(h * 0.78) - STRIP_H // 2 if h > w else h - STRIP_H - 60
            subprocess.run(
                [FFMPEG, "-v", "error", "-y", "-i", a.input,
                 "-framerate", str(fps), "-i", f"{tmp}/%06d.png",
                 "-filter_complex", f"[0:v][1:v]overlay=0:{y}:shortest=1[v]",
                 "-map", "[v]", "-map", "0:a?",
                 "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                 "-pix_fmt", "yuv420p", "-c:a", "copy",
                 "-movflags", "+faststart", a.output], check=True)
            print(json.dumps({"method": "pillow", "cues": len(groups),
                              "words": len(words), "frames": frames,
                              "unique_states": uniq, "output": a.output},
                             indent=2))
            return
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    om = find_openmontage()
    if not om:
        sys.exit("cannot render captions — Pillow missing and no OpenMontage")

    sys.path.insert(0, str(om))
    from tools.video.remotion_caption_burn import RemotionCaptionBurn  # noqa: E402
    res = RemotionCaptionBurn().execute({
        "input_path": str(Path(a.input).resolve()),
        "output_path": str(Path(a.output).resolve()),
        "segments": d["segments"],
        "words_per_page": WORDS_PER_PAGE,
        "font_size": cfg["font_size"],
        "highlight_color": cfg["accent"],
        "corrections": cfg["corrections"],
    })
    if not res.success:
        sys.exit(f"Remotion failed: {res.error}")
    print(json.dumps({"method": "remotion", **res.data}, indent=2))


if __name__ == "__main__":
    main()

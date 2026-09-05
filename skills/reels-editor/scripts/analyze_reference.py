#!/usr/bin/env python3
"""Measures a Reel the user already published and liked, so their style becomes numbers.

    python analyze_reference.py reference.mp4

A reference beats any verbal description of style. Reports pace, format,
loudness and where text sits — feed the result into profiles/user.json.
"""
import argparse
import json
import re
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def probe(video):
    out = run(["ffprobe", "-v", "error",
               "-show_entries", "format=duration,size,bit_rate",
               "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate",
               "-of", "json", video])
    return json.loads(out or "{}")


def shot_changes(video):
    """Average shot length — the single best proxy for pace."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", video, "-filter:v",
         "select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    return len(re.findall(r"pts_time:", out))


def loudness(video):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", video, "-map", "0:a",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    res = {}
    for key, pat in (("lufs", r"I:\s+(-?[\d.]+)\s+LUFS"),
                     ("lra", r"LRA:\s+(-?[\d.]+)\s+LU"),
                     ("peak_dbfs", r"Peak:\s+(-?[\d.]+)\s+dBFS")):
        m = re.findall(pat, out)
        if m:
            res[key] = float(m[-1])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    a = ap.parse_args()

    info = probe(a.video)
    fmt = info.get("format", {})
    vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    dur = float(fmt.get("duration", 0) or 0)
    w, h = vs.get("width", 0), vs.get("height", 0)

    cuts = shot_changes(a.video)
    loud = loudness(a.video)

    report = {
        "duration_s": round(dur, 2),
        "resolution": f"{w}x{h}",
        "vertical": h > w,
        "fps": vs.get("r_frame_rate"),
        "size_mb": round(int(fmt.get("size", 0)) / 1048576, 1),
        "cuts_detected": cuts,
        "avg_shot_s": round(dur / cuts, 2) if cuts else None,
        "audio": loud,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n--- як це читати ---")
    if report["avg_shot_s"]:
        s = report["avg_shot_s"]
        pace = "дуже швидкий" if s < 2 else "швидкий" if s < 4 else "спокійний"
        print(f"Темп: {pace} — середній план {s} с")
    else:
        print("Темп: один безперервний план, без склейок")
    if not report["vertical"]:
        print("УВАГА: референс горизонтальний — для Reels потрібна вертикаль 1080x1920")
    if loud.get("peak_dbfs", -99) > -0.5:
        print(f"УВАГА: пікі {loud['peak_dbfs']} dBFS — у референсі вже є кліпінг, не копіювати")
    if loud.get("lufs"):
        print(f"Гучність {loud['lufs']} LUFS (норма для соцмереж — близько -14)")
    print(f"Тривалість {report['duration_s']} с — цільова для нових рілсів")
    print("\nПерекажи ці цифри користувачу і запиши в profiles/user.json → reference.measured")


if __name__ == "__main__":
    main()

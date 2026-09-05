#!/usr/bin/env python3
"""Reports what this machine can actually do, and picks a captioning mode.

Run this before editing anything. Modes:
    light        ffmpeg with libass + faster-whisper — everything local, no extras
    openmontage  OpenMontage present — captions render through Remotion
    blocked      something essential is missing; the report says what
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def has_binary(name):
    return shutil.which(name) is not None


def ffmpeg_filters():
    """Which subtitle-capable filters this ffmpeg build actually has."""
    if not has_binary("ffmpeg"):
        return set()
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return set()
    found = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in ("ass", "subtitles", "drawtext"):
            found.add(parts[1])
    return found


def python_module(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def find_openmontage():
    for p in [Path.home() / "Projects/OpenMontage",
              Path.home() / "OpenMontage",
              Path.cwd() / "OpenMontage"]:
        if (p / "remotion-composer" / "node_modules").is_dir():
            return p
    return None


def main():
    filters = ffmpeg_filters()
    om = find_openmontage()

    report = {
        "ffmpeg": has_binary("ffmpeg"),
        "ffprobe": has_binary("ffprobe"),
        "ffmpeg_libass": "ass" in filters or "subtitles" in filters,
        "ffmpeg_drawtext": "drawtext" in filters,
        "faster_whisper": python_module("faster_whisper"),
        "pillow": python_module("PIL"),
        "openmontage_path": str(om) if om else None,
    }

    problems = []
    if not report["ffmpeg"] or not report["ffprobe"]:
        problems.append("ffmpeg/ffprobe not found — brew install ffmpeg")
    if not report["faster_whisper"]:
        problems.append("faster-whisper not installed — pip install faster-whisper")
    if not report["pillow"]:
        problems.append("Pillow not installed — pip install Pillow")

    if problems:
        mode = "blocked"
    elif report["ffmpeg_libass"]:
        mode = "light"
    elif om:
        mode = "openmontage"
    else:
        mode = "blocked"
        problems.append(
            "this ffmpeg has no libass and OpenMontage is not installed — "
            "captions cannot be burned. Either 'brew reinstall ffmpeg' or "
            "install OpenMontage: https://github.com/calesthio/OpenMontage"
        )

    report["mode"] = mode
    report["problems"] = problems

    print(json.dumps(report, indent=2))
    print()
    if mode == "light":
        print("MODE: light — ffmpeg burns ASS subtitles. Nothing else needed.")
    elif mode == "openmontage":
        print(f"MODE: openmontage — captions via Remotion at {om}")
        print("NOTE: this ffmpeg has no libass, so ASS subtitles are unavailable.")
    else:
        print("MODE: blocked — fix these before editing:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)


if __name__ == "__main__":
    main()

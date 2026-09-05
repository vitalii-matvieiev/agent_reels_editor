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


def plugin_config():
    """setup.py writes config.json with resolved paths — prefer them."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cfg = parent / "config.json"
        if cfg.exists():
            try:
                return json.loads(cfg.read_text()), parent
            except Exception:
                pass
        if (parent / "setup.py").exists():
            break
    return {}, None


CONFIG, PLUGIN_ROOT = plugin_config()


def has_binary(name):
    if CONFIG.get(name):
        return True
    if PLUGIN_ROOT and (PLUGIN_ROOT / "vendor" / name).exists():
        return True
    return shutil.which(name) is not None


def binary(name):
    """Full path to a tool — vendor copy first, then config, then PATH."""
    if PLUGIN_ROOT:
        local = PLUGIN_ROOT / "vendor" / name
        if local.exists():
            return str(local)
    return CONFIG.get(name) or shutil.which(name) or name


def ffmpeg_filters():
    """Which subtitle-capable filters this ffmpeg build actually has."""
    if not has_binary("ffmpeg"):
        return set()
    try:
        out = subprocess.run([binary("ffmpeg"), "-hide_banner", "-filters"],
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
    else:
        # No libass — captions render through Pillow instead. Self-contained,
        # nothing else to install.
        mode = "standalone"

    report["mode"] = mode
    report["problems"] = problems

    print(json.dumps(report, indent=2))
    print()
    if mode == "light":
        print("MODE: light — ffmpeg burns ASS subtitles. Nothing else needed.")
    elif mode == "standalone":
        print("MODE: standalone — this ffmpeg has no libass, so captions render")
        print("      through Pillow instead. Works the same; nothing to install.")
        if om:
            print(f"      (OpenMontage also found at {om}, but not required.)")
    else:
        print("MODE: blocked — fix these before editing:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)


if __name__ == "__main__":
    main()

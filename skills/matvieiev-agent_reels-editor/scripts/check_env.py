#!/usr/bin/env python3
"""Reports what this machine can actually do, and picks a captioning mode.

Run this before editing anything — with plain `python3`; it switches itself to
the plugin's own interpreter when there is one. Modes:
    light        ffmpeg with libass — captions burned as ASS subtitles
    standalone   no libass — captions drawn by Pillow, composited by ffmpeg
    blocked      something essential is missing; the report says what

The `python` field in the report is the interpreter every other script in this
folder should be run with.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tools  # noqa: E402

_tools.reexec_in_venv()


def has_binary(name):
    path = _tools.binary(name)
    return "/" in path and Path(path).exists()


def ffmpeg_filters():
    """Which subtitle-capable filters this ffmpeg build actually has."""
    if not has_binary("ffmpeg"):
        return set()
    try:
        out = subprocess.run([_tools.FFMPEG, "-hide_banner", "-filters"],
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
    if _tools.ROOT and (_tools.ROOT / "pro" / "OpenMontage" /
                        "remotion-composer" / "node_modules").is_dir():
        return _tools.ROOT / "pro" / "OpenMontage"
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
        "plugin_root": str(_tools.ROOT) if _tools.ROOT else None,
        "python": _tools.python_path() or sys.executable,
        "ffmpeg": has_binary("ffmpeg"),
        "ffprobe": has_binary("ffprobe"),
        "ffmpeg_path": _tools.FFMPEG,
        "ffmpeg_libass": "ass" in filters or "subtitles" in filters,
        "ffmpeg_drawtext": "drawtext" in filters,
        "faster_whisper": python_module("faster_whisper"),
        "pillow": python_module("PIL"),
        "profile": _tools.profile_path(),
        "openmontage_path": str(om) if om else None,
    }

    fix = "запусти в папці плагіна:  python3 setup.py"
    problems = []
    if not report["ffmpeg"] or not report["ffprobe"]:
        problems.append(f"немає ffmpeg/ffprobe — {fix}")
    if not report["faster_whisper"]:
        problems.append(f"немає faster-whisper — {fix}")
    if not report["pillow"]:
        problems.append(f"немає Pillow — {fix}")
    if problems and not report["plugin_root"]:
        problems.append("не знайшов папку плагіна — перевстанови через ./install.sh")

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

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print()
    print(f"PYTHON: {report['python']}")
    print("        Запускай усі інші скрипти саме ним.")
    if mode == "light":
        print("MODE: light — ffmpeg burns ASS subtitles. Nothing else needed.")
    elif mode == "standalone":
        print("MODE: standalone — this ffmpeg has no libass, so captions render")
        print("      through Pillow instead. Works the same; nothing to install.")
    else:
        print("MODE: blocked — fix these before editing:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)


if __name__ == "__main__":
    main()

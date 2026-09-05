"""Resolves the plugin folder and the tools setup.py put inside it.

install.sh copies only the skill folder, so the installed copy has no setup.py
above it. It writes `.plugin-root` next to these scripts instead — that file
points back at the plugin folder holding vendor/, .venv/ and config.json.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _plugin_root():
    # 1. installed copy: an explicit pointer written by install.sh
    for base in (HERE, *HERE.parents):
        marker = base / ".plugin-root"
        if marker.exists():
            try:
                cand = Path(marker.read_text(encoding="utf-8").strip()).expanduser()
                if (cand / "setup.py").exists():
                    return cand
            except Exception:
                pass
    # 2. running from inside the plugin folder itself
    for parent in HERE.parents:
        if (parent / "setup.py").exists():
            return parent
    return None


ROOT = _plugin_root()
CONFIG = {}
if ROOT and (ROOT / "config.json").exists():
    try:
        CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    except Exception:
        CONFIG = {}


def binary(name):
    """Full path to ffmpeg/ffprobe — vendor copy, then config, then PATH."""
    if ROOT:
        local = ROOT / "vendor" / name
        if local.exists():
            return str(local)
    cfg = CONFIG.get(name)
    if cfg and Path(cfg).exists():
        return cfg
    return shutil.which(name) or name


def python_path():
    """The interpreter that has faster-whisper and Pillow, if setup.py made one."""
    if ROOT:
        local = ROOT / ".venv" / "bin" / "python"
        if local.exists():
            return str(local)
    cfg = CONFIG.get("python")
    if cfg and Path(cfg).exists():
        return cfg
    return None


def profile_path():
    """Where the user profile lives: the video folder first, then the plugin."""
    here = Path.cwd() / "profiles" / "user.json"
    if here.exists():
        return str(here)
    if ROOT and (ROOT / "profiles" / "user.json").exists():
        return str(ROOT / "profiles" / "user.json")
    return None


def reexec_in_venv():
    """Re-run this script under the plugin's interpreter when needed.

    Lets the agent call every script with plain `python3` and still get the one
    that has faster-whisper installed.
    """
    py = python_path()
    if not py or Path(py).resolve() == Path(sys.executable).resolve():
        return
    import os
    os.execv(py, [py, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]])


FFMPEG = binary("ffmpeg")
FFPROBE = binary("ffprobe")

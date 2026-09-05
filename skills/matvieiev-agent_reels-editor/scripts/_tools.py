"""Resolves ffmpeg/ffprobe paths. setup.py may put them in the plugin's vendor/,
so calling them by bare name fails on a machine without a system install.
"""
import json
import shutil
from pathlib import Path


def _plugin_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / "setup.py").exists():
            return parent
    return None


ROOT = _plugin_root()
_CONFIG = {}
if ROOT and (ROOT / "config.json").exists():
    try:
        _CONFIG = json.loads((ROOT / "config.json").read_text())
    except Exception:
        _CONFIG = {}


def binary(name):
    """Full path to ffmpeg/ffprobe — vendor copy, then config, then PATH."""
    if ROOT:
        local = ROOT / "vendor" / name
        if local.exists():
            return str(local)
    cfg = _CONFIG.get(name)
    if cfg and Path(cfg).exists():
        return cfg
    return shutil.which(name) or name


FFMPEG = binary("ffmpeg")
FFPROBE = binary("ffprobe")

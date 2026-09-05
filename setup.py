#!/usr/bin/env python3
"""Sets the plugin up on this machine. Run by the agent, not by the user.

Installs everything into the plugin folder itself — nothing goes into system
directories, nothing asks for an administrator password, and removing the
folder removes every trace.

    python3 setup.py            install what is missing
    python3 setup.py --check    report only, change nothing
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
VENV = ROOT / ".venv"
CONFIG = ROOT / "config.json"

FFMPEG_MAC = "https://evermeet.cx/ffmpeg/getrelease/zip"
FFPROBE_MAC = "https://evermeet.cx/ffprobe/getrelease/zip"
UV_INSTALL = "https://astral.sh/uv/install.sh"
PY_VERSION = "3.12"


def say(msg):
    print(msg, flush=True)


def ok(msg):
    print(f"  \033[32m✓\033[0m {msg}", flush=True)


def work(msg):
    print(f"  · {msg}", flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def which(name):
    """Look in vendor/ first, then on PATH."""
    local = VENDOR / name
    if local.exists() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which(name)


# ---------------------------------------------------------------- ffmpeg

def fetch_ffmpeg():
    """Static ffmpeg + ffprobe into vendor/. No Homebrew, no password."""
    if platform.system() != "Darwin":
        return False, ("автоматична установка ffmpeg зроблена для macOS. "
                       "На Linux: sudo apt install ffmpeg")
    VENDOR.mkdir(exist_ok=True)
    for name, url in (("ffmpeg", FFMPEG_MAC), ("ffprobe", FFPROBE_MAC)):
        if (VENDOR / name).exists():
            continue
        work(f"завантажую {name} (~25 МБ)…")
        tmp = VENDOR / f"{name}.zip"
        urllib.request.urlretrieve(url, tmp)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(VENDOR)
        tmp.unlink()
        (VENDOR / name).chmod(0o755)
        # macOS quarantines downloads; strip it so the binary can run
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(VENDOR / name)],
                       capture_output=True)
    return True, None


# ---------------------------------------------------------------- python

def find_python310():
    """A Python new enough for ctranslate2 — 3.9 has no wheels."""
    for cand in ([sys.executable] + [shutil.which(f"python3.{m}") for m in (13, 12, 11, 10)]):
        if not cand:
            continue
        try:
            out = run([cand, "-c",
                       "import sys;print('%d.%d' % sys.version_info[:2])"]).stdout.strip()
            major, minor = (int(x) for x in out.split("."))
            if (major, minor) >= (3, 10):
                return cand
        except Exception:
            continue
    return None


def ensure_uv():
    uv = which("uv") or shutil.which("uv")
    if uv:
        return uv
    work("ставлю uv — менеджер, який принесе потрібний Python…")
    script = urllib.request.urlopen(UV_INSTALL, timeout=60).read().decode()
    env = dict(os.environ, UV_INSTALL_DIR=str(VENDOR), UV_NO_MODIFY_PATH="1")
    subprocess.run(["sh", "-c", script], env=env, check=True,
                   capture_output=True, text=True)
    for c in (VENDOR / "uv", Path.home() / ".local/bin/uv", Path.home() / ".cargo/bin/uv"):
        if c.exists():
            return str(c)
    return shutil.which("uv")


def ensure_venv():
    """A private virtualenv inside the plugin folder."""
    py = VENV / "bin" / "python"
    if py.exists():
        return str(py)

    base = find_python310()
    if base:
        work(f"створюю оточення на {Path(base).name}…")
        run([base, "-m", "venv", str(VENV)])
        return str(py)

    uv = ensure_uv()
    if not uv:
        raise RuntimeError("не вдалось поставити uv — потрібен Python 3.10 або новіший")
    work(f"ставлю Python {PY_VERSION} (у папку плагіна, систему не чіпає)…")
    run([uv, "python", "install", PY_VERSION])
    run([uv, "venv", "--python", PY_VERSION, str(VENV)])
    return str(py)


def ensure_packages(py):
    need = []
    for mod, pkg in (("faster_whisper", "faster-whisper"), ("PIL", "Pillow")):
        try:
            run([py, "-c", f"import {mod}"])
        except subprocess.CalledProcessError:
            need.append(pkg)
    if not need:
        return
    work(f"ставлю {', '.join(need)} (кілька хвилин)…")
    run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([py, "-m", "pip", "install", "--quiet", *need])


# ---------------------------------------------------------------- report

def status():
    py = VENV / "bin" / "python"
    have_pkgs = False
    if py.exists():
        try:
            run([str(py), "-c", "import faster_whisper, PIL"])
            have_pkgs = True
        except Exception:
            pass
    return {
        "ffmpeg": which("ffmpeg"),
        "ffprobe": which("ffprobe"),
        "python": str(py) if py.exists() else None,
        "packages": have_pkgs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    st = status()
    ready = all([st["ffmpeg"], st["ffprobe"], st["python"], st["packages"]])

    if a.check:
        print(json.dumps({**st, "ready": ready}, indent=2))
        return 0 if ready else 1

    if ready:
        say("Все вже встановлено — можна монтувати.")
        CONFIG.write_text(json.dumps(status(), indent=2), encoding="utf-8")
        return 0

    say("")
    say("Готую все потрібне. Пароль не знадобиться, систему не чіпаю —")
    say("усе лягає в папку самого плагіна.")
    say("")

    try:
        if not (st["ffmpeg"] and st["ffprobe"]):
            good, err = fetch_ffmpeg()
            if not good:
                say(f"  ! {err}")
                return 1
            ok("ffmpeg — відео й звук")
        else:
            ok("ffmpeg вже є")

        py = ensure_venv()
        ok("Python")

        ensure_packages(py)
        ok("розпізнавання мови й малювання субтитрів")

    except subprocess.CalledProcessError as e:
        say("")
        say(f"  ! Не вийшло: {(e.stderr or '').strip()[:400]}")
        return 1
    except Exception as e:
        say("")
        say(f"  ! Не вийшло: {e}")
        return 1

    CONFIG.write_text(json.dumps(status(), indent=2), encoding="utf-8")
    say("")
    say("Готово. Можна кидати відео.")
    say("Перше розпізнавання додатково завантажить мовну модель (~2.7 ГБ).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

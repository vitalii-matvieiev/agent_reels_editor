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

# evermeet's /getrelease/ endpoint returns ffmpeg for both tools, so resolve
# the real per-tool URL through its info API instead.
EVERMEET_INFO = "https://evermeet.cx/ffmpeg/info/{tool}/release"
UV_INSTALL = "https://astral.sh/uv/install.sh"
PY_VERSION = "3.12"

# Розширений режим. Ставиться ОКРЕМО і лише на явне прохання людини:
# OpenMontage має ліцензію AGPLv3, тому ми його не вшиваємо і не поширюємо —
# людина завантажує його сама, як будь-яку сторонню програму.
OPENMONTAGE_REPO = "https://github.com/calesthio/OpenMontage.git"
NODE_INDEX = "https://nodejs.org/dist/index.json"
PRO_DIR = ROOT / "pro" / "OpenMontage"


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) reels-editor-setup"


def http_get(url, timeout=120):
    """Fetch bytes. Some CDNs reject urllib's default User-Agent with 403."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


def http_download(url, dest, timeout=300):
    data = http_get(url, timeout)
    Path(dest).write_bytes(data)


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
    for name in ("ffmpeg", "ffprobe"):
        target = VENDOR / name
        if target.exists():
            continue

        info = json.loads(http_get(EVERMEET_INFO.format(tool=name), 60))
        url = next((d["url"] for d in info.get("download", {}).values()
                    if d.get("url", "").endswith(".zip")), None)
        if not url:
            return False, f"не знайшов, звідки завантажити {name}"

        work(f"завантажую {name} (~25 МБ)…")
        tmp = VENDOR / f"{name}.zip"
        http_download(url, tmp)

        # the archive holds one binary; its inner name is not reliable
        with zipfile.ZipFile(tmp) as z:
            member = next(m for m in z.namelist() if not m.startswith("__"))
            with z.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp.unlink()
        target.chmod(0o755)

        # macOS quarantines downloads; strip it so the binary can run
        subprocess.run(["xattr", "-d", "com.apple.quarantine", str(target)],
                       capture_output=True)

        # make sure we actually got the tool we asked for
        probe = subprocess.run([str(target), "-hide_banner", "-version"],
                               capture_output=True, text=True)
        if name not in (probe.stdout or "").split("\n")[0]:
            target.unlink(missing_ok=True)
            return False, f"завантажений файл виявився не {name}"
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


def uv_env():
    """Keep uv's Python inside the plugin folder — the README promises that
    deleting the folder leaves nothing behind, and uv's default is ~/.local."""
    return dict(os.environ,
                UV_PYTHON_INSTALL_DIR=str(VENDOR / "python"),
                UV_NO_MODIFY_PATH="1")


def find_uv():
    """uv may live in vendor/, in ~/.local/bin, or on PATH."""
    marker = ROOT / ".uv-path"
    if marker.exists():
        cand = marker.read_text().strip()
        if cand and Path(cand).exists():
            return cand
    for c in (VENDOR / "uv", Path.home() / ".local/bin/uv",
              Path.home() / ".cargo/bin/uv"):
        if c.exists():
            return str(c)
    return shutil.which("uv")


def ensure_uv():
    uv = find_uv()
    if uv:
        return uv
    work("ставлю uv — менеджер, який принесе потрібний Python…")
    script = http_get(UV_INSTALL).decode()
    env = dict(os.environ, UV_INSTALL_DIR=str(VENDOR), UV_NO_MODIFY_PATH="1")
    subprocess.run(["sh", "-c", script], env=env, check=True,
                   capture_output=True, text=True)
    found = find_uv()
    if found:
        (ROOT / ".uv-path").write_text(found, encoding="utf-8")
    return found


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
    env = uv_env()
    run([uv, "python", "install", PY_VERSION], env=env)
    run([uv, "venv", "--python", PY_VERSION, str(VENV)], env=env)
    (ROOT / ".uv-path").write_text(uv, encoding="utf-8")
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

    # A uv-created venv has no pip of its own — install through uv instead.
    try:
        run([py, "-m", "pip", "--version"])
        run([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        run([py, "-m", "pip", "install", "--quiet", *need])
        return
    except subprocess.CalledProcessError:
        pass

    uv = find_uv() or ensure_uv()
    if not uv:
        raise RuntimeError("немає ні pip, ні uv — не можу поставити пакети")
    run([uv, "pip", "install", "--python", py, *need])


# ---------------------------------------------------------------- pro mode

def ensure_node():
    """Node for Remotion. Official tarball into vendor/ — no brew, no password."""
    local = VENDOR / "node" / "bin"
    if (local / "npm").exists():
        return str(local)
    if shutil.which("npm"):
        return None                      # системний підходить

    if platform.system() != "Darwin":
        raise RuntimeError("автоматична установка Node зроблена для macOS — "
                           "постав його з nodejs.org")

    arch = "arm64" if platform.machine() == "arm64" else "x64"
    index = json.loads(http_get(NODE_INDEX, 60))
    rel = next(r for r in index if r.get("lts"))
    ver = rel["version"]
    name = f"node-{ver}-darwin-{arch}"
    url = f"https://nodejs.org/dist/{ver}/{name}.tar.gz"

    work(f"ставлю Node {ver} (~50 МБ, у папку плагіна)…")
    VENDOR.mkdir(exist_ok=True)
    tgz = VENDOR / "node.tar.gz"
    http_download(url, tgz, timeout=600)

    import tarfile
    with tarfile.open(tgz) as t:
        t.extractall(VENDOR)
    tgz.unlink()

    extracted = VENDOR / name
    target = VENDOR / "node"
    if target.exists():
        shutil.rmtree(target)
    extracted.rename(target)

    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(target)],
                   capture_output=True)
    return str(target / "bin")


def install_pro():
    """Downloads OpenMontage — optional, unlocks AI generation via paid APIs."""
    if not shutil.which("git"):
        return False, "потрібен git — постав Xcode Command Line Tools"

    node_bin = ensure_node()
    env = dict(os.environ)
    if node_bin:
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")

    PRO_DIR.parent.mkdir(parents=True, exist_ok=True)

    if not PRO_DIR.exists():
        work("завантажую OpenMontage (~260 МБ, кілька хвилин)…")
        run(["git", "clone", "--depth", "1", OPENMONTAGE_REPO, str(PRO_DIR)])
    else:
        work("OpenMontage уже завантажений")

    om_venv = PRO_DIR / ".venv"
    if not (om_venv / "bin" / "python").exists():
        work("створюю оточення для OpenMontage…")
        base = find_python310() or ensure_venv()
        uv = find_uv()
        if uv:
            run([uv, "venv", "--python", PY_VERSION, str(om_venv)], env=uv_env())
        else:
            run([base, "-m", "venv", str(om_venv)])

    om_py = str(om_venv / "bin" / "python")
    work("ставлю залежності OpenMontage (кілька хвилин)…")
    try:
        run([om_py, "-m", "pip", "install", "--quiet", "-r",
             str(PRO_DIR / "requirements.txt")])
    except subprocess.CalledProcessError:
        uv = find_uv() or ensure_uv()
        if not uv:
            return False, "не вдалось поставити залежності OpenMontage"
        run([uv, "pip", "install", "--python", om_py, "-r",
             str(PRO_DIR / "requirements.txt")])

    work("ставлю Remotion (~580 МБ, це найдовше)…")
    npm = str(Path(node_bin) / "npm") if node_bin else "npm"
    run([npm, "install", "--silent"],
        cwd=str(PRO_DIR / "remotion-composer"), env=env)

    env_file = PRO_DIR / ".env"
    if not env_file.exists() and (PRO_DIR / ".env.example").exists():
        shutil.copy(PRO_DIR / ".env.example", env_file)

    return True, None


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
    pro_py = PRO_DIR / ".venv" / "bin" / "python"
    return {
        "ffmpeg": which("ffmpeg"),
        "ffprobe": which("ffprobe"),
        "python": str(py) if py.exists() else None,
        "packages": have_pkgs,
        "mode": "pro" if pro_py.exists() else "free",
        "openmontage": str(PRO_DIR) if pro_py.exists() else None,
        "openmontage_python": str(pro_py) if pro_py.exists() else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--pro", action="store_true",
                    help="додатково поставити OpenMontage (генерація через платні API)")
    a = ap.parse_args()

    st = status()
    ready = all([st["ffmpeg"], st["ffprobe"], st["python"], st["packages"]])

    if a.check:
        print(json.dumps({**st, "ready": ready}, indent=2))
        return 0 if ready else 1

    if ready and not a.pro:
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

    if a.pro:
        say("")
        say("Тепер розширений режим. Це стороння програма OpenMontage —")
        say("вона під ліцензією AGPLv3 і завантажується з її власного репозиторію.")
        say("")
        try:
            good, err = install_pro()
        except subprocess.CalledProcessError as e:
            good, err = False, (e.stderr or "").strip()[:300]
        except Exception as e:
            good, err = False, str(e)
        if good:
            ok("розширений режим — генерація зображень і відео")
        else:
            say(f"  ! Розширений режим не став: {err}")
            say("    Безкоштовний режим від цього не постраждав — він працює.")

    CONFIG.write_text(json.dumps(status(), indent=2), encoding="utf-8")
    say("")
    say("Готово. Можна кидати відео.")
    say("Перше розпізнавання додатково завантажить мовну модель (~2.7 ГБ).")
    if not a.pro:
        say("")
        say("Це безкоштовний режим — усе локально, без жодних API-ключів.")
        say("Потрібна генерація картинок і відео? Скажи агенту «постав розширений режим».")
    return 0


if __name__ == "__main__":
    sys.exit(main())

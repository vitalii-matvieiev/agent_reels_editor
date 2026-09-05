#!/usr/bin/env python3
"""Вшиває хук у рілс так, щоб його було видно і в сітці профілю, і при перегляді.

Причина існування скрипта — розбір ролика від 2026-09-04: хук стояв угорі кадру,
Instagram зрізав його в сітці профілю й накрив шапкою при перегляді. 96 переглядів
проти 1029 і 1183 у сусідніх постів. Заміри й висновки — у README.md, розділ
«Обкладинка і хук».

Використання:
    python3 hook_overlay.py in.mp4 out.mp4 "МОНТАЖ ВІДЕО|КОШТУВАВ $10|ЗА 3 ХВИЛИНИ"
    python3 hook_overlay.py in.mp4 out.mp4 --text "РЯДОК|ЩЕ РЯДОК" --seconds 4

Рядки розділяються вертикальною рискою. Якщо рядок ширший за безпечну зону,
шрифт зменшується сам — і лише коли й це не рятує, скрипт зупиняється.

Поруч із out.mp4 кладе grid_preview.png — це кроп 3:4, тобто рівно те, що побачить
людина в сітці профілю. Дивись на нього перед публікацією, а не на повний кадр.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tools  # noqa: E402
from _tools import FFMPEG, FFPROBE  # noqa: E402

_tools.reexec_in_venv()


W, H = 1080, 1920

# Зона, у якій текст переживає і кроп сітки, і накладки плеєра.
# Виведення чисел — у references/safe-zones.md.
SAFE_TOP = 480      # вище — ховає шапка плеєра
SAFE_BOTTOM = 1350  # нижче — ховає підпис і кнопки
SAFE_LEFT = 50
SAFE_RIGHT = 1010   # правіше — вертикальна стрічка кнопок плеєра

FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_BOLD_INDEX = 1
FONT_SIZE = 104          # дає висоту великої літери ~75 px
FONT_MIN = 68            # нижче — не читається в плитці 438 px
STROKE = 11              # чорна обводка замість плашки: не ріже кадр


def load_font(size):
    for path in FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        try:
            idx = FONT_BOLD_INDEX if path.endswith(".ttc") else 0
            return ImageFont.truetype(path, size, index=idx)
        except Exception:
            continue
    sys.exit("не знайшов жирного шрифту для хука — постав Arial Black або DejaVu Sans Bold")


def fit_font(lines, draw):
    """Найбільший кегль, при якому всі рядки влазять у безпечну зону."""
    max_w = SAFE_RIGHT - SAFE_LEFT
    size = FONT_SIZE
    while size >= FONT_MIN:
        font = load_font(size)
        pitch = round(size * 1.115)
        if pitch * len(lines) <= SAFE_BOTTOM - SAFE_TOP and \
           all(draw.textlength(ln, font=font) <= max_w for ln in lines):
            return font, pitch, size
        size -= 4

    font = load_font(FONT_MIN)
    widest = max(lines, key=lambda ln: draw.textlength(ln, font=font))
    if round(FONT_MIN * 1.115) * len(lines) > SAFE_BOTTOM - SAFE_TOP:
        sys.exit(f"Забагато рядків: {len(lines)}. У безпечну зону влазить "
                 f"{(SAFE_BOTTOM - SAFE_TOP) // round(FONT_MIN * 1.115)}.")
    sys.exit(f"Рядок задовгий навіть на найменшому кеглі:\n  {widest}\n"
             f"Розбий його вертикальною рискою на два коротші.")


def probe_dims(video):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video],
        capture_output=True, text=True).stdout.strip()
    try:
        w, h = out.split("x")[:2]
        return int(w), int(h)
    except Exception:
        sys.exit(f"не зміг прочитати розмір кадру: {video}")


def fit_filter(src_w, src_h, fit):
    """Як привести кадр до 1080x1920, не розтягуючи обличчя."""
    if abs(src_w / src_h - W / H) < 0.01:
        return f"scale={W}:{H}"
    if fit == "crop":
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H}")
    if fit == "pad":
        return (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")
    if fit == "blur":
        return (f"split[bg][fg];"
                f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},gblur=sigma=40[bgb];"
                f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
                f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    sys.exit(
        f"Відео {src_w}x{src_h} — це не вертикаль 9:16, а рілс має бути 1080x1920.\n"
        f"Розтягувати кадр я не буду: обличчя стане сплюснутим.\n"
        f"Спитай людину, як приводити, і додай один з варіантів:\n"
        f"  --fit crop  — обрізати боки (втрачається частина кадру)\n"
        f"  --fit pad   — вписати цілком, чорні поля зверху й знизу\n"
        f"  --fit blur  — вписати цілком, розмитий кадр замість полів")


def render_overlay(lines, path, accent_last=False):
    """Малює хук у безпечній зоні, вирівняний по низу зони."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font, pitch, size = fit_font(lines, d)
    if size != FONT_SIZE:
        print(f"  (кегль зменшено {FONT_SIZE} → {size}, щоб рядки влізли в безпечну зону)")

    block_h = pitch * len(lines)
    # Ставимо блок у нижню третину безпечної зони — там, де він працює у Віталія.
    y = SAFE_BOTTOM - block_h
    max_w = SAFE_RIGHT - SAFE_LEFT

    for i, line in enumerate(lines):
        w = d.textlength(line, font=font)
        x = SAFE_LEFT + (max_w - w) / 2
        colour = (217, 119, 87) if (accent_last and i == len(lines) - 1) else (255, 255, 255)
        d.text((x, y), line, font=font, fill=colour + (255,),
               stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
        y += pitch

    img.save(path)


def grid_preview(video, overlay_png, out_png, scale_filter, at=1.0):
    """Кроп 3:4 по центру — рівно те, що видно в сітці профілю."""
    keep = int(W / 0.75)              # 1440 px із 1920
    top = (H - keep) // 2             # 240 px зверху і знизу зникають
    subprocess.run([
        FFMPEG, "-v", "error", "-y", "-ss", str(at), "-i", video, "-i", overlay_png,
        "-filter_complex",
        f"[0:v]{scale_filter}[b];[b][1:v]overlay=0:0,crop={W}:{keep}:0:{top}",
        "-frames:v", "1", out_png,
    ], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("hook", nargs="?", default=None,
                    help="рядки хука через вертикальну риску")
    ap.add_argument("--text", dest="text", default=None,
                    help="те саме, що позиційний аргумент hook")
    ap.add_argument("--seconds", type=float, default=0,
                    help="скільки секунд тримати хук; 0 — весь ролик")
    ap.add_argument("--accent-last", action="store_true",
                    help="останній рядок помаранчевим")
    ap.add_argument("--fit", choices=["crop", "pad", "blur"], default=None,
                    help="як приводити невертикальне відео до 1080x1920")
    a = ap.parse_args()

    raw = a.hook or a.text
    if not raw:
        sys.exit("Не передав текст хука. Приклад:\n"
                 '  hook_overlay.py in.mp4 out.mp4 "РЯДОК|ЩЕ РЯДОК"')
    lines = [s.strip() for s in raw.split("|") if s.strip()]
    if not lines:
        sys.exit("Порожній хук.")

    if not Path(a.src).exists():
        sys.exit(f"файлу немає: {a.src}")
    sw, sh = probe_dims(a.src)
    scale_filter = fit_filter(sw, sh, a.fit)

    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "hook.png")
    render_overlay(lines, png, accent_last=a.accent_last)

    enable = f":enable='lte(t,{a.seconds})'" if a.seconds else ""
    subprocess.run([
        FFMPEG, "-v", "error", "-y", "-i", a.src, "-i", png,
        "-filter_complex", f"[0:v]{scale_filter}[b];[b][1:v]overlay=0:0{enable}[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.dst,
    ], check=True)

    preview = os.path.join(os.path.dirname(os.path.abspath(a.dst)) or ".", "grid_preview.png")
    grid_preview(a.src, png, preview, scale_filter)
    print(f"Готово: {a.dst}\nПеревір сітку: {preview}")


if __name__ == "__main__":
    main()

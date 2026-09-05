#!/usr/bin/env python3
"""Вшиває хук у рілс так, щоб його було видно і в сітці профілю, і при перегляді.

Причина існування скрипта — розбір ролика від 2026-09-04: хук стояв угорі кадру,
Instagram зрізав його в сітці профілю й накрив шапкою при перегляді. 96 переглядів
проти 1029 і 1183 у сусідніх постів. Заміри й висновки — у README.md, розділ
«Обкладинка і хук».

Використання:
    python3 reels/hook_overlay.py in.mp4 out.mp4 "МОНТАЖ ВІДЕО|КОШТУВАВ $10.|АГЕНТ РОБИТЬ|ЗА 3 ХВИЛИНИ"
    python3 reels/hook_overlay.py in.mp4 out.mp4 "РЯДОК|ЩЕ РЯДОК" --seconds 4

Поруч із out.mp4 кладе grid_preview.png — це кроп 3:4, тобто рівно те, що побачить
людина в сітці профілю. Дивись на нього перед публікацією, а не на повний кадр.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

# Зона, у якій текст переживає і кроп сітки, і накладки плеєра.
# Виведення чисел — у README.md, розділ «Обкладинка і хук».
SAFE_TOP = 480      # вище — ховає шапка плеєра
SAFE_BOTTOM = 1350  # нижче — ховає підпис і кнопки
SAFE_LEFT = 50
SAFE_RIGHT = 1010   # правіше — вертикальна стрічка кнопок плеєра

FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
FONT_BOLD_INDEX = 1
FONT_SIZE = 104          # дає висоту великої літери ~75 px
LINE_PITCH = 116
STROKE = 11              # чорна обводка замість плашки: не ріже кадр


def render_overlay(lines, path, accent_last=False):
    """Малює хук у безпечній зоні, вирівняний по низу зони."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, FONT_SIZE, index=FONT_BOLD_INDEX)

    block_h = LINE_PITCH * len(lines)
    if block_h > SAFE_BOTTOM - SAFE_TOP:
        sys.exit(f"Забагато рядків: {len(lines)}. У безпечну зону влазить "
                 f"{(SAFE_BOTTOM - SAFE_TOP) // LINE_PITCH}.")

    # Ставимо блок у нижню третину безпечної зони — там, де він працює у Віталія.
    y = SAFE_BOTTOM - block_h
    max_w = SAFE_RIGHT - SAFE_LEFT

    for i, line in enumerate(lines):
        w = d.textlength(line, font=font)
        if w > max_w:
            sys.exit(f"Рядок не влазить у безпечну ширину ({int(w)} > {max_w} px):\n  {line}\n"
                     f"Розбий його вертикальною рискою на два.")
        x = SAFE_LEFT + (max_w - w) / 2
        colour = (217, 119, 87) if (accent_last and i == len(lines) - 1) else (255, 255, 255)
        d.text((x, y), line, font=font, fill=colour + (255,),
               stroke_width=STROKE, stroke_fill=(0, 0, 0, 255))
        y += LINE_PITCH

    img.save(path)


def grid_preview(video, overlay_png, out_png, at=1.0):
    """Кроп 3:4 по центру — рівно те, що видно в сітці профілю."""
    keep = int(W / 0.75)              # 1440 px із 1920
    top = (H - keep) // 2             # 240 px зверху і знизу зникають
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", video, "-i", overlay_png,
        "-filter_complex",
        f"[0:v]scale={W}:{H}[b];[b][1:v]overlay=0:0,crop={W}:{keep}:0:{top}",
        "-frames:v", "1", out_png,
    ], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("hook", help="рядки хука через вертикальну риску")
    ap.add_argument("--seconds", type=float, default=0,
                    help="скільки секунд тримати хук; 0 — весь ролик")
    ap.add_argument("--accent-last", action="store_true",
                    help="останній рядок помаранчевим")
    a = ap.parse_args()

    lines = [s.strip() for s in a.hook.split("|") if s.strip()]
    if not lines:
        sys.exit("Порожній хук.")

    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "hook.png")
    render_overlay(lines, png, accent_last=a.accent_last)

    enable = f":enable='lte(t,{a.seconds})'" if a.seconds else ""
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", a.src, "-i", png,
        "-filter_complex", f"[0:v]scale={W}:{H}[b];[b][1:v]overlay=0:0{enable}[v]",
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.dst,
    ], check=True)

    preview = os.path.join(os.path.dirname(os.path.abspath(a.dst)) or ".", "grid_preview.png")
    grid_preview(a.src, png, preview)
    print(f"Готово: {a.dst}\nПеревір сітку: {preview}")


if __name__ == "__main__":
    main()

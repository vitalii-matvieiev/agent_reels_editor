#!/usr/bin/env python3
"""Renders caption frames with Pillow — the fallback when ffmpeg has no libass.

Draws only a horizontal strip, not the whole frame, so the PNGs stay small and
the overlay is cheap. Used by burn_captions.py; not usually called directly.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STRIP_H = 320          # tall enough for two lines at 76px
PAD_X, PAD_Y = 34, 18  # padding inside the plate
RADIUS = 14


def _load_font(name, size):
    """Resolve a font by family name or path, with sane fallbacks."""
    candidates = []
    if name and os.path.sep in name:
        candidates.append(name)
    base = "/System/Library/Fonts/Supplemental"
    for fam in filter(None, [name, "Arial Black", "Arial Bold", "Helvetica"]):
        candidates += [f"{base}/{fam}.ttf", f"{base}/{fam}.ttc",
                       f"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render_group(group, active_idx, width, cfg):
    """One PNG strip: the group's words, with word `active_idx` highlighted."""
    font = _load_font(cfg.get("font"), cfg.get("font_size", 76))
    accent, text_col = _hex(cfg.get("accent", "#FFC93C")), _hex(cfg.get("text", "#FFFFFF"))

    img = Image.new("RGBA", (width, STRIP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    words = [w["word"] for w in group]
    space = d.textlength(" ", font=font)
    widths = [d.textlength(w, font=font) for w in words]
    total = sum(widths) + space * (len(words) - 1)

    # Wrap to two lines if the group is too wide for the frame
    max_w = width - 2 * (PAD_X + 40)
    lines, cur, cur_w = [], [], 0.0
    if total <= max_w:
        lines = [list(range(len(words)))]
    else:
        for i, ww in enumerate(widths):
            add = ww if not cur else space + ww
            if cur_w + add > max_w and cur:
                lines.append(cur); cur, cur_w = [i], ww
            else:
                cur.append(i); cur_w += add
        if cur:
            lines.append(cur)

    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 8
    block_h = line_h * len(lines)
    y0 = (STRIP_H - block_h) // 2

    # Plate behind the text
    plate_w = max(sum(widths[i] for i in ln) + space * (len(ln) - 1) for ln in lines)
    plate = [
        (width - plate_w) / 2 - PAD_X, y0 - PAD_Y,
        (width + plate_w) / 2 + PAD_X, y0 + block_h + PAD_Y,
    ]
    d.rounded_rectangle(plate, radius=RADIUS, fill=(15, 23, 42, 180))

    for li, idxs in enumerate(lines):
        lw = sum(widths[i] for i in idxs) + space * (len(idxs) - 1)
        x = (width - lw) / 2
        y = y0 + li * line_h
        for i in idxs:
            col = accent if i == active_idx else text_col
            d.text((x, y), words[i], font=font, fill=col + (255,),
                   stroke_width=6, stroke_fill=(0, 0, 0, 210))
            x += widths[i] + space
    return img


def render_sequence(groups, width, height, fps, duration, cfg, outdir):
    """Writes one PNG per frame. Identical states are hard-linked, not redrawn."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    blank = Image.new("RGBA", (width, STRIP_H), (0, 0, 0, 0))
    blank_path = outdir / "_blank.png"
    blank.save(blank_path)

    cache = {}
    total_frames = int(round(duration * fps))
    for f in range(total_frames):
        t = f / fps
        state = None
        for gi, g in enumerate(groups):
            if g[0]["start"] <= t < g[-1]["end"] + 0.12:
                ai = 0
                for wi, w in enumerate(g):
                    if w["start"] <= t:
                        ai = wi
                state = (gi, ai)
                break

        dst = outdir / f"{f:06d}.png"
        if state is None:
            os.link(blank_path, dst) if not dst.exists() else None
            continue
        if state not in cache:
            src = outdir / f"s_{state[0]:04d}_{state[1]:02d}.png"
            render_group(groups[state[0]], state[1], width, cfg).save(src)
            cache[state] = src
        if not dst.exists():
            os.link(cache[state], dst)

    return total_frames, len(cache)

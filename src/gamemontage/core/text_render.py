"""Render styled gaming text to RGBA images with Pillow.

We deliberately avoid MoviePy's ``TextClip`` because it requires ImageMagick to
be installed and configured, which is a common source of "it doesn't work on my
machine" issues. Instead we render text with Pillow (already a dependency) into
RGBA numpy arrays that can be wrapped in a MoviePy ``ImageClip``.

Features:
* bold outline + drop shadow (the classic "gamer caption" look)
* automatic font discovery with graceful fallback to Pillow's default font
* word wrapping to a max width
"""

from __future__ import annotations

import functools
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

# Common bold font locations across OSes; first hit wins.
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


@functools.lru_cache(maxsize=32)
def _load_font(size: int, font_path: str | None = None) -> ImageFont.FreeTypeFont:
    candidates = [font_path] if font_path else []
    candidates += _FONT_CANDIDATES
    for cand in candidates:
        if cand and Path(cand).exists():
            try:
                return ImageFont.truetype(cand, size=size)
            except OSError:
                continue
    logger.debug("No TrueType font found; using Pillow default (size fixed).")
    return ImageFont.load_default()


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#FFFFFF").lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (255, 255, 255)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont,
          max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def render_text_rgba(
    text: str,
    *,
    font_size: int = 64,
    color: str = "#FFFFFF",
    outline_color: str = "#000000",
    outline_width: int = 4,
    shadow: bool = True,
    shadow_offset: int = 4,
    max_width: int | None = None,
    font_path: str | None = None,
    uppercase: bool = True,
    align: str = "center",
) -> np.ndarray:
    """Render ``text`` to an RGBA numpy array (HxWx4, uint8)."""
    if uppercase:
        text = text.upper()

    font = _load_font(font_size, font_path)
    fill = _hex_to_rgb(color)
    outline = _hex_to_rgb(outline_color)

    # Measure on a scratch image.
    scratch = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scratch)

    wrap_width = max_width or 100_000
    lines = _wrap(sdraw, text, font, wrap_width)

    ascent, descent = _font_metrics(font)
    line_h = ascent + descent + 8
    line_widths = [sdraw.textlength(ln, font=font) for ln in lines]
    text_w = int(max(line_widths) if line_widths else 1)
    text_h = int(line_h * len(lines))

    pad = outline_width + (shadow_offset if shadow else 0) + 6
    img_w = text_w + pad * 2
    img_h = text_h + pad * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        lw = line_widths[i]
        if align == "left":
            x = pad
        elif align == "right":
            x = img_w - pad - lw
        else:
            x = (img_w - lw) / 2
        y = pad + i * line_h

        if shadow:
            draw.text(
                (x + shadow_offset, y + shadow_offset), line, font=font,
                fill=(0, 0, 0, 160),
            )
        # outline via stroke (Pillow >= 8 supports stroke_width)
        try:
            draw.text(
                (x, y), line, font=font, fill=(*fill, 255),
                stroke_width=outline_width, stroke_fill=(*outline, 255),
            )
        except TypeError:  # very old Pillow without stroke support
            for ox in range(-outline_width, outline_width + 1):
                for oy in range(-outline_width, outline_width + 1):
                    draw.text((x + ox, y + oy), line, font=font, fill=(*outline, 255))
            draw.text((x, y), line, font=font, fill=(*fill, 255))

    return np.array(img)


def _font_metrics(font: ImageFont.ImageFont) -> tuple[int, int]:
    try:
        ascent, descent = font.getmetrics()
        return ascent, descent
    except AttributeError:
        return font.size, int(font.size * 0.25)

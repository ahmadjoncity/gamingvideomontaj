"""Tests for the Pillow-based text renderer (no ImageMagick needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from gamemontage.core.text_render import render_text_rgba  # noqa: E402


def test_render_returns_rgba_array():
    img = render_text_rgba("ACE!", font_size=48)
    assert img.ndim == 3
    assert img.shape[2] == 4          # RGBA
    assert img.dtype == np.uint8
    assert img.shape[0] > 0 and img.shape[1] > 0


def test_render_has_visible_pixels():
    img = render_text_rgba("CLUTCH", font_size=40)
    # some pixels must be non-transparent (alpha > 0)
    assert int((img[:, :, 3] > 0).sum()) > 0


def test_uppercase_and_wrapping_do_not_crash():
    img = render_text_rgba("insane one v five clutch play", font_size=36,
                           max_width=200, uppercase=True)
    assert img.shape[1] <= 200 + 64   # roughly within max width + padding budget

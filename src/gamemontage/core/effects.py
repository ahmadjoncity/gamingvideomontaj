"""Reusable MoviePy clip effects for the montage engine.

Each function takes a MoviePy ``VideoClip`` and returns a transformed clip.
They are written defensively so that, if a particular effect fails on an odd
clip, the montage builder can fall back to the untouched clip.

All effects are pure with respect to their inputs (they return new clips).
"""

from __future__ import annotations

import numpy as np

from gamemontage.core._moviepy import mpy
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Speed / time
# --------------------------------------------------------------------------- #
def slow_motion(clip, factor: float = 0.5):
    """Slow a clip down (``factor`` < 1 = slower). Keeps audio if present."""
    try:
        import moviepy.video.fx.all as vfx
        return clip.fx(vfx.speedx, factor)
    except Exception as exc:  # noqa: BLE001
        logger.debug("slow_motion failed: %s", exc)
        return clip


def speed_up(clip, factor: float = 1.5):
    try:
        import moviepy.video.fx.all as vfx
        return clip.fx(vfx.speedx, factor)
    except Exception as exc:  # noqa: BLE001
        logger.debug("speed_up failed: %s", exc)
        return clip


# --------------------------------------------------------------------------- #
# Spatial: zoom / punch-in / shake
# --------------------------------------------------------------------------- #
def punch_zoom(clip, max_zoom: float = 1.25):
    """Animated 'punch-in' zoom that eases from 1.0 to ``max_zoom``."""
    duration = clip.duration or 1.0

    def scale(t: float) -> float:
        p = min(1.0, t / duration)
        # ease-out cubic
        return 1.0 + (max_zoom - 1.0) * (1 - (1 - p) ** 3)

    try:
        zoomed = clip.resize(lambda t: scale(t))
        return zoomed.set_position("center")
    except Exception as exc:  # noqa: BLE001
        logger.debug("punch_zoom failed: %s", exc)
        return clip


def static_zoom(clip, zoom: float = 1.15):
    """Constant centred zoom that crops back to the original frame size."""
    try:
        w, h = clip.size
        zoomed = clip.resize(zoom)
        return zoomed.crop(
            x_center=zoomed.w / 2, y_center=zoomed.h / 2, width=w, height=h
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("static_zoom failed: %s", exc)
        return clip


def camera_shake(clip, intensity: float = 8.0, zoom: float = 1.08):
    """Add a hand-held 'shake' by jittering a slightly zoomed clip."""
    try:
        w, h = clip.size
        base = clip.resize(zoom)
        rng = np.random.default_rng(1234)
        # Pre-generate a smooth-ish random walk for x/y offsets.
        n = max(2, int((clip.duration or 1.0) * 24))
        dx = np.cumsum(rng.uniform(-1, 1, n))
        dy = np.cumsum(rng.uniform(-1, 1, n))
        dx = _norm_offset(dx, intensity)
        dy = _norm_offset(dy, intensity)

        def position(t: float):
            i = min(n - 1, int(t / (clip.duration or 1.0) * (n - 1)))
            cx = (base.w - w) / 2 + dx[i]
            cy = (base.h - h) / 2 + dy[i]
            return (-cx, -cy)

        composite = mpy().CompositeVideoClip(
            [base.set_position(position)], size=(w, h)
        ).set_duration(clip.duration)
        if clip.audio is not None:
            composite = composite.set_audio(clip.audio)
        return composite
    except Exception as exc:  # noqa: BLE001
        logger.debug("camera_shake failed: %s", exc)
        return clip


# --------------------------------------------------------------------------- #
# Stylised: glitch / fade
# --------------------------------------------------------------------------- #
def glitch(clip, intensity: int = 12):
    """Cheap RGB-split + scanline glitch achieved by channel shifting."""
    try:
        def fl(get_frame, t):
            frame = get_frame(t).astype(np.int16)
            shift = int(intensity * (0.5 + 0.5 * np.sin(t * 50)))
            if shift <= 0:
                return frame.astype("uint8")
            out = frame.copy()
            # shift red channel left, blue channel right
            out[:, shift:, 0] = frame[:, :-shift, 0]
            out[:, :-shift, 2] = frame[:, shift:, 2]
            return np.clip(out, 0, 255).astype("uint8")

        return clip.fl(fl)
    except Exception as exc:  # noqa: BLE001
        logger.debug("glitch failed: %s", exc)
        return clip


def fade_in_out(clip, fade: float = 0.2):
    try:
        import moviepy.video.fx.all as vfx
        d = clip.duration or 1.0
        f = min(fade, d / 3)
        return clip.fx(vfx.fadein, f).fx(vfx.fadeout, f)
    except Exception as exc:  # noqa: BLE001
        logger.debug("fade_in_out failed: %s", exc)
        return clip


# --------------------------------------------------------------------------- #
# Transitions between two clips
# --------------------------------------------------------------------------- #
def crossfade_transition(clip_a, clip_b, duration: float = 0.4):
    """Return ``clip_b`` set up to crossfade over the tail of ``clip_a``.

    The montage builder is responsible for negative padding when concatenating.
    """
    try:
        return clip_b.crossfadein(duration)
    except Exception as exc:  # noqa: BLE001
        logger.debug("crossfade failed: %s", exc)
        return clip_b


def zoom_transition_in(clip, duration: float = 0.3, start_zoom: float = 1.8):
    """Quick zoom-out at the start of a clip (feels like a punch cut)."""
    d = clip.duration or 1.0
    dur = min(duration, d)

    def scale(t: float) -> float:
        if t >= dur:
            return 1.0
        p = t / dur
        return start_zoom - (start_zoom - 1.0) * p

    try:
        return clip.resize(lambda t: scale(t)).set_position("center")
    except Exception as exc:  # noqa: BLE001
        logger.debug("zoom_transition failed: %s", exc)
        return clip


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _norm_offset(walk: np.ndarray, intensity: float) -> np.ndarray:
    if walk.size == 0:
        return walk
    peak = float(np.abs(walk).max()) or 1.0
    return walk / peak * intensity

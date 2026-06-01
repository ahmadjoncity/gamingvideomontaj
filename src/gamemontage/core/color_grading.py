"""Color grading 'looks' implemented as numpy frame transforms.

Applied to a MoviePy clip via ``clip.fl_image(grade_fn)``. No external LUT files
required. Looks are intentionally punchy because gaming montages favour vivid,
high-contrast imagery.
"""

from __future__ import annotations

import numpy as np

from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

LOOKS = ("none", "vibrant", "cinematic", "hdr", "cold", "warm")


def apply_grade(clip, look: str):
    """Return ``clip`` with the named color look applied."""
    look = (look or "none").lower()
    if look == "none":
        return clip
    fn = _LOOK_FNS.get(look)
    if fn is None:
        logger.debug("Unknown color look '%s'; skipping.", look)
        return clip
    try:
        return clip.fl_image(fn)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Color grade '%s' failed: %s", look, exc)
        return clip


# --------------------------------------------------------------------------- #
# Individual looks (operate on uint8 HxWx3 RGB frames)
# --------------------------------------------------------------------------- #
def _vibrant(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32) / 255.0
    # boost saturation by pushing channels away from luminance
    lum = f @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lum = lum[..., None]
    f = lum + (f - lum) * 1.35           # saturation
    f = (f - 0.5) * 1.12 + 0.5           # contrast
    f = np.clip(f, 0, 1) ** (1 / 1.05)   # slight gamma lift
    return (np.clip(f, 0, 1) * 255).astype("uint8")


def _cinematic(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32) / 255.0
    # teal shadows / orange highlights
    lum = (f @ np.array([0.299, 0.587, 0.114], dtype=np.float32))[..., None]
    shadows = np.clip(1.0 - lum, 0, 1)
    highs = np.clip(lum, 0, 1)
    f[..., 2] += 0.06 * shadows[..., 0]   # blue in shadows
    f[..., 1] += 0.03 * shadows[..., 0]
    f[..., 0] += 0.07 * highs[..., 0]     # red/orange in highlights
    f = (f - 0.5) * 1.08 + 0.5
    return (np.clip(f, 0, 1) * 255).astype("uint8")


def _hdr(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32) / 255.0
    lum = (f @ np.array([0.299, 0.587, 0.114], dtype=np.float32))[..., None]
    # local-ish detail boost: emphasise difference from luminance
    f = lum + (f - lum) * 1.5
    f = (f - 0.5) * 1.2 + 0.5
    f = np.clip(f, 0, 1) ** (1 / 1.15)
    return (np.clip(f, 0, 1) * 255).astype("uint8")


def _cold(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32)
    f[..., 2] *= 1.10   # more blue
    f[..., 0] *= 0.95   # less red
    return np.clip(f, 0, 255).astype("uint8")


def _warm(frame: np.ndarray) -> np.ndarray:
    f = frame.astype(np.float32)
    f[..., 0] *= 1.10   # more red
    f[..., 2] *= 0.93   # less blue
    return np.clip(f, 0, 255).astype("uint8")


_LOOK_FNS = {
    "vibrant": _vibrant,
    "cinematic": _cinematic,
    "hdr": _hdr,
    "cold": _cold,
    "warm": _warm,
}

"""Automatic thumbnail generation from the most epic frame.

Picks the highest-scoring highlight, grabs a punchy frame from it, applies a
vivid grade, and optionally stamps a big title. Output is a JPEG/PNG ready to
upload alongside the montage.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from gamemontage.core.text_render import render_text_rgba
from gamemontage.models import Highlight
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


class ThumbnailGenerator:
    def generate(
        self,
        highlights: list[Highlight],
        out_path: Path,
        title: str = "",
        size: tuple[int, int] = (1280, 720),
    ) -> Path | None:
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV unavailable; cannot generate thumbnail.")
            return None

        if not highlights:
            return None

        best = max(highlights, key=lambda h: h.score)
        frame = self._grab_frame(best, cv2)
        if frame is None:
            return None

        frame = cv2.resize(frame, size)
        frame = self._punch(frame)

        if title:
            frame = self._stamp_title(frame, title)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if ok:
            logger.info("Thumbnail written to %s", out_path)
            return out_path
        return None

    # ---- helpers ------------------------------------------------------------
    def _grab_frame(self, highlight: Highlight, cv2):
        cap = cv2.VideoCapture(str(highlight.clip_path))
        try:
            ts = highlight.start + highlight.duration * 0.5
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            return frame if ok else None
        finally:
            cap.release()

    @staticmethod
    def _punch(frame_bgr: np.ndarray) -> np.ndarray:
        """Boost saturation + contrast for an eye-catching thumbnail (BGR)."""
        f = frame_bgr.astype(np.float32)
        f = (f - 128) * 1.18 + 128            # contrast
        f = np.clip(f, 0, 255)
        # crude saturation boost
        mean = f.mean(axis=2, keepdims=True)
        f = mean + (f - mean) * 1.3
        return np.clip(f, 0, 255).astype("uint8")

    @staticmethod
    def _stamp_title(frame_bgr: np.ndarray, title: str) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        rgba = render_text_rgba(
            title, font_size=max(48, int(h * 0.13)),
            color="#FFE14D", outline_color="#000000", outline_width=8,
            shadow=True, max_width=int(w * 0.92),
        )
        # composite RGBA (text) over BGR frame near the bottom
        th, tw = rgba.shape[:2]
        x = max(0, (w - tw) // 2)
        y = max(0, int(h * 0.66))
        x2, y2 = min(w, x + tw), min(h, y + th)
        tw_c, th_c = x2 - x, y2 - y
        if tw_c <= 0 or th_c <= 0:
            return frame_bgr

        text_rgb = rgba[:th_c, :tw_c, :3][:, :, ::-1]   # RGB->BGR
        alpha = (rgba[:th_c, :tw_c, 3:4].astype(np.float32)) / 255.0
        region = frame_bgr[y:y2, x:x2].astype(np.float32)
        blended = region * (1 - alpha) + text_rgb.astype(np.float32) * alpha
        frame_bgr[y:y2, x:x2] = blended.astype("uint8")
        return frame_bgr

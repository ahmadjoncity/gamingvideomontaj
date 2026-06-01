"""AI-powered highlight detection.

The detector scans a clip on a coarse grid (``sample_fps`` frames per second)
and computes four per-window signals:

#. **audio**  -- loudness spikes (gunshots, screams, hit-markers).
#. **motion** -- mean absolute frame difference (camera/character movement).
#. **flash**  -- sudden brightness jumps (kills, abilities, explosions).
#. **text**   -- optional Tesseract OCR matching game keywords (kill feed).

The signals are normalised, fused with preset weights, and segmented into
:class:`~gamemontage.models.Highlight` windows around local score peaks.

None of the heavy libraries are required at import time; missing ones simply
contribute a zero signal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from gamemontage.core.audio_analyzer import AudioAnalyzer
from gamemontage.models import Clip, Highlight, HighlightKind
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

ProgressFn = Callable[[float, str], None]


@dataclass
class DetectionConfig:
    """Knobs for the detector, usually sourced from a game preset."""

    sample_fps: float = 2.0
    window_seconds: float = 2.5
    min_score: float = 0.45
    pad_before: float = 1.2
    pad_after: float = 1.0
    merge_gap: float = 1.0
    weights: dict[str, float] | None = None
    keywords: tuple[str, ...] = ()
    enable_ocr: bool = False

    def normalised_weights(self) -> dict[str, float]:
        w = dict(self.weights or {"audio": 0.4, "motion": 0.3, "flash": 0.2, "text": 0.1})
        if not self.enable_ocr:
            w["text"] = 0.0
        total = sum(max(0.0, v) for v in w.values()) or 1.0
        return {k: max(0.0, v) / total for k, v in w.items()}

    @classmethod
    def from_preset(cls, preset: dict, sample_fps: float, enable_ocr: bool) -> DetectionConfig:
        det = preset.get("detection", {})
        return cls(
            sample_fps=sample_fps,
            window_seconds=det.get("window_seconds", 2.5),
            min_score=det.get("min_score", 0.45),
            pad_before=det.get("pad_before", 1.2),
            pad_after=det.get("pad_after", 1.0),
            merge_gap=det.get("merge_gap", 1.0),
            weights=det.get("weights"),
            keywords=tuple(k.lower() for k in det.get("keywords", [])),
            enable_ocr=enable_ocr,
        )


class HighlightDetector:
    """Detects highlights inside source clips."""

    def __init__(self, config: DetectionConfig | None = None,
                 tesseract_path: str | None = None) -> None:
        self.config = config or DetectionConfig()
        self.audio = AudioAnalyzer()
        if tesseract_path:
            self._configure_tesseract(tesseract_path)

    # ---- public API ---------------------------------------------------------
    def detect_in_clips(self, clips: list[Clip],
                        progress: ProgressFn | None = None,
                        should_cancel: Callable[[], bool] | None = None) -> list[Highlight]:
        results: list[Highlight] = []
        total = len(clips) or 1
        for i, clip in enumerate(clips):
            if should_cancel and should_cancel():
                logger.info("Detection cancelled by user.")
                break
            base = i / total

            def clip_progress(frac: float, msg: str, _b=base, _t=total) -> None:
                if progress:
                    progress(_b + frac / _t, msg)

            results.extend(self.detect_in_clip(clip, clip_progress, should_cancel))
        if progress:
            progress(1.0, f"Found {len(results)} highlights")
        results.sort(key=lambda h: h.score, reverse=True)
        return results

    def detect_in_clip(self, clip: Clip,
                       progress: ProgressFn | None = None,
                       should_cancel: Callable[[], bool] | None = None) -> list[Highlight]:
        logger.info("Detecting highlights in %s", clip.name)
        if progress:
            progress(0.05, f"Analysing audio: {clip.name}")

        audio = self.audio.analyze_video(clip.path) if clip.has_audio else None

        if progress:
            progress(0.2, f"Scanning frames: {clip.name}")
        motion, flash, times, text_hits = self._scan_video(clip, progress, should_cancel)

        if times.size == 0:
            return []

        audio_sig = self._audio_signal(audio, times)
        weights = self.config.normalised_weights()
        fused = (
            weights["audio"] * audio_sig
            + weights["motion"] * motion
            + weights["flash"] * flash
            + weights["text"] * text_hits
        )
        fused = _smooth(fused, win=3)

        highlights = self._segment(clip, times, fused, audio_sig, motion, flash, text_hits)
        logger.info("  -> %d highlights in %s", len(highlights), clip.name)
        return highlights

    # ---- video scanning -----------------------------------------------------
    def _scan_video(self, clip: Clip, progress: ProgressFn | None,
                    should_cancel: Callable[[], bool] | None):
        """Sample frames and compute motion/flash/text arrays aligned to ``times``."""
        empty = np.zeros(0)
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV unavailable; motion/flash detection disabled.")
            return empty, empty, empty, empty

        cap = cv2.VideoCapture(str(clip.path))
        if not cap.isOpened():
            logger.warning("Could not open %s", clip.name)
            return empty, empty, empty, empty

        fps = clip.fps or cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, int(round(fps / max(0.5, self.config.sample_fps))))
        ocr_enabled = self.config.enable_ocr and self._ocr_available()
        # OCR is slow; run it on a coarser grid.
        ocr_every = max(1, int(self.config.sample_fps))  # ~1/sec

        motion_vals: list[float] = []
        flash_vals: list[float] = []
        text_vals: list[float] = []
        times: list[float] = []

        prev_gray = None
        prev_bright = None
        frame_idx = 0
        sample_idx = 0
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0

        try:
            while True:
                ok = cap.grab()
                if not ok:
                    break
                if frame_idx % step != 0:
                    frame_idx += 1
                    continue
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    break

                if should_cancel and should_cancel():
                    break

                small = cv2.resize(frame, (160, 90))
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                bright = float(gray.mean())

                if prev_gray is not None:
                    motion_vals.append(float(np.abs(gray.astype(np.int16)
                                                     - prev_gray.astype(np.int16)).mean()))
                    flash_vals.append(abs(bright - (prev_bright or bright)))
                else:
                    motion_vals.append(0.0)
                    flash_vals.append(0.0)

                # OCR keyword detection (optional, coarse)
                if ocr_enabled and (sample_idx % ocr_every == 0):
                    text_vals.append(self._ocr_keyword_score(frame, cv2))
                else:
                    text_vals.append(text_vals[-1] if text_vals else 0.0)

                times.append(frame_idx / fps)
                prev_gray = gray
                prev_bright = bright
                frame_idx += 1
                sample_idx += 1

                if progress and total_frames:
                    frac = 0.2 + 0.75 * min(1.0, frame_idx / total_frames)
                    if sample_idx % 10 == 0:
                        progress(frac, f"Scanning {clip.name}")
        finally:
            cap.release()

        return (
            _normalise(np.asarray(motion_vals, dtype=float)),
            _normalise(np.asarray(flash_vals, dtype=float)),
            np.asarray(times, dtype=float),
            _clip01(np.asarray(text_vals, dtype=float)),
        )

    # ---- signals ------------------------------------------------------------
    @staticmethod
    def _audio_signal(audio, times: np.ndarray) -> np.ndarray:
        if audio is None or times.size == 0 or audio.loudness.size == 0:
            return np.zeros(times.size)
        sig = np.array([audio.loudness_at(t) for t in times])
        # Emphasise spike neighbourhoods.
        for st in audio.spike_times:
            idx = int(np.argmin(np.abs(times - st)))
            lo, hi = max(0, idx - 1), min(times.size, idx + 2)
            sig[lo:hi] = np.maximum(sig[lo:hi], 0.9)
        return _normalise(sig)

    # ---- segmentation -------------------------------------------------------
    def _segment(self, clip: Clip, times: np.ndarray, fused: np.ndarray,
                 audio_sig: np.ndarray, motion: np.ndarray, flash: np.ndarray,
                 text: np.ndarray) -> list[Highlight]:
        cfg = self.config
        above = fused >= cfg.min_score
        highlights: list[Highlight] = []

        i = 0
        n = times.size
        while i < n:
            if not above[i]:
                i += 1
                continue
            j = i
            while j < n and above[j]:
                j += 1
            seg = slice(i, j)
            peak_local = int(np.argmax(fused[seg])) + i
            score = float(fused[seg].max())
            center = float(times[peak_local])

            start = max(0.0, center - cfg.window_seconds / 2 - cfg.pad_before)
            end = min(clip.duration or times[-1] + 1,
                      center + cfg.window_seconds / 2 + cfg.pad_after)

            kind = self._classify(
                float(audio_sig[peak_local]), float(motion[peak_local]),
                float(flash[peak_local]), float(text[peak_local]),
            )
            highlights.append(
                Highlight(
                    clip_id=clip.id, clip_path=clip.path, start=start, end=end,
                    score=score, kind=kind,
                    audio_score=float(audio_sig[peak_local]),
                    motion_score=float(motion[peak_local]),
                    flash_score=float(flash[peak_local]),
                    text_score=float(text[peak_local]),
                )
            )
            i = j

        return self._merge_overlaps(highlights, cfg.merge_gap)

    @staticmethod
    def _classify(audio: float, motion: float, flash: float, text: float) -> HighlightKind:
        if text > 0.5:
            return HighlightKind.KILL
        if flash > 0.6 and audio > 0.5:
            return HighlightKind.EPIC
        if audio > 0.6:
            return HighlightKind.ACTION
        if motion > 0.6:
            return HighlightKind.ACTION
        return HighlightKind.UNKNOWN

    @staticmethod
    def _merge_overlaps(highlights: list[Highlight], gap: float) -> list[Highlight]:
        if not highlights:
            return []
        highlights.sort(key=lambda h: h.start)
        merged = [highlights[0]]
        for h in highlights[1:]:
            last = merged[-1]
            if h.start <= last.end + gap:
                last.end = max(last.end, h.end)
                if h.score > last.score:
                    last.score = h.score
                    last.kind = h.kind
                    last.audio_score = h.audio_score
                    last.motion_score = h.motion_score
                    last.flash_score = h.flash_score
                    last.text_score = h.text_score
            else:
                merged.append(h)
        return merged

    # ---- OCR ----------------------------------------------------------------
    def _ocr_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            return True
        except ImportError:
            logger.debug("pytesseract not installed; OCR disabled.")
            return False

    @staticmethod
    def _configure_tesseract(path: str) -> None:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = path
        except ImportError:
            pass

    def _ocr_keyword_score(self, frame, cv2) -> float:
        """Return 1.0 if a game keyword appears in the kill-feed region."""
        try:
            import pytesseract
        except ImportError:
            return 0.0
        if not self.config.keywords:
            return 0.0
        try:
            h, w = frame.shape[:2]
            # Kill feed is usually top-right; OCR just that region for speed.
            region = frame[0:int(h * 0.35), int(w * 0.5):w]
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
            text = pytesseract.image_to_string(thresh, config="--psm 6").lower()
            return 1.0 if any(kw in text for kw in self.config.keywords) else 0.0
        except Exception as exc:  # noqa: BLE001
            logger.debug("OCR error: %s", exc)
            return 0.0


# --------------------------------------------------------------------------- #
# small numeric helpers
# --------------------------------------------------------------------------- #
def _normalise(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _clip01(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    return np.clip(arr, 0.0, 1.0)


def _smooth(arr: np.ndarray, win: int = 3) -> np.ndarray:
    if arr.size == 0 or win <= 1:
        return arr
    kernel = np.ones(win) / win
    return np.convolve(arr, kernel, mode="same")

"""Speech-to-text captions using faster-whisper, rendered as animated overlays.

Pipeline:

#. Transcribe the (already rendered) montage's audio with ``faster-whisper``.
#. Group words into short phrases (max ~4 words) for readable, punchy captions.
#. Render each phrase with :mod:`text_render` and pop it in with a small scale
   animation near the lower-third.

If ``faster-whisper`` is not installed, :meth:`transcribe` returns an empty list
and the montage simply ships without captions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gamemontage.core.text_render import render_text_rgba
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CaptionPhrase:
    text: str
    start: float
    end: float


class CaptionGenerator:
    """Transcribes audio and builds caption clips."""

    def __init__(self, model_size: str = "base", device: str = "auto",
                 compute_type: str = "auto", max_words: int = 4) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.max_words = max_words
        self._model = None

    # ---- transcription ------------------------------------------------------
    def available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        device = self.device
        compute_type = self.compute_type
        if device == "auto":
            device, compute_type = self._auto_device(compute_type)
        logger.info("Loading Whisper '%s' on %s (%s)", self.model_size, device, compute_type)
        self._model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        return self._model

    @staticmethod
    def _auto_device(compute_type: str) -> tuple[str, str]:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", (compute_type if compute_type != "auto" else "float16")
        except Exception:  # noqa: BLE001
            pass
        return "cpu", (compute_type if compute_type != "auto" else "int8")

    def transcribe(self, audio_path: Path, language: str | None = None) -> list[CaptionPhrase]:
        if not self.available():
            logger.warning("faster-whisper not installed; skipping captions.")
            return []
        try:
            model = self._load_model()
            segments, _info = model.transcribe(
                str(audio_path), language=language, word_timestamps=True,
                vad_filter=True,
            )
            return self._group_words(segments)
        except Exception as exc:  # noqa: BLE001
            logger.error("Transcription failed: %s", exc)
            return []

    def _group_words(self, segments) -> list[CaptionPhrase]:
        phrases: list[CaptionPhrase] = []
        buf: list = []

        def flush() -> None:
            if not buf:
                return
            text = " ".join(w.word.strip() for w in buf).strip()
            if text:
                phrases.append(CaptionPhrase(text=text, start=buf[0].start, end=buf[-1].end))
            buf.clear()

        for seg in segments:
            words = getattr(seg, "words", None)
            if not words:
                # No word timing -> use the whole segment.
                txt = (seg.text or "").strip()
                if txt:
                    phrases.append(CaptionPhrase(txt, seg.start, seg.end))
                continue
            for w in words:
                buf.append(w)
                ends_sentence = w.word.strip().endswith((".", "!", "?", ","))
                if len(buf) >= self.max_words or ends_sentence:
                    flush()
            flush()
        logger.info("Transcribed %d caption phrases", len(phrases))
        return phrases

    # ---- caption clips ------------------------------------------------------
    def build_caption_clips(
        self,
        phrases: list[CaptionPhrase],
        frame_size: tuple[int, int],
        style: dict | None = None,
    ) -> list:
        """Return MoviePy ImageClips for each phrase, positioned in lower third."""
        if not phrases:
            return []
        from gamemontage.core._moviepy import mpy

        editor = mpy()
        style = style or {}
        w, h = frame_size
        font_size = max(28, int(h * 0.055))
        clips = []

        for ph in phrases:
            try:
                rgba = render_text_rgba(
                    ph.text,
                    font_size=font_size,
                    color=style.get("caption_color", "#FFFFFF"),
                    outline_color=style.get("caption_outline", "#000000"),
                    outline_width=max(3, font_size // 14),
                    shadow=True,
                    max_width=int(w * 0.9),
                )
                duration = max(0.4, ph.end - ph.start)
                img = (
                    editor.ImageClip(rgba)
                    .set_start(ph.start)
                    .set_duration(duration)
                    .set_position(("center", int(h * 0.72)))
                )
                # quick pop-in scale
                img = img.resize(lambda t: 1.0 + 0.12 * max(0.0, 1 - t / 0.18))
                clips.append(img)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Caption clip failed for '%s': %s", ph.text, exc)
        return clips

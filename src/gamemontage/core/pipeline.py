"""High-level orchestration of the full montage workflow.

The :class:`MontagePipeline` ties the engine modules together so both the GUI
and the CLI can drive the exact same logic:

    detect highlights -> build montage -> (captions) -> export -> thumbnail

Progress + cancellation flow through :class:`PipelineCallbacks`, keeping the
engine free of any GUI/threading concerns.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gamemontage.app_config import Settings, load_preset
from gamemontage.core.captions import CaptionGenerator
from gamemontage.core.exporter import Exporter
from gamemontage.core.highlight_detector import DetectionConfig, HighlightDetector
from gamemontage.core.montage_creator import MontageCreator, MontageOptions
from gamemontage.core.thumbnail import ThumbnailGenerator
from gamemontage.models import Highlight, Project
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineCallbacks:
    """Hooks the caller can supply to observe / control a run."""

    on_progress: Callable[[str, float, str], None] | None = None  # (stage, 0..1, msg)
    on_log: Callable[[str], None] | None = None
    cancel_check: Callable[[], bool] | None = None

    def progress(self, stage: str, frac: float, msg: str) -> None:
        if self.on_progress:
            self.on_progress(stage, max(0.0, min(1.0, frac)), msg)

    def log(self, msg: str) -> None:
        logger.info(msg)
        if self.on_log:
            self.on_log(msg)

    def cancelled(self) -> bool:
        return bool(self.cancel_check and self.cancel_check())


@dataclass
class PipelineResult:
    montage_path: Path | None = None
    thumbnail_path: Path | None = None
    highlights: list[Highlight] = field(default_factory=list)
    cancelled: bool = False
    error: str | None = None


class MontagePipeline:
    """Drives detection, assembly and export for a :class:`Project`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()

    # ---- step 1: detection --------------------------------------------------
    def detect_highlights(self, project: Project,
                          callbacks: PipelineCallbacks | None = None) -> list[Highlight]:
        cb = callbacks or PipelineCallbacks()
        preset = load_preset(project.game_type)
        config = DetectionConfig.from_preset(
            preset,
            sample_fps=self.settings.detection_sample_fps,
            enable_ocr=self.settings.enable_ocr,
        )
        detector = HighlightDetector(
            config,
            tesseract_path=self.settings.tesseract_path or None,
        )
        cb.log(f"Detecting highlights for game preset '{project.game_type}'")

        def prog(frac: float, msg: str) -> None:
            cb.progress("detect", frac, msg)

        highlights = detector.detect_in_clips(
            project.enabled_clips(), progress=prog, should_cancel=cb.cancelled
        )
        project.highlights = highlights
        cb.log(f"Detected {len(highlights)} highlights")
        return highlights

    # ---- step 2+3: build + export ------------------------------------------
    def build_and_export(self, project: Project,
                         callbacks: PipelineCallbacks | None = None) -> PipelineResult:
        cb = callbacks or PipelineCallbacks()
        result = PipelineResult(highlights=project.highlights)
        try:
            if cb.cancelled():
                result.cancelled = True
                return result

            preset = load_preset(project.style_preset or project.game_type)
            export = project.export
            frame_size = export.frame_size()

            options = MontageOptions.from_preset(
                preset, aspect=export.aspect, frame_size=frame_size,
                fps=export.fps, music_path=project.music_path,
            )
            # apply GUI overrides (color grade, transition, target count, etc.)
            for key, value in (project.montage_overrides or {}).items():
                if hasattr(options, key) and value is not None:
                    setattr(options, key, value)
            creator = MontageCreator(options)

            cb.progress("build", 0.0, "Selecting highlights")
            montage = creator.build(
                project.highlights,
                progress=lambda f, m: cb.progress("build", f, m),
                should_cancel=cb.cancelled,
            )

            if cb.cancelled():
                result.cancelled = True
                _safe_close(montage)
                return result

            # optional captions
            if self.settings.enable_captions:
                montage = self._maybe_add_captions(montage, frame_size, preset, cb)

            # export
            out_dir = project.output_dir or self.settings.resolved_output_dir()
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_name = _safe_filename(project.name)
            out_path = out_dir / f"{safe_name}.mp4"

            exporter = Exporter(export)
            cb.progress("export", 0.0, "Rendering montage")
            exporter.export(
                montage, out_path,
                progress=lambda f, m: cb.progress("export", f, m),
                threads=self.settings.max_threads,
            )
            result.montage_path = out_path

            # thumbnail
            if export.generate_thumbnail and project.highlights:
                cb.progress("thumbnail", 0.5, "Generating thumbnail")
                thumb = out_dir / f"{safe_name}_thumbnail.jpg"
                title = preset.get("style", {}).get("intro_text", "") or ""
                tgen = ThumbnailGenerator()
                result.thumbnail_path = tgen.generate(
                    project.highlights, thumb, title=title,
                )
            cb.progress("done", 1.0, "Done")
            cb.log(f"Montage exported to {out_path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline failed")
            result.error = str(exc)
            cb.log(f"ERROR: {exc}")
        return result

    # ---- captions helper ----------------------------------------------------
    def _maybe_add_captions(self, montage, frame_size, preset, cb: PipelineCallbacks):
        captioner = CaptionGenerator(
            model_size=self.settings.whisper_model,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
        )
        if not captioner.available():
            cb.log("faster-whisper not installed; skipping captions.")
            return montage
        if montage.audio is None:
            return montage

        cb.progress("captions", 0.1, "Transcribing audio for captions")
        tmp_wav = Path(tempfile.mktemp(suffix=".wav", prefix="gm_caption_"))
        try:
            montage.audio.write_audiofile(str(tmp_wav), logger=None, fps=16000)
            phrases = captioner.transcribe(tmp_wav)
            if not phrases:
                return montage
            from gamemontage.core._moviepy import mpy
            clips = captioner.build_caption_clips(
                phrases, frame_size, style=preset.get("style", {})
            )
            if not clips:
                return montage
            cb.progress("captions", 0.8, f"Rendering {len(clips)} captions")
            composite = mpy().CompositeVideoClip([montage, *clips], size=frame_size)
            composite = composite.set_duration(montage.duration).set_audio(montage.audio)
            composite._gm_sources = getattr(montage, "_gm_sources", [])  # type: ignore
            return composite
        except Exception as exc:  # noqa: BLE001
            logger.debug("Caption stage failed: %s", exc)
            return montage
        finally:
            try:
                tmp_wav.unlink(missing_ok=True)
            except OSError:
                pass

    # ---- one-shot convenience ----------------------------------------------
    def run_all(self, project: Project,
                callbacks: PipelineCallbacks | None = None) -> PipelineResult:
        cb = callbacks or PipelineCallbacks()
        if not project.highlights:
            self.detect_highlights(project, cb)
        if cb.cancelled():
            return PipelineResult(highlights=project.highlights, cancelled=True)
        return self.build_and_export(project, cb)


def _safe_filename(name: str) -> str:
    keep = "-_. ()"
    cleaned = "".join(c for c in name if c.isalnum() or c in keep).strip()
    return cleaned.replace(" ", "_") or "montage"


def _safe_close(clip) -> None:
    try:
        for src in getattr(clip, "_gm_sources", []):
            try:
                src.close()
            except Exception:  # noqa: BLE001
                pass
        clip.close()
    except Exception:  # noqa: BLE001
        pass

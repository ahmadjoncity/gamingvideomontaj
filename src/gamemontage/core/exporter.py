"""Render a montage clip to a file with the chosen codec/aspect/resolution.

Wraps MoviePy's ``write_videofile`` with:

* logical -> concrete codec selection (CPU libx264/libx265 or GPU NVENC/QSV…),
* sensible default bitrates per resolution,
* a progress bridge so the GUI can show a live percentage,
* best-effort cleanup of the source readers opened during montage building.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gamemontage.models import ExportSettings
from gamemontage.utils.ffmpeg_utils import pick_encoder
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

ProgressFn = Callable[[float, str], None]

# Reasonable target bitrates (video) by resolution long-edge.
_DEFAULT_BITRATE = {
    1280: "6M",
    1920: "12M",
    2560: "24M",
    3840: "45M",
}


class _ProgressLogger:
    """A ``proglog`` logger that forwards MoviePy render progress to a callback."""

    def __init__(self, callback: ProgressFn | None, message: str) -> None:
        self.callback = callback
        self.message = message
        self._total = None

    def __call__(self, **kwargs):  # proglog calls the logger like a function
        return self

    # proglog ProgressBarLogger-compatible hooks ----------------------------
    def iter_bar(self, **kwargs):
        # Yield through items while reporting progress.
        for _key, iterable in kwargs.items():
            try:
                items = list(iterable)
            except TypeError:
                items = iterable
            total = len(items) if hasattr(items, "__len__") else None
            for i, item in enumerate(items):
                if self.callback and total:
                    self.callback(min(1.0, (i + 1) / total), self.message)
                yield item
            return

    def bars_callback(self, *args, **kwargs):
        pass

    def callback(self, *args, **kwargs):
        pass


class Exporter:
    def __init__(self, settings: ExportSettings) -> None:
        self.settings = settings

    def export(self, montage, out_path: Path,
               progress: ProgressFn | None = None,
               threads: int = 4) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        codec = pick_encoder(self.settings.codec, self.settings.use_gpu)
        bitrate = self.settings.bitrate or _DEFAULT_BITRATE.get(
            self.settings.resolution.long_edge, "12M"
        )

        logger.info(
            "Exporting -> %s | %s | %s | %s | %dfps",
            out_path.name, self.settings.resolution.value,
            self.settings.aspect.value, codec, self.settings.fps,
        )

        if progress:
            progress(0.0, "Rendering video")

        temp_audio = out_path.with_suffix(".temp-audio.m4a")
        try:
            montage.write_videofile(
                str(out_path),
                fps=self.settings.fps,
                codec=codec,
                bitrate=bitrate,
                audio_codec="aac",
                audio_bitrate=self.settings.audio_bitrate,
                threads=max(1, threads),
                preset="medium" if codec.startswith("lib") else None,
                temp_audiofile=str(temp_audio),
                remove_temp=True,
                logger=_ProgressLogger(progress, "Rendering video"),
                ffmpeg_params=self._ffmpeg_params(codec),
            )
        finally:
            self._cleanup(montage)
            try:
                temp_audio.unlink(missing_ok=True)
            except OSError:
                pass

        if progress:
            progress(1.0, "Export complete")
        logger.info("Export finished: %s", out_path)
        return out_path

    def _ffmpeg_params(self, codec: str) -> list[str]:
        params = ["-pix_fmt", "yuv420p"]
        if codec == "libx265" or codec.startswith("hevc"):
            # ensure broad player compatibility for HEVC in mp4
            params += ["-tag:v", "hvc1"]
        return params

    @staticmethod
    def _cleanup(montage) -> None:
        """Close the montage and any source readers it kept alive."""
        try:
            sources = getattr(montage, "_gm_sources", [])
            for src in sources:
                try:
                    src.close()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            try:
                montage.close()
            except Exception:  # noqa: BLE001
                pass

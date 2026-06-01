"""FFmpeg discovery and capability probing.

MoviePy needs an FFmpeg binary. We prefer one on the system ``PATH`` and fall
back to the binary bundled by ``imageio-ffmpeg``. We also probe for hardware
encoders (NVENC / QSV / AMF) so the exporter can offer GPU acceleration.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
from pathlib import Path

from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """Return a usable ffmpeg executable path, or ``None`` if unavailable."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe

    # Fall back to imageio-ffmpeg's bundled binary.
    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    except Exception as exc:  # pragma: no cover
        logger.debug("imageio-ffmpeg lookup failed: %s", exc)

    logger.warning("FFmpeg not found. Export/transcode features will not work.")
    return None


@functools.lru_cache(maxsize=1)
def ffmpeg_available() -> bool:
    return find_ffmpeg() is not None


@functools.lru_cache(maxsize=1)
def available_encoders() -> tuple[str, ...]:
    """Return the set of video encoders reported by ``ffmpeg -encoders``."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return ()
    try:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        encoders = []
        for line in out.stdout.splitlines():
            parts = line.split()
            # Lines look like: " V..... libx264   H.264 ..."
            if len(parts) >= 2 and parts[0].startswith("V"):
                encoders.append(parts[1])
        return tuple(encoders)
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to probe encoders: %s", exc)
        return ()


def pick_encoder(codec: str, prefer_gpu: bool) -> str:
    """Choose the best concrete encoder for a logical codec.

    Parameters
    ----------
    codec:
        Either ``"h264"`` or ``"h265"`` / ``"hevc"``.
    prefer_gpu:
        When ``True`` and a hardware encoder exists, use it.
    """
    codec = codec.lower()
    encoders = available_encoders()

    h264_gpu = ["h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"]
    h265_gpu = ["hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox"]

    if codec in ("h265", "hevc"):
        if prefer_gpu:
            for enc in h265_gpu:
                if enc in encoders:
                    logger.info("Using GPU encoder: %s", enc)
                    return enc
        return "libx265"

    # default: h264
    if prefer_gpu:
        for enc in h264_gpu:
            if enc in encoders:
                logger.info("Using GPU encoder: %s", enc)
                return enc
    return "libx264"

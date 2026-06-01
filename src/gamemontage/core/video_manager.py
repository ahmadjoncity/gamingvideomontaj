"""Import source clips, probe their metadata, and generate thumbnails.

Probing tries ffprobe first (fast, no decode) and falls back to OpenCV.
Thumbnails are produced with OpenCV and saved as JPEG into a temp cache.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from gamemontage.models import Clip
from gamemontage.utils.ffmpeg_utils import find_ffmpeg
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".flv", ".m4v", ".wmv", ".ts",
}


class VideoManager:
    """Discovers, probes and thumbnails source video files."""

    def __init__(self, thumbnail_dir: Path | None = None) -> None:
        self.thumbnail_dir = thumbnail_dir or Path(tempfile.gettempdir()) / "gamemontage_thumbs"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    # ---- discovery ----------------------------------------------------------
    @staticmethod
    def is_video(path: Path) -> bool:
        return path.suffix.lower() in VIDEO_EXTENSIONS

    def collect_paths(self, inputs: list[str | Path]) -> list[Path]:
        """Expand a mix of files and folders into a flat, de-duplicated list."""
        found: list[Path] = []
        seen: set[Path] = set()
        for item in inputs:
            p = Path(item).expanduser()
            if p.is_dir():
                for child in sorted(p.rglob("*")):
                    if child.is_file() and self.is_video(child) and child not in seen:
                        found.append(child)
                        seen.add(child)
            elif p.is_file() and self.is_video(p) and p not in seen:
                found.append(p)
                seen.add(p)
        return found

    # ---- import -------------------------------------------------------------
    def import_clip(self, path: Path, make_thumbnail: bool = True) -> Clip:
        path = Path(path)
        meta = self._probe(path)
        clip = Clip(
            path=path,
            duration=meta.get("duration", 0.0),
            fps=meta.get("fps", 0.0),
            width=meta.get("width", 0),
            height=meta.get("height", 0),
            has_audio=meta.get("has_audio", True),
        )
        if make_thumbnail:
            clip.thumbnail_path = self.make_thumbnail(clip)
        logger.info(
            "Imported %s (%.1fs, %s @ %.0ffps)",
            clip.name, clip.duration, clip.resolution_label, clip.fps,
        )
        return clip

    def import_many(self, inputs: list[str | Path], make_thumbnail: bool = True) -> list[Clip]:
        clips: list[Clip] = []
        for p in self.collect_paths(inputs):
            try:
                clips.append(self.import_clip(p, make_thumbnail=make_thumbnail))
            except Exception as exc:  # noqa: BLE001 - one bad file shouldn't abort
                logger.error("Skipping %s: %s", p, exc)
        return clips

    # ---- probing ------------------------------------------------------------
    def _probe(self, path: Path) -> dict:
        meta = self._probe_ffprobe(path)
        if meta:
            return meta
        return self._probe_opencv(path)

    def _probe_ffprobe(self, path: Path) -> dict | None:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            return None
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
        if not Path(ffprobe).exists() and ffprobe != "ffprobe":
            ffprobe = "ffprobe"
        try:
            out = subprocess.run(
                [
                    ffprobe, "-v", "error", "-print_format", "json",
                    "-show_format", "-show_streams", str(path),
                ],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if out.returncode != 0:
                return None
            data = json.loads(out.stdout)
            streams = data.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), None)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            if not video:
                return None
            duration = float(data.get("format", {}).get("duration", 0) or 0)
            if not duration:
                duration = float(video.get("duration", 0) or 0)
            return {
                "duration": duration,
                "fps": _parse_fraction(video.get("avg_frame_rate", "0/0")),
                "width": int(video.get("width", 0) or 0),
                "height": int(video.get("height", 0) or 0),
                "has_audio": has_audio,
            }
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, OSError) as exc:
            logger.debug("ffprobe failed for %s: %s", path, exc)
            return None

    def _probe_opencv(self, path: Path) -> dict:
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not available; cannot probe %s", path)
            return {"duration": 0.0, "fps": 0.0, "width": 0, "height": 0, "has_audio": True}

        cap = cv2.VideoCapture(str(path))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            duration = (frames / fps) if fps else 0.0
            return {
                "duration": duration, "fps": fps, "width": width,
                "height": height, "has_audio": True,
            }
        finally:
            cap.release()

    # ---- thumbnails ---------------------------------------------------------
    def make_thumbnail(self, clip: Clip, at_seconds: float | None = None,
                       max_width: int = 320) -> Path | None:
        try:
            import cv2
        except ImportError:
            return None

        ts = at_seconds if at_seconds is not None else max(0.0, clip.duration * 0.35)
        cap = cv2.VideoCapture(str(clip.path))
        try:
            if clip.fps:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(ts * clip.fps))
            else:
                cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok or frame is None:
                return None

            h, w = frame.shape[:2]
            if w > max_width:
                scale = max_width / w
                frame = cv2.resize(frame, (max_width, int(h * scale)))
            out_path = self.thumbnail_dir / f"{clip.id}.jpg"
            cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return out_path
        except Exception as exc:  # noqa: BLE001
            logger.debug("Thumbnail failed for %s: %s", clip.name, exc)
            return None
        finally:
            cap.release()


def _parse_fraction(text: str) -> float:
    """Parse ffprobe frame-rate fractions like ``"30000/1001"``."""
    try:
        if "/" in text:
            num, den = text.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        return float(text)
    except (ValueError, ZeroDivisionError):
        return 0.0

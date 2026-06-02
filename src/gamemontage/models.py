"""Framework-free data models shared across the GameMontage AI layers.

These are plain :mod:`dataclasses` / :class:`enum.Enum` types with no heavy
dependencies, so they can be imported by the engine, the GUI and the tests
without pulling in MoviePy, OpenCV or anything else.

Concepts
--------
* :class:`AspectRatio` / :class:`Resolution` -- export geometry.
* :class:`ExportSettings`                    -- how the final file is rendered.
* :class:`Clip`                               -- a single imported source video.
* :class:`HighlightKind` / :class:`Highlight` -- a detected interesting moment.
* :class:`Project`                            -- the whole editing session.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
class AspectRatio(str, Enum):
    """Target aspect ratio for the rendered montage."""

    LANDSCAPE = "16:9"   # YouTube / Twitch
    VERTICAL = "9:16"    # TikTok / Shorts / Reels
    SQUARE = "1:1"

    @property
    def ratio(self) -> float:
        w, h = (int(part) for part in self.value.split(":"))
        return w / h


class Resolution(str, Enum):
    """Output resolution, expressed by its quality tier."""

    P720 = "720p"
    P1080 = "1080p"
    P1440 = "1440p"
    P4K = "4k"

    @property
    def long_edge(self) -> int:
        """The longer side, in pixels (independent of orientation)."""
        return {
            Resolution.P720: 1280,
            Resolution.P1080: 1920,
            Resolution.P1440: 2560,
            Resolution.P4K: 3840,
        }[self]

    def frame_size(self, aspect: AspectRatio) -> tuple[int, int]:
        """Return ``(width, height)`` for this resolution at ``aspect``.

        The long edge stays fixed per tier; the short edge is derived from the
        aspect ratio and rounded to an even number (required by most codecs).
        """
        le = self.long_edge
        short = _even(round(le * 9 / 16))
        if aspect == AspectRatio.VERTICAL:
            return short, le
        if aspect == AspectRatio.SQUARE:
            return le, le
        # default / landscape
        return le, short


def _even(value: int) -> int:
    """Round down to the nearest even integer (codec-friendly)."""
    value = int(value)
    return value - (value % 2)


# --------------------------------------------------------------------------- #
# Export settings
# --------------------------------------------------------------------------- #
@dataclass
class ExportSettings:
    """How the final montage file should be rendered."""

    aspect: AspectRatio = AspectRatio.LANDSCAPE
    resolution: Resolution = Resolution.P1080
    codec: str = "h264"          # logical: h264 | h265
    fps: int = 30
    use_gpu: bool = False
    generate_thumbnail: bool = True
    bitrate: str | None = None   # blank -> exporter picks a sensible default
    audio_bitrate: str = "192k"

    def frame_size(self) -> tuple[int, int]:
        return self.resolution.frame_size(self.aspect)


# --------------------------------------------------------------------------- #
# Source clips
# --------------------------------------------------------------------------- #
@dataclass
class Clip:
    """A single imported source video and its probed metadata."""

    path: Path
    duration: float = 0.0    # seconds
    fps: float = 0.0
    width: int = 0
    height: int = 0
    has_audio: bool = True
    enabled: bool = True
    thumbnail_path: Path | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def duration_label(self) -> str:
        """Human readable ``M:SS`` (e.g. 75s -> ``1:15``)."""
        total = max(0, int(round(self.duration)))
        minutes, seconds = divmod(total, 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def resolution_label(self) -> str:
        return f"{self.width}x{self.height}"


# --------------------------------------------------------------------------- #
# Highlights
# --------------------------------------------------------------------------- #
class HighlightKind(str, Enum):
    """Classification of a detected highlight (drives overlay text + color)."""

    KILL = "kill"
    CLUTCH = "clutch"
    EPIC = "epic"
    ACE = "ace"
    FUNNY = "funny"
    ACTION = "action"
    UNKNOWN = "unknown"


@dataclass
class Highlight:
    """A scored, interesting time window inside a source clip."""

    clip_id: str
    clip_path: Path
    start: float
    end: float
    score: float
    kind: HighlightKind = HighlightKind.UNKNOWN
    selected: bool = False
    label: str = ""
    # per-signal score breakdown (0..1), filled in by the detector
    audio_score: float = 0.0
    motion_score: float = 0.0
    flash_score: float = 0.0
    text_score: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not isinstance(self.clip_path, Path):
            self.clip_path = Path(self.clip_path)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def timestamp_label(self) -> str:
        """Start time as ``M:SS`` for display."""
        total = max(0, int(round(self.start)))
        minutes, seconds = divmod(total, 60)
        return f"{minutes}:{seconds:02d}"


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #
@dataclass
class Project:
    """The whole editing session: sources, detected highlights and settings."""

    name: str = "Montage"
    game_type: str = "default"
    style_preset: str | None = None
    clips: list[Clip] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    music_path: Path | None = None
    output_dir: Path | None = None
    export: ExportSettings = field(default_factory=ExportSettings)
    # free-form overrides applied to MontageOptions (color grade, transition…)
    montage_overrides: dict | None = None

    # ---- clip helpers -------------------------------------------------------
    def enabled_clips(self) -> list[Clip]:
        return [c for c in self.clips if c.enabled]

    def clip_by_id(self, clip_id: str) -> Clip | None:
        return next((c for c in self.clips if c.id == clip_id), None)

    def add_clip(self, clip: Clip) -> None:
        """Append a clip unless one with the same path is already present."""
        if any(c.path == clip.path for c in self.clips):
            return
        self.clips.append(clip)

    # ---- highlight helpers --------------------------------------------------
    def selected_highlights(self) -> list[Highlight]:
        return [h for h in self.highlights if h.selected]


__all__ = [
    "AspectRatio",
    "Resolution",
    "ExportSettings",
    "Clip",
    "HighlightKind",
    "Highlight",
    "Project",
]

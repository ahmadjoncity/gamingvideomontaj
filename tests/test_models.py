"""Tests for the framework-free data models."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamemontage.models import (  # noqa: E402
    AspectRatio,
    Clip,
    Highlight,
    HighlightKind,
    Project,
    Resolution,
)


def test_resolution_frame_size_landscape():
    assert Resolution.P1080.frame_size(AspectRatio.LANDSCAPE) == (1920, 1080)
    assert Resolution.P4K.frame_size(AspectRatio.LANDSCAPE) == (3840, 2160)


def test_resolution_frame_size_vertical_is_even():
    w, h = Resolution.P1080.frame_size(AspectRatio.VERTICAL)
    assert h == 1920
    assert w % 2 == 0 and h % 2 == 0
    assert w < h  # vertical


def test_square_frame_size():
    assert Resolution.P1080.frame_size(AspectRatio.SQUARE) == (1920, 1920)


def test_clip_labels():
    clip = Clip(path=Path("/tmp/clip.mp4"), duration=75, fps=60, width=1920, height=1080)
    assert clip.name == "clip.mp4"
    assert clip.duration_label == "1:15"
    assert clip.resolution_label == "1920x1080"


def test_project_selection_helpers():
    project = Project()
    c1 = Clip(path=Path("a.mp4"), enabled=True)
    c2 = Clip(path=Path("b.mp4"), enabled=False)
    project.clips = [c1, c2]
    assert project.enabled_clips() == [c1]
    assert project.clip_by_id(c1.id) is c1

    h = Highlight(clip_id=c1.id, clip_path=c1.path, start=1, end=3, score=0.8,
                  kind=HighlightKind.KILL, selected=True)
    project.highlights = [h]
    assert project.selected_highlights() == [h]
    assert abs(h.duration - 2.0) < 1e-9


def test_add_clip_dedupes_by_path():
    project = Project()
    project.add_clip(Clip(path=Path("dup.mp4")))
    project.add_clip(Clip(path=Path("dup.mp4")))
    assert len(project.clips) == 1

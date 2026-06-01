"""Tests for engine logic that does not require video/audio backends.

These cover the numeric + selection logic that drives detection and montage
assembly, using synthetic data so they run fast and dependency-free.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from gamemontage.core.highlight_detector import (  # noqa: E402
    DetectionConfig,
    HighlightDetector,
    _normalise,
    _smooth,
)
from gamemontage.core.montage_creator import MontageCreator, MontageOptions  # noqa: E402
from gamemontage.models import Clip, Highlight, HighlightKind  # noqa: E402


# --------------------------------------------------------------------------- #
# numeric helpers
# --------------------------------------------------------------------------- #
def test_normalise_scales_to_unit_range():
    out = _normalise(np.array([2.0, 4.0, 6.0]))
    assert out.min() == 0.0
    assert out.max() == 1.0


def test_normalise_handles_constant_array():
    out = _normalise(np.array([5.0, 5.0, 5.0]))
    assert np.all(out == 0.0)


def test_smooth_preserves_length():
    arr = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    assert _smooth(arr, win=3).shape == arr.shape


# --------------------------------------------------------------------------- #
# segmentation
# --------------------------------------------------------------------------- #
def test_segment_extracts_peaks_above_threshold():
    detector = HighlightDetector(DetectionConfig(min_score=0.5, window_seconds=2.0,
                                                 pad_before=0.0, pad_after=0.0,
                                                 merge_gap=0.0))
    clip = Clip(path=Path("game.mp4"), duration=20.0, fps=30)
    n = 40
    times = np.linspace(0, 20, n)
    fused = np.zeros(n)
    fused[10:13] = 0.9    # one clear highlight region
    fused[30:32] = 0.8    # another
    zeros = np.zeros(n)

    highlights = detector._segment(clip, times, fused, fused, zeros, zeros, zeros)
    assert len(highlights) == 2
    assert all(h.score >= 0.5 for h in highlights)
    assert all(h.start <= h.end for h in highlights)


def test_classify_kill_from_text_signal():
    detector = HighlightDetector(DetectionConfig())
    assert detector._classify(0.1, 0.1, 0.1, 0.9) == HighlightKind.KILL
    assert detector._classify(0.9, 0.1, 0.9, 0.0) == HighlightKind.EPIC


def test_merge_overlaps_combines_adjacent():
    detector = HighlightDetector(DetectionConfig())
    p = Path("c.mp4")
    hs = [
        Highlight(clip_id="a", clip_path=p, start=0.0, end=3.0, score=0.6),
        Highlight(clip_id="a", clip_path=p, start=3.2, end=5.0, score=0.8),  # within gap
        Highlight(clip_id="a", clip_path=p, start=20.0, end=22.0, score=0.7),
    ]
    merged = detector._merge_overlaps(hs, gap=1.0)
    assert len(merged) == 2
    assert merged[0].end == 5.0
    assert merged[0].score == 0.8  # keeps the higher score


# --------------------------------------------------------------------------- #
# montage selection / ordering
# --------------------------------------------------------------------------- #
def _mk(score: float) -> Highlight:
    return Highlight(clip_id="x", clip_path=Path("x.mp4"), start=0, end=2, score=score)


def test_select_respects_target_count():
    opt = MontageOptions(target_highlights=5, min_highlights=3, max_highlights=8)
    creator = MontageCreator(opt)
    highlights = [_mk(i / 20) for i in range(20)]
    chosen = creator.select_highlights(highlights)
    assert len(chosen) == 5


def test_order_builds_to_peak_last():
    opt = MontageOptions(target_highlights=6, min_highlights=3, max_highlights=8,
                         build_to_peak=True)
    creator = MontageCreator(opt)
    highlights = [_mk(s) for s in [0.2, 0.9, 0.5, 0.7, 0.3, 0.6]]
    ordered = creator.select_highlights(highlights)
    # the single biggest moment should be placed last
    assert ordered[-1].score == max(h.score for h in highlights)


def test_min_highlights_floor_applied():
    opt = MontageOptions(target_highlights=12, min_highlights=6, max_highlights=15)
    creator = MontageCreator(opt)
    highlights = [_mk(0.5) for _ in range(3)]  # fewer than min
    chosen = creator.select_highlights(highlights)
    assert len(chosen) == 3  # cannot exceed what exists

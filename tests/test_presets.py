"""Tests for preset loading and detection config derivation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gamemontage.app_config import CONFIGS_DIR, list_presets, load_preset  # noqa: E402
from gamemontage.core.highlight_detector import DetectionConfig  # noqa: E402


def test_shipped_presets_are_valid_json():
    for path in CONFIGS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "detection" in data
        assert "montage" in data


def test_list_presets_includes_default_and_valorant():
    names = list_presets()
    assert "default" in names
    assert "valorant" in names


def test_load_preset_merges_onto_default():
    preset = load_preset("valorant")
    # value present in valorant.json
    assert preset["detection"]["weights"]["audio"] == 0.45
    # value only in default falls through (overlays section exists)
    assert "overlays" in preset


def test_load_unknown_preset_falls_back():
    preset = load_preset("does-not-exist-xyz")
    assert preset["name"] == "Default"


def test_detection_config_weights_normalise_and_drop_text_without_ocr():
    preset = load_preset("default")
    cfg = DetectionConfig.from_preset(preset, sample_fps=2.0, enable_ocr=False)
    weights = cfg.normalised_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    assert weights["text"] == 0.0  # OCR disabled -> text weight removed


def test_detection_config_keeps_text_with_ocr():
    preset = load_preset("valorant")
    cfg = DetectionConfig.from_preset(preset, sample_fps=2.0, enable_ocr=True)
    weights = cfg.normalised_weights()
    assert weights["text"] > 0.0
    assert abs(sum(weights.values()) - 1.0) < 1e-6

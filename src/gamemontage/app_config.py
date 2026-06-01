"""Application-level configuration: paths, user settings and game presets.

Two distinct concepts live here:

* :class:`Settings` -- persistent *application* settings (model size, device,
  ffmpeg path, last output folder…). Stored in the user config dir.
* *Editing presets* -- per-game JSON templates shipped in ``configs/`` that
  drive detection weights, keywords and overlay style. Loaded on demand.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Filesystem layout
# --------------------------------------------------------------------------- #
def _project_root() -> Path:
    """Repo root (……/gamemontage-ai), works in both source and installed mode."""
    # src/gamemontage/app_config.py -> parents[2] == repo root
    return Path(__file__).resolve().parents[2]


def user_config_dir() -> Path:
    """OS-appropriate per-user config directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "GameMontageAI"
    path.mkdir(parents=True, exist_ok=True)
    return path


PROJECT_ROOT = _project_root()
CONFIGS_DIR = PROJECT_ROOT / "configs"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
DEFAULT_OUTPUT_DIR = Path.home() / "GameMontageAI" / "output"
SETTINGS_FILE = user_config_dir() / "settings.json"


# --------------------------------------------------------------------------- #
# Persistent application settings
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    """User-tunable application settings, persisted to JSON."""

    # AI / captions
    whisper_model: str = "base"            # tiny|base|small|medium|large-v3
    whisper_device: str = "auto"           # auto|cpu|cuda
    whisper_compute_type: str = "auto"     # auto|int8|float16|float32
    enable_captions: bool = True
    enable_ocr: bool = False               # kill-feed OCR (needs tesseract)

    # Performance
    use_gpu_encode: bool = False
    detection_sample_fps: float = 2.0      # frames/sec analysed during detection
    max_threads: int = 4

    # Paths
    ffmpeg_path: str = ""                  # override; blank -> auto-detect
    tesseract_path: str = ""               # override; blank -> auto-detect
    output_dir: str = str(DEFAULT_OUTPUT_DIR)
    music_dir: str = ""                    # local music library

    # Voiceover
    tts_voice: str = "en-US-GuyNeural"

    # UI
    appearance_mode: str = "dark"          # dark|light|system
    color_theme: str = "blue"

    extra: dict[str, Any] = field(default_factory=dict)

    # ---- persistence --------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or SETTINGS_FILE
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                known = {f for f in cls().__dict__}
                kwargs = {k: v for k, v in data.items() if k in known}
                logger.info("Loaded settings from %s", path)
                return cls(**kwargs)
            except (json.JSONDecodeError, TypeError, OSError) as exc:
                logger.warning("Could not read settings (%s); using defaults.", exc)
        return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or SETTINGS_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            logger.info("Saved settings to %s", path)
        except OSError as exc:
            logger.error("Failed to save settings: %s", exc)

    def resolved_output_dir(self) -> Path:
        p = Path(self.output_dir or DEFAULT_OUTPUT_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


# --------------------------------------------------------------------------- #
# Editing presets (per-game JSON templates)
# --------------------------------------------------------------------------- #
DEFAULT_PRESET: dict[str, Any] = {
    "name": "Default",
    "game": "default",
    "description": "Generic montage style that works for any game.",
    "detection": {
        # weights for fusing per-signal scores (auto-normalised)
        "weights": {"audio": 0.4, "motion": 0.3, "flash": 0.2, "text": 0.1},
        "min_score": 0.45,
        "window_seconds": 2.5,
        "pad_before": 1.2,
        "pad_after": 1.0,
        "merge_gap": 1.0,
        "keywords": ["kill", "killed", "headshot", "wins", "victory", "eliminated"],
    },
    "montage": {
        "target_highlights": 12,
        "min_highlights": 6,
        "max_highlights": 15,
        "slowmo_on_peak": True,
        "punch_zoom": True,
        "shake": True,
        "transition": "zoom",          # zoom|glitch|fade|cut
        "build_to_peak": True,
    },
    "style": {
        "color_grade": "vibrant",      # vibrant|cinematic|hdr|none
        "caption_color": "#FFFFFF",
        "caption_highlight": "#FFE14D",
        "caption_outline": "#000000",
        "overlay_color": "#00E5FF",
        "intro_text": "",
    },
    "overlays": {
        "kill": "ELIMINATED",
        "clutch": "CLUTCH!",
        "epic": "INSANE",
        "ace": "ACE!",
    },
}


def list_presets() -> list[str]:
    """Return preset names available in the configs directory (without .json)."""
    if not CONFIGS_DIR.exists():
        return ["default"]
    names = sorted(p.stem for p in CONFIGS_DIR.glob("*.json"))
    return names or ["default"]


def load_preset(name_or_path: str | Path) -> dict[str, Any]:
    """Load an editing preset by game name or explicit path, merged onto defaults."""
    path = Path(name_or_path)
    if not path.suffix:  # a bare name like "valorant"
        path = CONFIGS_DIR / f"{name_or_path}.json"

    preset = json.loads(json.dumps(DEFAULT_PRESET))  # deep copy
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            _deep_merge(preset, user)
            logger.info("Loaded preset '%s'", path.stem)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load preset %s (%s); using default.", path, exc)
    else:
        logger.info("Preset '%s' not found; using built-in default.", name_or_path)
    return preset


def save_preset(name: str, preset: dict[str, Any]) -> Path:
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIGS_DIR / f"{name}.json"
    path.write_text(json.dumps(preset, indent=2), encoding="utf-8")
    logger.info("Saved preset to %s", path)
    return path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base`` (in place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base

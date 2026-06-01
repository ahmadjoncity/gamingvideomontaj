"""GameMontage AI (yoki AutoGamerEdit).

An AI-powered desktop application that automatically edits raw gaming footage
into fast-paced montages for YouTube, TikTok and Shorts.

The package is intentionally modular:

* :mod:`gamemontage.core`   -- the editing engine (detection, montage, export).
* :mod:`gamemontage.gui`    -- the CustomTkinter desktop interface.
* :mod:`gamemontage.models` -- plain dataclasses shared across layers.
* :mod:`gamemontage.utils`  -- logging + ffmpeg helpers.

Heavy / optional dependencies (faster-whisper, pytesseract, edge-tts) are
imported lazily so the core experience runs without them installed.
"""

from __future__ import annotations

__all__ = ["__version__", "APP_NAME", "APP_SLUG"]

__version__ = "0.1.0"

APP_NAME = "GameMontage AI"
APP_SLUG = "gamemontage-ai"

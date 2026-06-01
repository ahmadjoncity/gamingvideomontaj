"""Centralised, colourised logging for GameMontage AI.

Use :func:`get_logger` everywhere instead of the stdlib ``logging`` directly so
that log formatting / level is configured once.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

# ANSI colours for nicer console output (auto-disabled when not a TTY).
_COLORS = {
    "DEBUG": "\033[37m",      # grey
    "INFO": "\033[36m",       # cyan
    "WARNING": "\033[33m",    # yellow
    "ERROR": "\033[31m",      # red
    "CRITICAL": "\033[41m",   # red background
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Adds ANSI colour to the level name when stdout is a terminal."""

    def __init__(self, use_color: bool, fmt: str, datefmt: str) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        if self.use_color:
            color = _COLORS.get(record.levelname, "")
            record.levelname = f"{color}{record.levelname:<8}{_RESET}"
        else:
            record.levelname = f"{record.levelname:<8}"
        return super().format(record)


def configure_logging(level: str | int = "INFO", log_file: Path | None = None) -> None:
    """Configure root logging once. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("gamemontage")
    root.setLevel(level)
    root.propagate = False

    use_color = sys.stdout is not None and sys.stdout.isatty() and os.name != "nt"
    console_fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%H:%M:%S"

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColorFormatter(use_color, console_fmt, datefmt))
    root.addHandler(console)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
                )
            )
            root.addHandler(file_handler)
        except OSError:
            # Logging to file is best-effort; never crash the app over it.
            pass

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, configuring logging on first use."""
    if not _CONFIGURED:
        configure_logging()
    if not name.startswith("gamemontage"):
        name = f"gamemontage.{name}"
    return logging.getLogger(name)

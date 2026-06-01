"""Lazy MoviePy loader.

MoviePy (and its FFmpeg backend) is heavy, so we import it lazily and surface a
single, friendly error if it is missing. All engine modules should obtain
MoviePy classes through :func:`mpy` rather than importing ``moviepy.editor``
directly -- this keeps the import cost off the GUI start-up path and makes the
"not installed" experience consistent.
"""

from __future__ import annotations

import functools
from types import ModuleType


class MoviePyUnavailable(RuntimeError):
    """Raised when a feature needs MoviePy but it isn't importable."""


@functools.lru_cache(maxsize=1)
def mpy() -> ModuleType:
    """Return the ``moviepy.editor`` module, raising a clear error if missing."""
    try:
        import moviepy.editor as editor  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise MoviePyUnavailable(
            "MoviePy is required for this operation. Install it with:\n"
            "    pip install 'moviepy>=1.0.3,<2.0.0'"
        ) from exc
    return editor


def moviepy_available() -> bool:
    try:
        mpy()
        return True
    except MoviePyUnavailable:
        return False

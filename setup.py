"""Backwards-compatible setup shim.

Project metadata lives in ``pyproject.toml``. This file exists so that
legacy tooling (``python setup.py ...``) and ``pip install -e .`` on older
setuptools keep working.
"""

from setuptools import setup

if __name__ == "__main__":
    setup()

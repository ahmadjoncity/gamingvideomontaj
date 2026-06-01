#!/usr/bin/env python3
"""GameMontage AI - desktop launcher.

Run this file to start the GUI:

    python main.py

It adds the ``src`` directory to ``sys.path`` so the app runs straight from a
git checkout without needing ``pip install -e .`` first.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from a source checkout (src-layout).
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> int:
    from gamemontage.__main__ import main as _main

    return _main()


if __name__ == "__main__":
    raise SystemExit(main())

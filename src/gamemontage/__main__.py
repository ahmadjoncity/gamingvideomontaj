"""Console entry point: ``python -m gamemontage`` and the ``gamemontage`` script.

Launches the GUI by default. If GUI dependencies are missing it prints a helpful
message and points the user at the CLI.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from gamemontage.gui.app import run_app
    except Exception as exc:  # pragma: no cover - import-time guard
        print("Failed to start the GameMontage AI GUI.")
        print(f"Reason: {exc}")
        print(
            "\nMake sure GUI dependencies are installed:\n"
            "    pip install -r requirements.txt\n\n"
            "You can still use the headless pipeline:\n"
            "    python -m gamemontage.cli build --help"
        )
        return 1

    return run_app()


if __name__ == "__main__":
    sys.exit(main())

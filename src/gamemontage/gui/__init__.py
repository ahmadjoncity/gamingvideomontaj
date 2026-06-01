"""CustomTkinter desktop interface for GameMontage AI."""

__all__ = ["run_app"]


def run_app() -> int:  # pragma: no cover - thin wrapper
    from gamemontage.gui.app import run_app as _run

    return _run()

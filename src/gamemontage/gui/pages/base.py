"""Common base class for all GUI pages."""

from __future__ import annotations

import customtkinter as ctk

from gamemontage.gui.controller import AppController
from gamemontage.gui.theme import COLORS


class BasePage(ctk.CTkFrame):
    """A page hosted in the app's content area.

    Subclasses implement :meth:`build` to construct their widgets and may
    implement :meth:`on_show` to refresh when navigated to.
    """

    title: str = "Page"

    def __init__(self, master, controller: AppController, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg"])
        super().__init__(master, **kwargs)
        self.controller = controller
        self.build()

    def build(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def on_show(self) -> None:
        """Hook called every time the page becomes visible."""

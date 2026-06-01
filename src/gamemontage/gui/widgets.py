"""Reusable CustomTkinter widgets for a consistent look.

Kept dependency-light: only ``customtkinter`` + ``Pillow`` (for thumbnails).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from gamemontage.gui.theme import COLORS, font
from gamemontage.models import Clip, Highlight
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


class Card(ctk.CTkFrame):
    """A rounded surface panel."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["surface"])
        kwargs.setdefault("corner_radius", 14)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", COLORS["border"])
        super().__init__(master, **kwargs)


class SectionTitle(ctk.CTkFrame):
    """A page header with title + subtitle."""

    def __init__(self, master, title: str, subtitle: str = "", **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text=title, font=font("title"),
                     text_color=COLORS["text"], anchor="w").pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, font=font("body"),
                         text_color=COLORS["text_dim"], anchor="w").pack(anchor="w")


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["primary"])
        kwargs.setdefault("hover_color", COLORS["primary_hover"])
        kwargs.setdefault("text_color", "#04141A")
        kwargs.setdefault("font", font("body_bold"))
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("height", 42)
        super().__init__(master, **kwargs)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["surface_alt"])
        kwargs.setdefault("hover_color", COLORS["border"])
        kwargs.setdefault("text_color", COLORS["text"])
        kwargs.setdefault("font", font("body_bold"))
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("height", 42)
        super().__init__(master, **kwargs)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["danger"])
        kwargs.setdefault("hover_color", COLORS["danger_hover"])
        kwargs.setdefault("text_color", "#FFFFFF")
        kwargs.setdefault("font", font("body_bold"))
        kwargs.setdefault("corner_radius", 10)
        kwargs.setdefault("height", 42)
        super().__init__(master, **kwargs)


class StatPill(Card):
    """A compact metric display: a big value over a label."""

    def __init__(self, master, label: str, value: str = "0", **kwargs):
        super().__init__(master, **kwargs)
        self.value_lbl = ctk.CTkLabel(self, text=value, font=font("h1"),
                                      text_color=COLORS["primary"])
        self.value_lbl.pack(padx=18, pady=(14, 0))
        ctk.CTkLabel(self, text=label, font=font("small"),
                     text_color=COLORS["text_dim"]).pack(padx=18, pady=(0, 14))

    def set_value(self, value: str) -> None:
        self.value_lbl.configure(text=value)


def load_thumbnail(path: Path | None, size: tuple[int, int]) -> ctk.CTkImage | None:
    """Load an image file into a CTkImage, or None on failure."""
    if not path or not Path(path).exists():
        return None
    try:
        from PIL import Image

        img = Image.open(path)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Thumbnail load failed for %s: %s", path, exc)
        return None


class ClipCard(Card):
    """A row representing one source clip: thumbnail, metadata, toggle, remove."""

    def __init__(self, master, clip: Clip,
                 on_remove: Callable[[str], None] | None = None,
                 on_toggle: Callable[[str, bool], None] | None = None, **kwargs):
        super().__init__(master, **kwargs)
        self.clip = clip
        self.grid_columnconfigure(1, weight=1)

        # thumbnail
        thumb = load_thumbnail(clip.thumbnail_path, (128, 72))
        thumb_holder = ctk.CTkLabel(
            self, text="" if thumb else "🎬", image=thumb,
            width=128, height=72, fg_color=COLORS["bg_alt"], corner_radius=8,
            font=("", 28),
        )
        thumb_holder.image = thumb  # keep ref
        thumb_holder.grid(row=0, column=0, rowspan=2, padx=12, pady=12)

        # name + meta
        ctk.CTkLabel(self, text=_ellipsize(clip.name, 46), font=font("body_bold"),
                     text_color=COLORS["text"], anchor="w").grid(
            row=0, column=1, sticky="sw", padx=(4, 8), pady=(12, 0))
        meta = f"{clip.duration_label}   •   {clip.resolution_label}   •   {clip.fps:.0f} fps"
        ctk.CTkLabel(self, text=meta, font=font("small"),
                     text_color=COLORS["text_dim"], anchor="w").grid(
            row=1, column=1, sticky="nw", padx=(4, 8), pady=(0, 12))

        # include toggle
        self.toggle_var = ctk.BooleanVar(value=clip.enabled)

        def _toggle() -> None:
            clip.enabled = self.toggle_var.get()
            if on_toggle:
                on_toggle(clip.id, clip.enabled)

        ctk.CTkSwitch(self, text="Use", variable=self.toggle_var, command=_toggle,
                      font=font("small"), progress_color=COLORS["primary"],
                      width=60).grid(row=0, column=2, rowspan=2, padx=6)

        if on_remove:
            ctk.CTkButton(self, text="✕", width=34, height=34, corner_radius=8,
                          fg_color=COLORS["surface_alt"], hover_color=COLORS["danger"],
                          text_color=COLORS["text_dim"], font=font("body_bold"),
                          command=lambda: on_remove(clip.id)).grid(
                row=0, column=3, rowspan=2, padx=(4, 12))


class HighlightCard(Card):
    """A row for a detected highlight: select toggle, score bar, signal breakdown."""

    KIND_COLORS = {
        "kill": COLORS["danger"],
        "clutch": COLORS["warning"],
        "epic": COLORS["secondary"],
        "funny": COLORS["success"],
        "action": COLORS["primary"],
        "unknown": COLORS["text_faint"],
    }

    def __init__(self, master, highlight: Highlight,
                 on_toggle: Callable[[str, bool], None] | None = None, **kwargs):
        super().__init__(master, **kwargs)
        self.highlight = highlight
        self.grid_columnconfigure(2, weight=1)

        self.sel_var = ctk.BooleanVar(value=highlight.selected)

        def _toggle() -> None:
            highlight.selected = self.sel_var.get()
            if on_toggle:
                on_toggle(highlight.id, highlight.selected)

        ctk.CTkCheckBox(self, text="", variable=self.sel_var, command=_toggle,
                        width=24, checkbox_width=22, checkbox_height=22,
                        fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"]
                        ).grid(row=0, column=0, rowspan=2, padx=(14, 6), pady=12)

        # kind badge
        kind = highlight.kind.value
        badge = ctk.CTkLabel(self, text=kind.upper(), font=font("small"),
                             text_color="#0B0C10",
                             fg_color=self.KIND_COLORS.get(kind, COLORS["text_faint"]),
                             corner_radius=6, width=70)
        badge.grid(row=0, column=1, rowspan=2, padx=6, pady=12, ipady=4)

        # time + duration
        info = f"@ {highlight.timestamp_label}   •   {highlight.duration:.1f}s   •   {Path(highlight.clip_path).name}"
        ctk.CTkLabel(self, text=_ellipsize(info, 60), font=font("body"),
                     text_color=COLORS["text"], anchor="w").grid(
            row=0, column=2, sticky="sw", padx=8, pady=(12, 0))

        # signal breakdown
        sig = (f"audio {highlight.audio_score:.2f}   motion {highlight.motion_score:.2f}   "
               f"flash {highlight.flash_score:.2f}   text {highlight.text_score:.2f}")
        ctk.CTkLabel(self, text=sig, font=font("small"),
                     text_color=COLORS["text_dim"], anchor="w").grid(
            row=1, column=2, sticky="nw", padx=8, pady=(0, 12))

        # score bar + value
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=3, rowspan=2, padx=(8, 16), pady=12)
        ctk.CTkLabel(right, text=f"{highlight.score:.0%}", font=font("h2"),
                     text_color=COLORS["primary"]).pack()
        bar = ctk.CTkProgressBar(right, width=120, height=8,
                                 progress_color=COLORS["primary"])
        bar.set(highlight.score)
        bar.pack(pady=(4, 0))

    def set_selected(self, value: bool) -> None:
        self.sel_var.set(value)
        self.highlight.selected = value


def _ellipsize(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"

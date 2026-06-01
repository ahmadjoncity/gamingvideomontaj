"""Import & manage source clips."""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from gamemontage.core.video_manager import VIDEO_EXTENSIONS
from gamemontage.gui.controller import EVT_CLIPS
from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.theme import COLORS, font
from gamemontage.gui.widgets import (
    ClipCard,
    GhostButton,
    PrimaryButton,
    SectionTitle,
    StatPill,
)


class ImportPage(BasePage):
    title = "Import"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)
        SectionTitle(header, "Import Footage",
                     "Add raw gameplay files or a whole folder to get started."
                     ).grid(row=0, column=0, sticky="w")

        # action + stats row
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=28, pady=8)
        bar.grid_columnconfigure(4, weight=1)

        PrimaryButton(bar, text="＋  Add Files", width=150,
                      command=self._add_files).grid(row=0, column=0, padx=(0, 10))
        GhostButton(bar, text="📁  Add Folder", width=150,
                    command=self._add_folder).grid(row=0, column=1, padx=10)
        GhostButton(bar, text="🗑  Clear", width=110,
                    command=self.controller.clear_clips).grid(row=0, column=2, padx=10)

        self.clip_stat = StatPill(bar, "Clips", "0")
        self.clip_stat.grid(row=0, column=5, padx=(10, 6), sticky="e")
        self.dur_stat = StatPill(bar, "Total Duration", "0:00")
        self.dur_stat.grid(row=0, column=6, padx=6, sticky="e")

        # clip list (scrollable)
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_alt"], corner_radius=14,
            label_text="Library", label_font=font("h2"),
            label_text_color=COLORS["text_dim"],
        )
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=28, pady=(8, 24))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self._empty = ctk.CTkLabel(
            self.list_frame,
            text="No clips yet.\n\nDrop in some gameplay with “Add Files” or “Add Folder”.",
            font=font("body"), text_color=COLORS["text_faint"], justify="center",
        )
        self._empty.grid(row=0, column=0, pady=80)

        self.controller.subscribe(EVT_CLIPS, self._render_clips)

    # ---- actions ------------------------------------------------------------
    def _add_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(VIDEO_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Select gameplay videos",
            filetypes=[("Video files", patterns), ("All files", "*.*")],
        )
        if paths:
            self.controller.add_inputs(list(paths))

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select a folder of gameplay")
        if folder:
            self.controller.add_inputs([folder])

    # ---- rendering ----------------------------------------------------------
    def _render_clips(self, clips) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        if not clips:
            self._empty = ctk.CTkLabel(
                self.list_frame,
                text="No clips yet.\n\nDrop in some gameplay with “Add Files” or “Add Folder”.",
                font=font("body"), text_color=COLORS["text_faint"], justify="center",
            )
            self._empty.grid(row=0, column=0, pady=80)
        else:
            for i, clip in enumerate(clips):
                card = ClipCard(
                    self.list_frame, clip,
                    on_remove=self.controller.remove_clip,
                )
                card.grid(row=i, column=0, sticky="ew", pady=6, padx=6)

        self.clip_stat.set_value(str(len(clips)))
        self.dur_stat.set_value(_fmt_duration(sum(c.duration for c in clips)))

    def on_show(self) -> None:
        self._render_clips(self.controller.project.clips)


def _fmt_duration(seconds: float) -> str:
    total = int(round(seconds))
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"

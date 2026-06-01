"""Detect and review AI highlights."""

from __future__ import annotations

import customtkinter as ctk

from gamemontage.gui.controller import EVT_BUSY, EVT_HIGHLIGHTS, EVT_PROGRESS
from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.theme import COLORS, GAME_TYPES, font
from gamemontage.gui.widgets import (
    DangerButton,
    GhostButton,
    HighlightCard,
    PrimaryButton,
    SectionTitle,
    StatPill,
)


class HighlightsPage(BasePage):
    title = "Highlights"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        SectionTitle(
            self, "AI Highlight Detection",
            "Pick your game, then let GameMontage find the kills, clutches and epic moments.",
        ).grid(row=0, column=0, sticky="w", padx=28, pady=(24, 8))

        # controls
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=28, pady=8)
        controls.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(controls, text="Game Type", font=font("small"),
                     text_color=COLORS["text_dim"]).grid(row=0, column=0, sticky="w", padx=(2, 6))
        self.game_var = ctk.StringVar(value=self.controller.project.game_type)
        ctk.CTkOptionMenu(controls, values=GAME_TYPES, variable=self.game_var,
                          command=self._on_game_change, width=160,
                          fg_color=COLORS["surface_alt"], button_color=COLORS["secondary"],
                          button_hover_color=COLORS["secondary_hover"],
                          font=font("body")).grid(row=1, column=0, padx=(2, 16))

        ctk.CTkLabel(controls, text="Scan Detail (fps)", font=font("small"),
                     text_color=COLORS["text_dim"]).grid(row=0, column=1, sticky="w")
        self.fps_value = ctk.CTkLabel(controls, text=f"{self.controller.settings.detection_sample_fps:.1f}",
                                      font=font("body_bold"), text_color=COLORS["primary"])
        self.fps_value.grid(row=0, column=2, sticky="w")
        self.fps_slider = ctk.CTkSlider(controls, from_=0.5, to=6.0, number_of_steps=11,
                                        width=160, command=self._on_fps_change,
                                        progress_color=COLORS["primary"],
                                        button_color=COLORS["primary"])
        self.fps_slider.set(self.controller.settings.detection_sample_fps)
        self.fps_slider.grid(row=1, column=1, columnspan=2, padx=(0, 16), sticky="w")

        self.ocr_var = ctk.BooleanVar(value=self.controller.settings.enable_ocr)
        ctk.CTkSwitch(controls, text="Kill-feed OCR", variable=self.ocr_var,
                      command=self._on_ocr_change, font=font("body"),
                      progress_color=COLORS["secondary"]).grid(
            row=1, column=3, padx=8, sticky="w")

        self.detect_btn = PrimaryButton(controls, text="⚡  Detect Highlights",
                                        width=200, command=self.controller.detect_highlights)
        self.detect_btn.grid(row=1, column=7, sticky="e", padx=(8, 0))
        self.cancel_btn = DangerButton(controls, text="✕ Cancel", width=110,
                                       command=self.controller.cancel)
        self.cancel_btn.grid(row=1, column=8, sticky="e", padx=(8, 0))
        self.cancel_btn.grid_remove()

        # progress + stats
        status = ctk.CTkFrame(self, fg_color="transparent")
        status.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 8))
        status.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(status, height=10,
                                           progress_color=COLORS["primary"])
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 16))
        self.progress_lbl = ctk.CTkLabel(status, text="Idle", font=font("small"),
                                         text_color=COLORS["text_dim"], width=240, anchor="e")
        self.progress_lbl.grid(row=0, column=1, sticky="e")

        # toolbar above list
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="e", padx=28, pady=(40, 0))
        GhostButton(toolbar, text="Select All", width=110, height=34,
                    command=lambda: self._select_all(True)).pack(side="left", padx=4)
        GhostButton(toolbar, text="Select None", width=110, height=34,
                    command=lambda: self._select_all(False)).pack(side="left", padx=4)
        self.count_stat = StatPill(toolbar, "Highlights", "0")
        self.count_stat.pack(side="left", padx=8)

        # list
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg_alt"], corner_radius=14,
            label_text="Detected Moments (sorted by score)", label_font=font("h2"),
            label_text_color=COLORS["text_dim"],
        )
        self.list_frame.grid(row=3, column=0, sticky="nsew", padx=28, pady=(8, 24))
        self.list_frame.grid_columnconfigure(0, weight=1)
        self._show_empty()

        self.controller.subscribe(EVT_HIGHLIGHTS, self._render)
        self.controller.subscribe(EVT_PROGRESS, self._on_progress)
        self.controller.subscribe(EVT_BUSY, self._on_busy)

    # ---- handlers -----------------------------------------------------------
    def _on_game_change(self, value: str) -> None:
        self.controller.project.game_type = value
        if not self.controller.project.style_preset or \
                self.controller.project.style_preset == "default":
            self.controller.project.style_preset = value

    def _on_fps_change(self, value: float) -> None:
        self.controller.settings.detection_sample_fps = round(float(value), 1)
        self.fps_value.configure(text=f"{value:.1f}")

    def _on_ocr_change(self) -> None:
        self.controller.settings.enable_ocr = self.ocr_var.get()

    def _on_progress(self, payload) -> None:
        stage, frac, msg = payload
        if stage == "detect":
            self.progress.set(frac)
            self.progress_lbl.configure(text=msg[:42])

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.detect_btn.configure(state="disabled")
            self.cancel_btn.grid()
        else:
            self.detect_btn.configure(state="normal")
            self.cancel_btn.grid_remove()
            self.progress_lbl.configure(text="Idle")

    def _select_all(self, value: bool) -> None:
        for h in self.controller.project.highlights:
            h.selected = value
        self._render(self.controller.project.highlights)

    # ---- rendering ----------------------------------------------------------
    def _show_empty(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.list_frame,
            text="No highlights yet.\n\nClick “Detect Highlights” to analyse your clips.",
            font=font("body"), text_color=COLORS["text_faint"], justify="center",
        ).grid(row=0, column=0, pady=80)

    def _render(self, highlights) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not highlights:
            self._show_empty()
        else:
            for i, h in enumerate(highlights):
                HighlightCard(self.list_frame, h).grid(
                    row=i, column=0, sticky="ew", pady=6, padx=6)
        selected = sum(1 for h in highlights if h.selected)
        self.count_stat.set_value(f"{selected}/{len(highlights)}")

    def on_show(self) -> None:
        self.game_var.set(self.controller.project.game_type)
        self._render(self.controller.project.highlights)

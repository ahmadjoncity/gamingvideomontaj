"""Configure the montage style and effects, then create it."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gamemontage.gui.controller import EVT_BUSY
from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.theme import COLOR_GRADES, COLORS, TRANSITIONS, font
from gamemontage.gui.widgets import Card, GhostButton, PrimaryButton, SectionTitle


class MontagePage(BasePage):
    title = "Montage"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        SectionTitle(
            self, "Create Epic Montage",
            "Dial in the style, music and effects — then let GameMontage cut it together.",
        ).grid(row=0, column=0, sticky="w", padx=28, pady=(24, 8))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        body.grid_columnconfigure((0, 1), weight=1, uniform="cols")

        if self.controller.project.montage_overrides is None:
            self.controller.project.montage_overrides = {}
        ov = self.controller.project.montage_overrides

        # ----- Style card -----
        style = Card(body)
        style.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        _card_title(style, "🎨  Style")

        self.grade_var = ctk.StringVar(value=ov.get("color_grade", "vibrant"))
        _labeled_menu(style, "Color Grade", COLOR_GRADES, self.grade_var,
                      lambda v: ov.__setitem__("color_grade", v))

        self.transition_var = ctk.StringVar(value=ov.get("transition", "zoom"))
        _labeled_menu(style, "Transition", TRANSITIONS, self.transition_var,
                      lambda v: ov.__setitem__("transition", v))

        self.intro_var = ctk.StringVar(value=ov.get("intro_text", ""))
        ctk.CTkLabel(style, text="Intro / Title text", font=font("small"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
        intro = ctk.CTkEntry(style, textvariable=self.intro_var, height=38,
                             placeholder_text="e.g. INSANE 1v5 CLUTCH",
                             fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        intro.pack(fill="x", padx=18, pady=(2, 16))
        intro.bind("<KeyRelease>",
                   lambda _e: ov.__setitem__("intro_text", self.intro_var.get()))

        # ----- Pacing card -----
        pacing = Card(body)
        pacing.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        _card_title(pacing, "⏱  Pacing & Effects")

        ctk.CTkLabel(pacing, text="Number of highlights", font=font("small"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
        row = ctk.CTkFrame(pacing, fg_color="transparent")
        row.pack(fill="x", padx=18)
        self.count_lbl = ctk.CTkLabel(row, text=str(ov.get("target_highlights", 12)),
                                      font=font("body_bold"), text_color=COLORS["primary"],
                                      width=30)
        self.count_lbl.pack(side="right")
        self.count_slider = ctk.CTkSlider(row, from_=6, to=15, number_of_steps=9,
                                          command=self._on_count, progress_color=COLORS["primary"],
                                          button_color=COLORS["primary"])
        self.count_slider.set(ov.get("target_highlights", 12))
        self.count_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.slowmo_var = ctk.BooleanVar(value=ov.get("slowmo_on_peak", True))
        self.zoom_var = ctk.BooleanVar(value=ov.get("punch_zoom", True))
        self.shake_var = ctk.BooleanVar(value=ov.get("shake", True))
        self.beat_var = ctk.BooleanVar(value=ov.get("beat_sync", True))
        self.caps_var = ctk.BooleanVar(value=self.controller.settings.enable_captions)

        _switch(pacing, "Slow-mo on peak moment", self.slowmo_var,
                lambda: ov.__setitem__("slowmo_on_peak", self.slowmo_var.get()))
        _switch(pacing, "Punch-in zoom", self.zoom_var,
                lambda: ov.__setitem__("punch_zoom", self.zoom_var.get()))
        _switch(pacing, "Camera shake", self.shake_var,
                lambda: ov.__setitem__("shake", self.shake_var.get()))
        _switch(pacing, "Beat-sync to music", self.beat_var,
                lambda: ov.__setitem__("beat_sync", self.beat_var.get()))
        _switch(pacing, "Animated captions (Whisper)", self.caps_var,
                self._on_captions)

        # ----- Music card -----
        music = Card(body)
        music.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        _card_title(music, "🎵  Music")
        m_row = ctk.CTkFrame(music, fg_color="transparent")
        m_row.pack(fill="x", padx=18, pady=(4, 16))
        m_row.grid_columnconfigure(0, weight=1)
        self.music_lbl = ctk.CTkLabel(
            m_row, text=self._music_label(), font=font("body"),
            text_color=COLORS["text_dim"], anchor="w")
        self.music_lbl.grid(row=0, column=0, sticky="ew")
        GhostButton(m_row, text="Choose Track", width=140,
                    command=self._pick_music).grid(row=0, column=1, padx=(8, 6))
        GhostButton(m_row, text="Clear", width=80,
                    command=self._clear_music).grid(row=0, column=2)

        # ----- Create button -----
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        footer.grid_columnconfigure(0, weight=1)
        self.hint = ctk.CTkLabel(footer, text="", font=font("small"),
                                 text_color=COLORS["text_dim"])
        self.hint.grid(row=0, column=0, sticky="w")
        self.create_btn = PrimaryButton(
            footer, text="🎬  Create Epic Montage", width=260, height=48,
            command=self._create)
        self.create_btn.grid(row=0, column=1, sticky="e")

        self.controller.subscribe(EVT_BUSY, self._on_busy)

    # ---- handlers -----------------------------------------------------------
    def _on_count(self, value: float) -> None:
        v = int(round(value))
        self.count_lbl.configure(text=str(v))
        self.controller.project.montage_overrides["target_highlights"] = v

    def _on_captions(self) -> None:
        self.controller.settings.enable_captions = self.caps_var.get()

    def _pick_music(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose background music",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg"), ("All files", "*.*")],
        )
        if path:
            self.controller.project.music_path = Path(path)
            self.music_lbl.configure(text=self._music_label())

    def _clear_music(self) -> None:
        self.controller.project.music_path = None
        self.music_lbl.configure(text=self._music_label())

    def _music_label(self) -> str:
        mp = self.controller.project.music_path
        return f"🎶  {Path(mp).name}" if mp else "No music selected (montage will keep game audio)."

    def _create(self) -> None:
        if not self.controller.project.highlights:
            self.controller.toast("Detect highlights first (Highlights tab).", "warning")
            return
        self.controller.build_and_export()

    def _on_busy(self, busy: bool) -> None:
        self.create_btn.configure(
            state="disabled" if busy else "normal",
            text="Working…" if busy else "🎬  Create Epic Montage",
        )

    def on_show(self) -> None:
        self.music_lbl.configure(text=self._music_label())
        self.caps_var.set(self.controller.settings.enable_captions)
        n = len(self.controller.project.selected_highlights())
        self.hint.configure(text=f"{n} highlight(s) selected — output goes to the Export tab settings.")


# --------------------------------------------------------------------------- #
# small layout helpers
# --------------------------------------------------------------------------- #
def _card_title(card, text: str) -> None:
    ctk.CTkLabel(card, text=text, font=font("h2"), text_color=COLORS["text"],
                 anchor="w").pack(anchor="w", padx=18, pady=(16, 4))


def _labeled_menu(parent, label, values, var, on_change) -> None:
    ctk.CTkLabel(parent, text=label, font=font("small"),
                 text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
    ctk.CTkOptionMenu(parent, values=values, variable=var, command=on_change,
                      fg_color=COLORS["bg_alt"], button_color=COLORS["secondary"],
                      button_hover_color=COLORS["secondary_hover"],
                      font=font("body")).pack(fill="x", padx=18, pady=(2, 6))


def _switch(parent, text, var, command) -> None:
    ctk.CTkSwitch(parent, text=text, variable=var, command=command,
                  font=font("body"), text_color=COLORS["text"],
                  progress_color=COLORS["primary"]).pack(anchor="w", padx=18, pady=6)

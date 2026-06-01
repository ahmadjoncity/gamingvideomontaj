"""Application settings: AI models, devices, paths, dependency status."""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from gamemontage.core.voiceover import VoiceoverEngine
from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.theme import COLORS, font
from gamemontage.gui.widgets import Card, GhostButton, PrimaryButton, SectionTitle


class SettingsPage(BasePage):
    title = "Settings"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        SectionTitle(
            self, "Settings",
            "Configure AI models, hardware acceleration and tool paths.",
        ).grid(row=0, column=0, sticky="w", padx=28, pady=(24, 8))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        body.grid_columnconfigure((0, 1), weight=1, uniform="s")

        s = self.controller.settings

        # ----- AI / captions -----
        ai = Card(body)
        ai.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        _title(ai, "🧠  AI / Captions")

        self.model_var = ctk.StringVar(value=s.whisper_model)
        _menu(ai, "Whisper model",
              ["tiny", "base", "small", "medium", "large-v3"], self.model_var)
        self.device_var = ctk.StringVar(value=s.whisper_device)
        _menu(ai, "Device", ["auto", "cpu", "cuda"], self.device_var)
        self.compute_var = ctk.StringVar(value=s.whisper_compute_type)
        _menu(ai, "Compute type", ["auto", "int8", "float16", "float32"], self.compute_var)

        self.captions_var = ctk.BooleanVar(value=s.enable_captions)
        _switch(ai, "Enable captions", self.captions_var)
        self.ocr_var = ctk.BooleanVar(value=s.enable_ocr)
        _switch(ai, "Enable kill-feed OCR", self.ocr_var)

        # ----- Performance -----
        perf = Card(body)
        perf.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        _title(perf, "⚙️  Performance")

        self.gpu_var = ctk.BooleanVar(value=s.use_gpu_encode)
        _switch(perf, "GPU video encoding", self.gpu_var)

        ctk.CTkLabel(perf, text="Encoder threads", font=font("small"),
                     text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
        trow = ctk.CTkFrame(perf, fg_color="transparent")
        trow.pack(fill="x", padx=18)
        self.threads_lbl = ctk.CTkLabel(trow, text=str(s.max_threads),
                                        font=font("body_bold"), text_color=COLORS["primary"],
                                        width=30)
        self.threads_lbl.pack(side="right")
        self.threads_slider = ctk.CTkSlider(trow, from_=1, to=16, number_of_steps=15,
                                            command=self._on_threads,
                                            progress_color=COLORS["primary"],
                                            button_color=COLORS["primary"])
        self.threads_slider.set(s.max_threads)
        self.threads_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.voice_var = ctk.StringVar(value=s.tts_voice)
        _menu(perf, "Voiceover voice (edge-tts)",
              VoiceoverEngine.list_common_voices(), self.voice_var)

        # ----- Paths -----
        paths = Card(body)
        paths.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        _title(paths, "📁  Paths")

        self.ffmpeg_var = ctk.StringVar(value=s.ffmpeg_path)
        _path_row(paths, "FFmpeg binary (blank = auto-detect)", self.ffmpeg_var, is_dir=False)
        self.tess_var = ctk.StringVar(value=s.tesseract_path)
        _path_row(paths, "Tesseract binary (blank = auto-detect)", self.tess_var, is_dir=False)
        self.output_var = ctk.StringVar(value=s.output_dir)
        _path_row(paths, "Default output folder", self.output_var, is_dir=True)
        self.music_var = ctk.StringVar(value=s.music_dir)
        _path_row(paths, "Local music library", self.music_var, is_dir=True)

        # ----- Dependency status -----
        deps = Card(body)
        deps.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        _title(deps, "🔌  Dependency status")
        self.deps_box = ctk.CTkLabel(deps, text=self._dep_status(), font=font("mono"),
                                     text_color=COLORS["text_dim"], justify="left", anchor="w")
        self.deps_box.pack(anchor="w", padx=18, pady=(0, 16))

        # ----- Save -----
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        footer.grid_columnconfigure(0, weight=1)
        self.saved_lbl = ctk.CTkLabel(footer, text="", font=font("small"),
                                      text_color=COLORS["success"])
        self.saved_lbl.grid(row=0, column=0, sticky="w")
        PrimaryButton(footer, text="💾  Save Settings", width=190,
                      command=self._save).grid(row=0, column=1, sticky="e")

    # ---- actions ------------------------------------------------------------
    def _on_threads(self, value: float) -> None:
        self.threads_lbl.configure(text=str(int(round(value))))

    def _save(self) -> None:
        s = self.controller.settings
        s.whisper_model = self.model_var.get()
        s.whisper_device = self.device_var.get()
        s.whisper_compute_type = self.compute_var.get()
        s.enable_captions = self.captions_var.get()
        s.enable_ocr = self.ocr_var.get()
        s.use_gpu_encode = self.gpu_var.get()
        s.max_threads = int(round(self.threads_slider.get()))
        s.tts_voice = self.voice_var.get()
        s.ffmpeg_path = self.ffmpeg_var.get().strip()
        s.tesseract_path = self.tess_var.get().strip()
        s.output_dir = self.output_var.get().strip() or s.output_dir
        s.music_dir = self.music_var.get().strip()
        self.controller.save_settings()
        self.saved_lbl.configure(text="Settings saved ✓")
        self.after(2500, lambda: self.saved_lbl.configure(text=""))

    def _dep_status(self) -> str:
        rows = []
        for label, module in [
            ("MoviePy", "moviepy"),
            ("OpenCV", "cv2"),
            ("librosa", "librosa"),
            ("faster-whisper", "faster_whisper"),
            ("pytesseract", "pytesseract"),
            ("edge-tts", "edge_tts"),
        ]:
            ok = _module_available(module)
            mark = "● available" if ok else "○ not installed"
            rows.append(f"  {label:<16} {mark}")
        from gamemontage.utils.ffmpeg_utils import find_ffmpeg
        ff = find_ffmpeg()
        rows.append(f"  {'FFmpeg':<16} {'● ' + ff if ff else '○ not found'}")
        return "\n".join(rows)

    def on_show(self) -> None:
        self.deps_box.configure(text=self._dep_status())


# --------------------------------------------------------------------------- #
def _title(card, text: str) -> None:
    ctk.CTkLabel(card, text=text, font=font("h2"), text_color=COLORS["text"],
                 anchor="w").pack(anchor="w", padx=18, pady=(16, 4))


def _menu(parent, label, values, var) -> None:
    ctk.CTkLabel(parent, text=label, font=font("small"),
                 text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
    ctk.CTkOptionMenu(parent, values=values, variable=var,
                      fg_color=COLORS["bg_alt"], button_color=COLORS["secondary"],
                      button_hover_color=COLORS["secondary_hover"],
                      font=font("body")).pack(fill="x", padx=18, pady=(2, 6))


def _switch(parent, text, var) -> None:
    ctk.CTkSwitch(parent, text=text, variable=var, font=font("body"),
                  text_color=COLORS["text"], progress_color=COLORS["primary"]
                  ).pack(anchor="w", padx=18, pady=6)


def _path_row(parent, label, var, is_dir: bool) -> None:
    ctk.CTkLabel(parent, text=label, font=font("small"),
                 text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=18, pady=(2, 4))
    row.grid_columnconfigure(0, weight=1)
    entry = ctk.CTkEntry(row, textvariable=var, height=36,
                         fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
    entry.grid(row=0, column=0, sticky="ew")

    def browse() -> None:
        if is_dir:
            chosen = filedialog.askdirectory(title=label)
        else:
            chosen = filedialog.askopenfilename(title=label)
        if chosen:
            var.set(chosen)

    GhostButton(row, text="Browse", width=90, command=browse).grid(
        row=0, column=1, padx=(8, 0))


def _module_available(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None

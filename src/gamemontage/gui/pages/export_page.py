"""Export settings + render trigger + result."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gamemontage.gui.controller import EVT_BUSY, EVT_FINISHED, EVT_PROGRESS
from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.theme import COLORS, font
from gamemontage.gui.widgets import (
    Card,
    DangerButton,
    GhostButton,
    PrimaryButton,
    SectionTitle,
)
from gamemontage.models import AspectRatio, Resolution

_ASPECTS = {
    "YouTube / Twitch (16:9)": AspectRatio.LANDSCAPE,
    "TikTok / Shorts / Reels (9:16)": AspectRatio.VERTICAL,
    "Square (1:1)": AspectRatio.SQUARE,
}
_RESOLUTIONS = {
    "720p": Resolution.P720,
    "1080p": Resolution.P1080,
    "1440p": Resolution.P1440,
    "4K": Resolution.P4K,
}


class ExportPage(BasePage):
    title = "Export"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        SectionTitle(
            self, "Export",
            "Choose the platform, quality and codec, then render your montage.",
        ).grid(row=0, column=0, sticky="w", padx=28, pady=(24, 8))

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        body.grid_columnconfigure((0, 1), weight=1, uniform="x")

        export = self.controller.project.export

        # ----- Format card -----
        fmt = Card(body)
        fmt.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        _title(fmt, "📐  Format")

        self.aspect_var = ctk.StringVar(value=_key_for(_ASPECTS, export.aspect))
        _menu(fmt, "Platform / Aspect Ratio", list(_ASPECTS), self.aspect_var,
              self._on_aspect)

        self.res_var = ctk.StringVar(value=_key_for(_RESOLUTIONS, export.resolution))
        _menu(fmt, "Resolution", list(_RESOLUTIONS), self.res_var, self._on_res)

        self.fps_var = ctk.StringVar(value=str(export.fps))
        _menu(fmt, "Frame rate", ["24", "30", "60"], self.fps_var, self._on_fps)

        # ----- Codec card -----
        codec = Card(body)
        codec.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        _title(codec, "🎞  Codec & Output")

        self.codec_var = ctk.StringVar(value="H.265 (HEVC)" if export.codec == "h265"
                                       else "H.264 (AVC)")
        _menu(codec, "Video codec", ["H.264 (AVC)", "H.265 (HEVC)"],
              self.codec_var, self._on_codec)

        self.gpu_var = ctk.BooleanVar(value=export.use_gpu)
        ctk.CTkSwitch(codec, text="GPU acceleration (NVENC/QSV if available)",
                      variable=self.gpu_var, command=self._on_gpu, font=font("body"),
                      progress_color=COLORS["primary"]).pack(anchor="w", padx=18, pady=8)

        self.thumb_var = ctk.BooleanVar(value=export.generate_thumbnail)
        ctk.CTkSwitch(codec, text="Auto-generate thumbnail", variable=self.thumb_var,
                      command=self._on_thumb, font=font("body"),
                      progress_color=COLORS["primary"]).pack(anchor="w", padx=18, pady=8)

        # output folder
        out_row = ctk.CTkFrame(codec, fg_color="transparent")
        out_row.pack(fill="x", padx=18, pady=(8, 16))
        out_row.grid_columnconfigure(0, weight=1)
        self.out_lbl = ctk.CTkLabel(out_row, text=self._out_label(), font=font("small"),
                                    text_color=COLORS["text_dim"], anchor="w")
        self.out_lbl.grid(row=0, column=0, sticky="ew")
        GhostButton(out_row, text="Change", width=90,
                    command=self._pick_output).grid(row=0, column=1, padx=(8, 0))

        # ----- Project name -----
        name_card = Card(body)
        name_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        _title(name_card, "📝  Output name")
        self.name_var = ctk.StringVar(value=self.controller.project.name)
        entry = ctk.CTkEntry(name_card, textvariable=self.name_var, height=38,
                             fg_color=COLORS["bg_alt"], border_color=COLORS["border"])
        entry.pack(fill="x", padx=18, pady=(2, 16))
        entry.bind("<KeyRelease>",
                   lambda _e: setattr(self.controller.project, "name", self.name_var.get()))

        # ----- progress + result -----
        prog_card = Card(body)
        prog_card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=8)
        _title(prog_card, "🚀  Render")
        self.progress = ctk.CTkProgressBar(prog_card, height=14,
                                           progress_color=COLORS["success"])
        self.progress.set(0)
        self.progress.pack(fill="x", padx=18, pady=(4, 4))
        self.stage_lbl = ctk.CTkLabel(prog_card, text="Ready.", font=font("small"),
                                      text_color=COLORS["text_dim"], anchor="w")
        self.stage_lbl.pack(anchor="w", padx=18, pady=(0, 8))

        self.result_lbl = ctk.CTkLabel(prog_card, text="", font=font("body"),
                                       text_color=COLORS["success"], anchor="w",
                                       justify="left")
        self.result_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        self.open_btn = GhostButton(prog_card, text="📂  Open output folder",
                                    width=200, command=self._open_output)
        self.open_btn.pack(anchor="w", padx=18, pady=(0, 16))
        self.open_btn.pack_forget()

        # ----- footer buttons -----
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 22))
        footer.grid_columnconfigure(0, weight=1)
        self.export_btn = PrimaryButton(footer, text="⬇  Export Montage",
                                        width=220, height=48, command=self._export)
        self.export_btn.grid(row=0, column=1, sticky="e")
        self.cancel_btn = DangerButton(footer, text="✕ Cancel", width=120, height=48,
                                       command=self.controller.cancel)
        self.cancel_btn.grid(row=0, column=2, sticky="e", padx=(10, 0))
        self.cancel_btn.grid_remove()

        self.controller.subscribe(EVT_PROGRESS, self._on_progress)
        self.controller.subscribe(EVT_BUSY, self._on_busy)
        self.controller.subscribe(EVT_FINISHED, self._on_finished)

    # ---- handlers -----------------------------------------------------------
    def _on_aspect(self, key: str) -> None:
        self.controller.project.export.aspect = _ASPECTS[key]

    def _on_res(self, key: str) -> None:
        self.controller.project.export.resolution = _RESOLUTIONS[key]

    def _on_fps(self, key: str) -> None:
        self.controller.project.export.fps = int(key)

    def _on_codec(self, key: str) -> None:
        self.controller.project.export.codec = "h265" if "265" in key else "h264"

    def _on_gpu(self) -> None:
        self.controller.project.export.use_gpu = self.gpu_var.get()
        self.controller.settings.use_gpu_encode = self.gpu_var.get()

    def _on_thumb(self) -> None:
        self.controller.project.export.generate_thumbnail = self.thumb_var.get()

    def _pick_output(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.controller.project.output_dir = Path(folder)
            self.out_lbl.configure(text=self._out_label())

    def _out_label(self) -> str:
        out = self.controller.project.output_dir or self.controller.settings.resolved_output_dir()
        return f"Output folder:  {out}"

    def _export(self) -> None:
        if not self.controller.project.highlights:
            self.controller.toast("Detect highlights first (Highlights tab).", "warning")
            return
        self.result_lbl.configure(text="")
        self.open_btn.pack_forget()
        self.controller.build_and_export()

    def _on_progress(self, payload) -> None:
        stage, frac, msg = payload
        if stage in ("build", "export", "captions", "thumbnail", "done"):
            self.progress.set(frac)
            self.stage_lbl.configure(text=f"[{stage}] {msg}")

    def _on_busy(self, busy: bool) -> None:
        self.export_btn.configure(state="disabled" if busy else "normal")
        if busy:
            self.cancel_btn.grid()
        else:
            self.cancel_btn.grid_remove()

    def _on_finished(self, result) -> None:
        if result is None:
            return
        if result.error:
            self.result_lbl.configure(text=f"❌  {result.error}", text_color=COLORS["danger"])
            return
        if result.cancelled:
            self.result_lbl.configure(text="⚠  Cancelled.", text_color=COLORS["warning"])
            return
        lines = [f"✅  Montage: {result.montage_path}"]
        if result.thumbnail_path:
            lines.append(f"🖼   Thumbnail: {result.thumbnail_path}")
        self.result_lbl.configure(text="\n".join(lines), text_color=COLORS["success"])
        self.open_btn.pack(anchor="w", padx=18, pady=(0, 16))

    def _open_output(self) -> None:
        out = self.controller.project.output_dir or self.controller.settings.resolved_output_dir()
        _open_in_file_manager(Path(out))

    def on_show(self) -> None:
        self.out_lbl.configure(text=self._out_label())
        self.name_var.set(self.controller.project.name)


# --------------------------------------------------------------------------- #
def _title(card, text: str) -> None:
    ctk.CTkLabel(card, text=text, font=font("h2"), text_color=COLORS["text"],
                 anchor="w").pack(anchor="w", padx=18, pady=(16, 4))


def _menu(parent, label, values, var, on_change) -> None:
    ctk.CTkLabel(parent, text=label, font=font("small"),
                 text_color=COLORS["text_dim"]).pack(anchor="w", padx=18, pady=(8, 0))
    ctk.CTkOptionMenu(parent, values=values, variable=var, command=on_change,
                      fg_color=COLORS["bg_alt"], button_color=COLORS["secondary"],
                      button_hover_color=COLORS["secondary_hover"],
                      font=font("body")).pack(fill="x", padx=18, pady=(2, 6))


def _key_for(mapping: dict, value) -> str:
    for k, v in mapping.items():
        if v == value:
            return k
    return next(iter(mapping))


def _open_in_file_manager(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:  # noqa: BLE001
        pass

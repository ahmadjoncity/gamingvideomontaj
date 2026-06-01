"""The main application window: sidebar navigation + stacked pages + status bar.

This module wires the :class:`AppController` to the CustomTkinter UI. All
cross-thread updates arrive through the controller's event queue, which is
drained on the Tk main loop via :meth:`App._pump`.
"""

from __future__ import annotations

import customtkinter as ctk

from gamemontage import APP_NAME, __version__
from gamemontage.gui.controller import (
    EVT_BUSY,
    EVT_LOG,
    EVT_TOAST,
    AppController,
)
from gamemontage.gui.pages import (
    ExportPage,
    HighlightsPage,
    ImportPage,
    MontagePage,
    SettingsPage,
)
from gamemontage.gui.theme import COLORS, font
from gamemontage.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)

_NAV = [
    ("Import", "📥", ImportPage),
    ("Highlights", "⚡", HighlightsPage),
    ("Montage", "🎬", MontagePage),
    ("Export", "📤", ExportPage),
    ("Settings", "⚙️", SettingsPage),
]


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.controller = AppController()

        ctk.set_appearance_mode(self.controller.settings.appearance_mode)
        ctk.set_default_color_theme(self.controller.settings.color_theme)

        self.title(f"{APP_NAME}  ·  v{__version__}")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self._build_statusbar()

        self.controller.subscribe(EVT_TOAST, self._show_toast)
        self.controller.subscribe(EVT_LOG, self._append_log)
        self.controller.subscribe(EVT_BUSY, self._on_busy)

        self._show_page("Import")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._pump)

    # ---- layout -------------------------------------------------------------
    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=COLORS["bg_alt"])
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(len(_NAV) + 1, weight=1)

        brand = ctk.CTkFrame(side, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 18))
        ctk.CTkLabel(brand, text="🎮 GameMontage", font=("Segoe UI", 19, "bold"),
                     text_color=COLORS["primary"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="AI · AutoGamerEdit", font=font("small"),
                     text_color=COLORS["text_faint"]).pack(anchor="w")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for i, (name, icon, _page) in enumerate(_NAV, start=1):
            btn = ctk.CTkButton(
                side, text=f"  {icon}   {name}", anchor="w", height=46,
                corner_radius=10, font=font("nav"),
                fg_color="transparent", hover_color=COLORS["surface_alt"],
                text_color=COLORS["text_dim"],
                command=lambda n=name: self._show_page(n),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            self.nav_buttons[name] = btn

        # busy indicator at the bottom of the sidebar
        self.busy_frame = ctk.CTkFrame(side, fg_color="transparent")
        self.busy_frame.grid(row=len(_NAV) + 2, column=0, sticky="ew", padx=14, pady=14)
        self.busy_bar = ctk.CTkProgressBar(self.busy_frame, mode="indeterminate",
                                           height=6, progress_color=COLORS["secondary"])
        self.busy_lbl = ctk.CTkLabel(self.busy_frame, text="Idle", font=font("small"),
                                     text_color=COLORS["text_faint"])
        self.busy_lbl.pack(anchor="w")

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages: dict[str, object] = {}
        for name, _icon, page_cls in _NAV:
            page = page_cls(self.content, self.controller)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=COLORS["bg_alt"])
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(bar, text="Ready", font=font("small"),
                                       text_color=COLORS["text_dim"], anchor="w")
        self.status_lbl.grid(row=0, column=0, sticky="w", padx=14, pady=4)

        self.log_toggle = ctk.CTkButton(
            bar, text="Show console", width=120, height=22, corner_radius=6,
            font=font("small"), fg_color=COLORS["surface_alt"],
            hover_color=COLORS["border"], text_color=COLORS["text_dim"],
            command=self._toggle_log)
        self.log_toggle.grid(row=0, column=1, sticky="e", padx=10, pady=4)

        # collapsible log console
        self.log_box = ctk.CTkTextbox(self, height=150, font=font("mono"),
                                      fg_color="#0A0B0E", text_color=COLORS["text_dim"],
                                      corner_radius=0)
        self._log_visible = False

        # toast overlay (created lazily)
        self._toast: ctk.CTkLabel | None = None

    # ---- navigation ---------------------------------------------------------
    def _show_page(self, name: str) -> None:
        page = self.pages.get(name)
        if page is None:
            return
        page.tkraise()
        if hasattr(page, "on_show"):
            page.on_show()
        for n, btn in self.nav_buttons.items():
            active = n == name
            btn.configure(
                fg_color=COLORS["surface"] if active else "transparent",
                text_color=COLORS["primary"] if active else COLORS["text_dim"],
            )

    # ---- event handlers -----------------------------------------------------
    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.busy_bar.pack(fill="x", pady=(4, 0))
            self.busy_bar.start()
            self.busy_lbl.configure(text="Working…", text_color=COLORS["secondary"])
            self.status_lbl.configure(text="Working…")
        else:
            self.busy_bar.stop()
            self.busy_bar.pack_forget()
            self.busy_lbl.configure(text="Idle", text_color=COLORS["text_faint"])
            self.status_lbl.configure(text="Ready")

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.status_lbl.configure(text=message[:90])

    def _toggle_log(self) -> None:
        if self._log_visible:
            self.log_box.grid_forget()
            self.log_toggle.configure(text="Show console")
        else:
            self.log_box.grid(row=2, column=0, columnspan=2, sticky="ew")
            self.log_toggle.configure(text="Hide console")
        self._log_visible = not self._log_visible

    def _show_toast(self, payload) -> None:
        level, message = payload
        colors = {
            "success": COLORS["success"], "warning": COLORS["warning"],
            "error": COLORS["danger"], "info": COLORS["primary"],
        }
        if self._toast is not None:
            self._toast.destroy()
        self._toast = ctk.CTkLabel(
            self, text=f"  {message}  ", font=font("body_bold"),
            fg_color=COLORS["surface"], text_color=colors.get(level, COLORS["primary"]),
            corner_radius=10, height=44,
        )
        self._toast.place(relx=0.5, rely=0.94, anchor="s")
        self.after(3200, self._hide_toast)

    def _hide_toast(self) -> None:
        if self._toast is not None:
            self._toast.destroy()
            self._toast = None

    # ---- main loop integration ----------------------------------------------
    def _pump(self) -> None:
        self.controller.pump()
        self.after(80, self._pump)

    def _on_close(self) -> None:
        try:
            self.controller.cancel()
            self.controller.save_settings()
        finally:
            self.destroy()


def run_app() -> int:
    configure_logging("INFO")
    logger.info("Starting %s v%s", APP_NAME, __version__)
    try:
        app = App()
        app.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("Fatal GUI error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_app())

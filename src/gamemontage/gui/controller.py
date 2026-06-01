"""Application controller: owns state, runs work off the UI thread, emits events.

The GUI is intentionally thin. All mutating operations go through the
:class:`AppController`, which:

* holds the current :class:`Project` and :class:`Settings`,
* runs long tasks (import, detection, export) on worker threads,
* posts ``(event, payload)`` messages onto a thread-safe queue.

The Tk app drains that queue on its main loop (via ``after``) and notifies
subscribers, so all widget updates happen on the UI thread -- the golden rule
for Tkinter.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gamemontage.app_config import Settings, load_preset
from gamemontage.core.pipeline import MontagePipeline, PipelineCallbacks
from gamemontage.core.video_manager import VideoManager
from gamemontage.models import Project
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

# Event names emitted to the UI.
EVT_CLIPS = "clips_changed"
EVT_HIGHLIGHTS = "highlights_changed"
EVT_PROGRESS = "progress"          # payload: (stage, frac, msg)
EVT_LOG = "log"                    # payload: str
EVT_BUSY = "busy_changed"          # payload: bool
EVT_FINISHED = "finished"          # payload: PipelineResult | None
EVT_TOAST = "toast"                # payload: (level, msg)


class AppController:
    def __init__(self) -> None:
        self.settings = Settings.load()
        self.project = Project()
        self.project.output_dir = self.settings.resolved_output_dir()
        self.video_manager = VideoManager()

        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._listeners: dict[str, list[Callable[[Any], None]]] = {}
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()
        self._busy = False

    # ---- pub/sub ------------------------------------------------------------
    def subscribe(self, event: str, callback: Callable[[Any], None]) -> None:
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event: str, payload: Any = None) -> None:
        """Thread-safe: queue an event for the UI loop to dispatch."""
        self._events.put((event, payload))

    def pump(self) -> None:
        """Called on the UI thread to dispatch queued events to listeners."""
        while True:
            try:
                event, payload = self._events.get_nowait()
            except queue.Empty:
                break
            for cb in self._listeners.get(event, []):
                try:
                    cb(payload)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Listener for %s failed: %s", event, exc)

    # ---- state --------------------------------------------------------------
    @property
    def busy(self) -> bool:
        return self._busy

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        self.emit(EVT_BUSY, value)

    def toast(self, message: str, level: str = "info") -> None:
        self.emit(EVT_TOAST, (level, message))

    # ---- import (threaded) --------------------------------------------------
    def add_inputs(self, inputs: list[str | Path]) -> None:
        if self.busy:
            self.toast("Please wait for the current task to finish.", "warning")
            return

        def work() -> None:
            self._set_busy(True)
            self.emit(EVT_LOG, f"Importing {len(inputs)} item(s)...")
            try:
                paths = self.video_manager.collect_paths(inputs)
                if not paths:
                    self.toast("No supported video files found.", "warning")
                    return
                for i, p in enumerate(paths):
                    if self._cancel.is_set():
                        break
                    try:
                        clip = self.video_manager.import_clip(p)
                        self.project.add_clip(clip)
                        self.emit(EVT_LOG, f"  + {clip.name} ({clip.duration_label})")
                        self.emit(EVT_PROGRESS, ("import", (i + 1) / len(paths), clip.name))
                    except Exception as exc:  # noqa: BLE001
                        self.emit(EVT_LOG, f"  ! Skipped {p.name}: {exc}")
                self.emit(EVT_CLIPS, self.project.clips)
                self.toast(f"Imported {len(self.project.clips)} clip(s).", "success")
            finally:
                self.emit(EVT_PROGRESS, ("import", 1.0, "Done"))
                self._set_busy(False)

        self._run(work)

    def remove_clip(self, clip_id: str) -> None:
        self.project.clips = [c for c in self.project.clips if c.id != clip_id]
        self.project.highlights = [h for h in self.project.highlights if h.clip_id != clip_id]
        self.emit(EVT_CLIPS, self.project.clips)
        self.emit(EVT_HIGHLIGHTS, self.project.highlights)

    def clear_clips(self) -> None:
        self.project.clips = []
        self.project.highlights = []
        self.emit(EVT_CLIPS, self.project.clips)
        self.emit(EVT_HIGHLIGHTS, self.project.highlights)

    # ---- detection (threaded) ----------------------------------------------
    def detect_highlights(self) -> None:
        if self.busy:
            self.toast("A task is already running.", "warning")
            return
        if not self.project.enabled_clips():
            self.toast("Import some clips first.", "warning")
            return

        def work() -> None:
            self._set_busy(True)
            self._cancel.clear()
            try:
                pipeline = MontagePipeline(self.settings)
                cb = self._callbacks()
                highlights = pipeline.detect_highlights(self.project, cb)
                self.emit(EVT_HIGHLIGHTS, highlights)
                if self._cancel.is_set():
                    self.toast("Detection cancelled.", "warning")
                else:
                    self.toast(f"Found {len(highlights)} highlights.", "success")
            finally:
                self._set_busy(False)

        self._run(work)

    # ---- build + export (threaded) -----------------------------------------
    def build_and_export(self) -> None:
        if self.busy:
            self.toast("A task is already running.", "warning")
            return
        if not self.project.highlights:
            self.toast("Detect highlights before building a montage.", "warning")
            return

        def work() -> None:
            self._set_busy(True)
            self._cancel.clear()
            result = None
            try:
                pipeline = MontagePipeline(self.settings)
                cb = self._callbacks()
                result = pipeline.build_and_export(self.project, cb)
                if result.error:
                    self.toast(f"Export failed: {result.error}", "error")
                elif result.cancelled:
                    self.toast("Export cancelled.", "warning")
                else:
                    self.toast("Montage exported successfully!", "success")
            finally:
                self.emit(EVT_FINISHED, result)
                self._set_busy(False)

        self._run(work)

    # ---- cancel -------------------------------------------------------------
    def cancel(self) -> None:
        if self.busy:
            self._cancel.set()
            self.emit(EVT_LOG, "Cancellation requested...")

    # ---- presets / settings -------------------------------------------------
    def preset_for_ui(self, name: str) -> dict:
        return load_preset(name)

    def save_settings(self) -> None:
        self.settings.save()

    # ---- helpers ------------------------------------------------------------
    def _callbacks(self) -> PipelineCallbacks:
        return PipelineCallbacks(
            on_progress=lambda stage, frac, msg: self.emit(EVT_PROGRESS, (stage, frac, msg)),
            on_log=lambda msg: self.emit(EVT_LOG, msg),
            cancel_check=self._cancel.is_set,
        )

    def _run(self, work: Callable[[], None]) -> None:
        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

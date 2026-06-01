"""Assemble selected highlights into a finished montage clip.

Responsibilities:

* select the top N highlights and order them to "build to the peak",
* cut sub-clips from the source videos,
* reframe each sub-clip to the target aspect ratio,
* apply per-clip effects (zoom-in transition, punch zoom, shake, slow-mo),
* stamp text overlays ("ACE!", kill labels, intro text),
* add a beat-synced music bed and overall color grade,
* (optionally) burn animated captions and a voiceover.

The result is an in-memory MoviePy clip; rendering to disk is the exporter's
job. Everything that can fail per-clip degrades to the untouched sub-clip so a
single bad source never aborts the whole montage.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gamemontage.core import color_grading, effects
from gamemontage.core._moviepy import mpy
from gamemontage.core.audio_analyzer import AudioAnalyzer
from gamemontage.core.text_render import render_text_rgba
from gamemontage.models import AspectRatio, Highlight, HighlightKind
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)

ProgressFn = Callable[[float, str], None]


@dataclass
class MontageOptions:
    """Resolved montage options (usually built from a preset + GUI choices)."""

    aspect: AspectRatio = AspectRatio.LANDSCAPE
    frame_size: tuple[int, int] = (1920, 1080)
    fps: int = 30
    target_highlights: int = 12
    min_highlights: int = 6
    max_highlights: int = 15
    slowmo_on_peak: bool = True
    punch_zoom: bool = True
    shake: bool = True
    transition: str = "zoom"          # zoom|glitch|fade|cut
    build_to_peak: bool = True
    color_grade: str = "vibrant"
    music_path: Path | None = None
    music_volume: float = 0.8
    beat_sync: bool = True
    overlays: dict[str, str] | None = None
    style: dict | None = None
    intro_text: str = ""

    @classmethod
    def from_preset(cls, preset: dict, aspect: AspectRatio,
                    frame_size: tuple[int, int], fps: int,
                    music_path: Path | None) -> MontageOptions:
        m = preset.get("montage", {})
        s = preset.get("style", {})
        return cls(
            aspect=aspect,
            frame_size=frame_size,
            fps=fps,
            target_highlights=m.get("target_highlights", 12),
            min_highlights=m.get("min_highlights", 6),
            max_highlights=m.get("max_highlights", 15),
            slowmo_on_peak=m.get("slowmo_on_peak", True),
            punch_zoom=m.get("punch_zoom", True),
            shake=m.get("shake", True),
            transition=m.get("transition", "zoom"),
            build_to_peak=m.get("build_to_peak", True),
            color_grade=s.get("color_grade", "vibrant"),
            music_path=music_path,
            overlays=preset.get("overlays", {}),
            style=s,
            intro_text=s.get("intro_text", ""),
        )


class MontageCreator:
    """Builds the montage video clip from highlights."""

    def __init__(self, options: MontageOptions) -> None:
        self.opt = options
        self._audio = AudioAnalyzer()

    # ---- selection ----------------------------------------------------------
    def select_highlights(self, highlights: list[Highlight]) -> list[Highlight]:
        chosen = [h for h in highlights if h.selected] or list(highlights)
        chosen.sort(key=lambda h: h.score, reverse=True)
        n = max(self.opt.min_highlights,
                min(self.opt.target_highlights, self.opt.max_highlights))
        chosen = chosen[:n]
        return self._order(chosen)

    def _order(self, highlights: list[Highlight]) -> list[Highlight]:
        """Order so intensity ramps up, with the single biggest moment last."""
        if not self.opt.build_to_peak or len(highlights) < 3:
            return highlights
        ranked = sorted(highlights, key=lambda h: h.score)
        peak = ranked.pop()                 # biggest moment
        # alternate low/high to create a rising rhythm, peak goes last
        ordered: list[Highlight] = []
        lo, hi = 0, len(ranked) - 1
        take_low = True
        while lo <= hi:
            if take_low:
                ordered.append(ranked[lo])
                lo += 1
            else:
                ordered.append(ranked[hi])
                hi -= 1
            take_low = not take_low
        ordered.sort(key=lambda h: h.score)  # gentle rising
        ordered.append(peak)
        return ordered

    # ---- build --------------------------------------------------------------
    def build(self, highlights: list[Highlight],
              progress: ProgressFn | None = None,
              should_cancel: Callable[[], bool] | None = None):
        editor = mpy()
        selected = self.select_highlights(highlights)
        if not selected:
            raise ValueError("No highlights to build a montage from.")

        logger.info("Building montage from %d highlights", len(selected))

        beat_durations = self._beat_durations(len(selected))
        source_cache: dict[str, object] = {}
        segments = []

        total = len(selected)
        for i, h in enumerate(selected):
            if should_cancel and should_cancel():
                logger.info("Montage build cancelled.")
                break
            if progress:
                progress(0.1 + 0.6 * (i / total), f"Editing clip {i + 1}/{total}")

            seg = self._build_segment(
                editor, h, i, total, beat_durations[i] if beat_durations else None,
                source_cache,
            )
            if seg is not None:
                segments.append(seg)

        if not segments:
            raise RuntimeError("Failed to build any montage segments.")

        if progress:
            progress(0.75, "Stitching timeline")
        montage = self._concatenate(editor, segments)

        # overall color grade
        montage = color_grading.apply_grade(montage, self.opt.color_grade)

        # intro overlay
        if self.opt.intro_text:
            montage = self._add_intro(editor, montage)

        # music bed
        if progress:
            progress(0.85, "Adding music")
        montage = self._add_music(editor, montage)

        # cleanup readers we no longer need is deferred to exporter (it renders)
        montage._gm_sources = list(source_cache.values())  # type: ignore[attr-defined]
        if progress:
            progress(0.95, "Montage assembled")
        return montage

    # ---- per-segment --------------------------------------------------------
    def _build_segment(self, editor, h: Highlight, index: int, total: int,
                       beat_dur: float | None, cache: dict):
        try:
            source = cache.get(h.clip_id)
            if source is None:
                source = editor.VideoFileClip(str(h.clip_path))
                cache[h.clip_id] = source

            start = max(0.0, h.start)
            end = min(source.duration, h.end) if source.duration else h.end
            if end - start < 0.3:
                end = min(source.duration or end, start + 1.0)

            clip = source.subclip(start, end)

            is_peak = index == total - 1
            # snap duration to a beat interval when beat-syncing
            if beat_dur and beat_dur > 0.3:
                clip = self._fit_duration(clip, beat_dur, slow=is_peak and self.opt.slowmo_on_peak)

            # reframe to target aspect
            clip = self._reframe(clip)

            # effects
            if self.opt.slowmo_on_peak and is_peak:
                clip = effects.slow_motion(clip, 0.55)
            if self.opt.punch_zoom and (is_peak or h.score > 0.7):
                clip = effects.punch_zoom(clip, 1.18)
            if self.opt.shake and h.kind in (HighlightKind.EPIC, HighlightKind.ACTION):
                clip = effects.camera_shake(clip, intensity=6)

            # entry transition
            if self.opt.transition == "zoom":
                clip = effects.zoom_transition_in(clip, 0.25, 1.6)
            elif self.opt.transition == "glitch":
                clip = effects.glitch(clip, 8)

            # text overlay
            clip = self._add_overlay(editor, clip, h, index)

            clip = clip.set_fps(self.opt.fps)
            return clip
        except Exception as exc:  # noqa: BLE001
            logger.warning("Segment %d failed (%s); skipping.", index, exc)
            return None

    def _fit_duration(self, clip, target: float, slow: bool):
        """Trim or stretch a clip toward ``target`` seconds."""
        d = clip.duration or target
        if d > target:
            # keep the most interesting middle
            mid = d / 2
            half = target / 2
            return clip.subclip(max(0, mid - half), min(d, mid + half))
        return clip

    def _reframe(self, clip):
        """Scale + crop the clip to fill the target frame size/aspect."""
        try:
            tw, th = self.opt.frame_size
            cw, ch = clip.size
            scale = max(tw / cw, th / ch)
            resized = clip.resize(scale)
            return resized.crop(
                x_center=resized.w / 2, y_center=resized.h / 2, width=tw, height=th
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Reframe failed: %s", exc)
            return clip

    def _add_overlay(self, editor, clip, h: Highlight, index: int):
        text = self._overlay_text(h, index)
        if not text:
            return clip
        try:
            tw, th = self.opt.frame_size
            style = self.opt.style or {}
            rgba = render_text_rgba(
                text,
                font_size=max(40, int(th * 0.085)),
                color=style.get("overlay_color", "#00E5FF"),
                outline_color=style.get("caption_outline", "#000000"),
                outline_width=max(4, int(th * 0.006)),
                shadow=True,
                max_width=int(tw * 0.9),
            )
            dur = min(1.6, clip.duration)
            overlay = (
                editor.ImageClip(rgba)
                .set_duration(dur)
                .set_position(("center", int(th * 0.12)))
                .crossfadein(0.15)
            )
            overlay = overlay.resize(lambda t: 1.0 + 0.15 * max(0.0, 1 - t / 0.2))
            return editor.CompositeVideoClip([clip, overlay], size=self.opt.frame_size)\
                .set_duration(clip.duration)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Overlay failed: %s", exc)
            return clip

    def _overlay_text(self, h: Highlight, index: int) -> str:
        if h.label:
            return h.label
        overlays = self.opt.overlays or {}
        return overlays.get(h.kind.value, "")

    # ---- assembly -----------------------------------------------------------
    def _concatenate(self, editor, segments):
        transition = self.opt.transition
        if transition == "fade":
            padded = [segments[0]]
            for seg in segments[1:]:
                padded.append(seg.crossfadein(0.3))
            return editor.concatenate_videoclips(
                padded, padding=-0.3, method="compose"
            ).set_fps(self.opt.fps)
        return editor.concatenate_videoclips(segments, method="compose").set_fps(self.opt.fps)

    def _add_intro(self, editor, montage):
        try:
            tw, th = self.opt.frame_size
            style = self.opt.style or {}
            rgba = render_text_rgba(
                self.opt.intro_text, font_size=max(60, int(th * 0.12)),
                color=style.get("caption_highlight", "#FFE14D"),
                outline_color="#000000", outline_width=8, shadow=True,
                max_width=int(tw * 0.9),
            )
            intro = (
                editor.ImageClip(rgba).set_duration(1.6)
                .set_position("center").crossfadein(0.3).crossfadeout(0.3)
            )
            return editor.CompositeVideoClip([montage, intro], size=self.opt.frame_size)\
                .set_duration(montage.duration)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Intro overlay failed: %s", exc)
            return montage

    # ---- music --------------------------------------------------------------
    def _beat_durations(self, n_clips: int) -> list[float] | None:
        if not (self.opt.beat_sync and self.opt.music_path
                and Path(self.opt.music_path).exists()):
            return None
        analysis = self._audio.analyze_audio(Path(self.opt.music_path))
        beats = analysis.beat_times
        if len(beats) < 4:
            return None
        # use every other beat as a cut grid for punchier pacing
        grid = beats[::2]
        durations = [max(0.6, grid[i + 1] - grid[i]) for i in range(len(grid) - 1)]
        if not durations:
            return None
        # repeat/cycle to cover all clips
        out = [durations[i % len(durations)] for i in range(n_clips)]
        logger.info("Beat-sync grid: %d intervals, tempo %.0f BPM",
                    len(durations), analysis.tempo)
        return out

    def _add_music(self, editor, montage):
        path = self.opt.music_path
        if not (path and Path(path).exists()):
            return montage
        try:
            music = editor.AudioFileClip(str(path)).volumex(self.opt.music_volume)
            if music.duration > montage.duration:
                music = music.subclip(0, montage.duration)
            else:
                # loop music to cover full montage
                loops = int(montage.duration / music.duration) + 1
                music = editor.concatenate_audioclips([music] * loops)\
                    .subclip(0, montage.duration)

            import moviepy.audio.fx.all as afx
            music = music.fx(afx.audio_fadeout, 1.0)

            if montage.audio is not None:
                # keep some game audio under the music
                game = montage.audio.volumex(0.55)
                mixed = editor.CompositeAudioClip([game, music])
                return montage.set_audio(mixed)
            return montage.set_audio(music)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Music mix failed: %s", exc)
            return montage

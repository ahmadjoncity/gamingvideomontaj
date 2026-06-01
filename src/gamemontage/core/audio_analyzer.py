"""Audio analysis: loudness spikes (for highlights) and beat tracking (for sync).

Everything degrades gracefully:

* If ``librosa`` is missing we return empty results and the detector simply
  weights audio at zero.
* Audio is extracted to a temporary WAV via ffmpeg when needed.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from gamemontage.utils.ffmpeg_utils import find_ffmpeg
from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AudioAnalysis:
    """Result of analysing a clip's audio track."""

    duration: float = 0.0
    sr: int = 0
    # loudness envelope sampled at ``env_fps`` Hz, normalised 0..1
    loudness: np.ndarray = field(default_factory=lambda: np.zeros(0))
    env_fps: float = 0.0
    # times (seconds) of detected loudness spikes
    spike_times: list[float] = field(default_factory=list)
    # tempo + beat times for beat-syncing cuts
    tempo: float = 0.0
    beat_times: list[float] = field(default_factory=list)

    def loudness_at(self, t: float) -> float:
        """Sample the normalised loudness envelope at time ``t`` (seconds)."""
        if self.loudness.size == 0 or self.env_fps <= 0:
            return 0.0
        idx = int(t * self.env_fps)
        idx = max(0, min(idx, self.loudness.size - 1))
        return float(self.loudness[idx])


class AudioAnalyzer:
    """Extracts and analyses audio from video/audio files."""

    def __init__(self, target_sr: int = 22050) -> None:
        self.target_sr = target_sr

    # ---- public API ---------------------------------------------------------
    def analyze_video(self, video_path: Path) -> AudioAnalysis:
        """Extract the audio track from a video and analyse it."""
        wav = self._extract_audio(video_path)
        if wav is None:
            return AudioAnalysis()
        try:
            return self.analyze_audio(wav)
        finally:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass

    def analyze_audio(self, audio_path: Path) -> AudioAnalysis:
        try:
            import librosa
        except ImportError:
            logger.warning("librosa not installed; audio analysis disabled.")
            return AudioAnalysis()

        try:
            y, sr = librosa.load(str(audio_path), sr=self.target_sr, mono=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load audio %s: %s", audio_path, exc)
            return AudioAnalysis()

        if y.size == 0:
            return AudioAnalysis(sr=sr)

        duration = librosa.get_duration(y=y, sr=sr)
        hop = 512
        env_fps = sr / hop

        # Short-time RMS energy -> normalised loudness envelope.
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        loud = self._normalise(rms)

        spikes = self._detect_spikes(loud, env_fps)

        tempo, beats = 0.0, []
        try:
            tempo_arr, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
            tempo = float(np.atleast_1d(tempo_arr)[0])
            beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop).tolist()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Beat tracking failed: %s", exc)

        logger.info(
            "Audio: %.1fs, %d spikes, tempo %.0f BPM, %d beats",
            duration, len(spikes), tempo, len(beats),
        )
        return AudioAnalysis(
            duration=duration, sr=sr, loudness=loud, env_fps=env_fps,
            spike_times=spikes, tempo=tempo, beat_times=beats,
        )

    # ---- helpers ------------------------------------------------------------
    @staticmethod
    def _normalise(arr: np.ndarray) -> np.ndarray:
        if arr.size == 0:
            return arr
        lo, hi = float(arr.min()), float(arr.max())
        if hi - lo < 1e-9:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    @staticmethod
    def _detect_spikes(loud: np.ndarray, env_fps: float,
                       z_threshold: float = 1.8, min_gap_s: float = 1.0) -> list[float]:
        """Find loudness peaks that stand out from the local mean."""
        if loud.size == 0 or env_fps <= 0:
            return []
        mean, std = float(loud.mean()), float(loud.std())
        if std < 1e-6:
            return []
        threshold = mean + z_threshold * std
        min_gap = int(min_gap_s * env_fps)

        spikes: list[float] = []
        last = -min_gap
        for i in range(1, loud.size - 1):
            if (
                loud[i] >= threshold
                and loud[i] >= loud[i - 1]
                and loud[i] >= loud[i + 1]
                and (i - last) >= min_gap
            ):
                spikes.append(i / env_fps)
                last = i
        return spikes

    def _extract_audio(self, video_path: Path) -> Path | None:
        """Extract a mono WAV from a video using ffmpeg."""
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            logger.warning("ffmpeg unavailable; cannot extract audio.")
            return None
        out = Path(tempfile.mktemp(suffix=".wav", prefix="gm_audio_"))
        try:
            res = subprocess.run(
                [
                    ffmpeg, "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", str(self.target_sr),
                    "-f", "wav", str(out),
                ],
                capture_output=True, text=True, timeout=600, check=False,
            )
            if res.returncode != 0 or not out.exists():
                logger.debug("Audio extraction returned %d", res.returncode)
                return None
            return out
        except (subprocess.SubprocessError, OSError) as exc:
            logger.debug("Audio extraction failed: %s", exc)
            return None

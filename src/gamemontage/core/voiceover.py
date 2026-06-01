"""Text-to-speech voiceover.

Default backend is ``edge-tts`` (free, no API key). An ElevenLabs adapter is
stubbed for users who have an API key. The result is an audio file path that the
montage builder can mix under the music bed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from gamemontage.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceoverEngine:
    """Generate narration audio from text."""

    def __init__(self, voice: str = "en-US-GuyNeural") -> None:
        self.voice = voice

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(self, text: str, out_path: Path,
                   rate: str = "+0%", volume: str = "+0%") -> Path | None:
        """Synthesize ``text`` to ``out_path`` (mp3). Returns the path or None."""
        if not text.strip():
            return None
        if not self.available():
            logger.warning("edge-tts not installed; voiceover skipped.")
            return None
        try:
            asyncio.run(self._edge_tts(text, out_path, rate, volume))
            if out_path.exists() and out_path.stat().st_size > 0:
                logger.info("Voiceover written to %s", out_path)
                return out_path
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Voiceover synthesis failed: %s", exc)
            return None

    async def _edge_tts(self, text: str, out_path: Path, rate: str, volume: str) -> None:
        import edge_tts

        out_path.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(text, self.voice, rate=rate, volume=volume)
        await communicate.save(str(out_path))

    # ---- optional adapter ---------------------------------------------------
    def synthesize_elevenlabs(self, text: str, out_path: Path, api_key: str,
                              voice_id: str = "Rachel") -> Path | None:
        """Stub for ElevenLabs. Requires the ``elevenlabs`` package + API key."""
        try:
            from elevenlabs import save  # type: ignore
            from elevenlabs.client import ElevenLabs  # type: ignore
        except ImportError:
            logger.warning("elevenlabs package not installed.")
            return None
        try:
            client = ElevenLabs(api_key=api_key)
            audio = client.generate(text=text, voice=voice_id)
            save(audio, str(out_path))
            return out_path if out_path.exists() else None
        except Exception as exc:  # noqa: BLE001
            logger.error("ElevenLabs synthesis failed: %s", exc)
            return None

    @staticmethod
    def list_common_voices() -> list[str]:
        """A handful of popular edge-tts voices for the settings dropdown."""
        return [
            "en-US-GuyNeural",
            "en-US-AriaNeural",
            "en-US-JennyNeural",
            "en-US-ChristopherNeural",
            "en-GB-RyanNeural",
            "en-GB-SoniaNeural",
            "en-AU-WilliamNeural",
        ]

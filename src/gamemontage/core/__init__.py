"""The GameMontage AI editing engine.

Submodules:

* :mod:`video_manager`     -- probe/import source clips, generate thumbnails.
* :mod:`audio_analyzer`    -- RMS spikes & beat detection (librosa).
* :mod:`highlight_detector`-- fuse audio/motion/flash/text signals into scores.
* :mod:`montage_creator`   -- assemble selected highlights with effects.
* :mod:`effects`           -- reusable MoviePy clip transforms (zoom/shake/...).
* :mod:`captions`          -- Whisper transcription -> animated caption clips.
* :mod:`color_grading`     -- LUT-free numpy color looks.
* :mod:`voiceover`         -- edge-tts narration.
* :mod:`thumbnail`         -- pick + render an epic thumbnail.
* :mod:`exporter`          -- final render with the chosen codec/aspect.
"""

from gamemontage.core.pipeline import MontagePipeline, PipelineCallbacks

__all__ = ["MontagePipeline", "PipelineCallbacks"]

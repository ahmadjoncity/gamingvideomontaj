"""Headless command-line interface for GameMontage AI.

Lets power users run the full pipeline without opening the GUI:

    python -m gamemontage.cli build --input ./clips --game valorant \
        --aspect 9:16 --resolution 1080p --output output/montage.mp4

Run ``python -m gamemontage.cli --help`` for all options.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from gamemontage.app_config import Settings, list_presets
from gamemontage.core.pipeline import MontagePipeline, PipelineCallbacks
from gamemontage.core.video_manager import VideoManager
from gamemontage.models import AspectRatio, ExportSettings, Project, Resolution
from gamemontage.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gamemontage",
        description="Automatically edit gaming footage into epic montages.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Detect highlights and render a montage.")
    b.add_argument("--input", "-i", nargs="+", required=True,
                   help="Video file(s) and/or folder(s) to import.")
    b.add_argument("--game", "-g", default="default",
                   help=f"Game preset. Available: {', '.join(list_presets())}")
    b.add_argument("--preset", default=None,
                   help="Path to a custom preset JSON (overrides --game).")
    b.add_argument("--output", "-o", default="output/montage.mp4",
                   help="Output video path.")
    b.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "1:1"])
    b.add_argument("--resolution", default="1080p",
                   choices=["720p", "1080p", "1440p", "4k"])
    b.add_argument("--codec", default="h264", choices=["h264", "h265"])
    b.add_argument("--fps", type=int, default=30)
    b.add_argument("--music", default=None, help="Background music file.")
    b.add_argument("--gpu", action="store_true", help="Use GPU encoder if available.")
    b.add_argument("--no-captions", action="store_true", help="Disable captions.")
    b.add_argument("--ocr", action="store_true", help="Enable kill-feed OCR.")
    b.add_argument("--name", default="Montage", help="Project / output name.")

    sub.add_parser("presets", help="List available game presets.")
    return parser


def _progress(stage: str, frac: float, msg: str) -> None:
    bar_len = 28
    filled = int(bar_len * frac)
    bar = "#" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\r[{stage:<9}] |{bar}| {frac * 100:5.1f}% {msg[:40]:<40}")
    sys.stdout.flush()
    if frac >= 1.0:
        sys.stdout.write("\n")


def cmd_build(args: argparse.Namespace) -> int:
    vm = VideoManager()
    clips = vm.import_many(args.input, make_thumbnail=False)
    if not clips:
        logger.error("No video files found in: %s", args.input)
        return 2
    logger.info("Imported %d clip(s).", len(clips))

    project = Project(name=args.name, game_type=args.game)
    project.style_preset = args.preset or args.game
    project.clips = clips
    if args.music:
        project.music_path = Path(args.music)

    project.export = ExportSettings(
        aspect=AspectRatio(args.aspect),
        resolution=Resolution(args.resolution),
        codec=args.codec,
        fps=args.fps,
        use_gpu=args.gpu,
    )
    out_path = Path(args.output)
    project.output_dir = out_path.parent
    project.name = out_path.stem

    settings = Settings.load()
    settings.enable_captions = not args.no_captions
    settings.enable_ocr = args.ocr
    settings.use_gpu_encode = args.gpu

    pipeline = MontagePipeline(settings)
    callbacks = PipelineCallbacks(on_progress=_progress)

    start = time.time()
    result = pipeline.run_all(project, callbacks)
    elapsed = time.time() - start

    if result.error:
        logger.error("Build failed: %s", result.error)
        return 1
    if result.cancelled:
        logger.warning("Build cancelled.")
        return 1

    logger.info("Done in %.1fs", elapsed)
    if result.montage_path:
        logger.info("Montage : %s", result.montage_path)
    if result.thumbnail_path:
        logger.info("Thumbnail: %s", result.thumbnail_path)
    return 0


def cmd_presets(_args: argparse.Namespace) -> int:
    print("Available game presets:")
    for name in list_presets():
        print(f"  - {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging("INFO")
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        return cmd_build(args)
    if args.command == "presets":
        return cmd_presets(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

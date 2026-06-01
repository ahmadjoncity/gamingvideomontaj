<div align="center">

# 🎮 GameMontage AI

### *yoki AutoGamerEdit* — automatic epic montage editor for gamers

**Drop in your raw gameplay → get a hype, captioned, beat-synced montage ready for YouTube, TikTok & Shorts.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GUI: CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-1f6feb.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

---

## ✨ What is this?

**GameMontage AI** is an open-source desktop application that watches your raw gameplay
recordings, **automatically finds the best moments** (kills, clutches, funny/epic spikes),
and stitches them into a fast-paced montage with **captions, text overlays, color grading,
beat-synced music and transitions** — then exports in the right aspect ratio for whatever
platform you target.

It is built to be **modular** and **degrade gracefully**: the heavy AI features
(Whisper captions, Tesseract kill-feed OCR, TTS voiceover) are optional. The core montage
engine works with just MoviePy + OpenCV + librosa.

> ⚠️ **Status:** Beta. This is a real, runnable application skeleton with a working GUI,
> a complete processing pipeline, and clean extension points. Some AI heuristics are
> intentionally simple so you can tune them per game.

---

## 🖼️ Screenshots

> _Add your own screenshots to `examples/screenshots/` and they will render here._

| Import & Library | Highlight Detection | Montage & Effects | Export |
| --- | --- | --- | --- |
| ![import](examples/screenshots/import.png) | ![highlights](examples/screenshots/highlights.png) | ![montage](examples/screenshots/montage.png) | ![export](examples/screenshots/export.png) |

---

## 🚀 Features

### 📥 Video Import & Management
- Import multiple files **or an entire folder**.
- Library view with **thumbnail + duration + resolution + FPS**.
- Per-clip enable/disable for the montage.

### 🧠 AI-Powered Highlight Detection *(the core)*
Scores every video on a sliding window using a fusion of signals:
- **Audio spikes** — gunshots, screams, hit-markers (RMS / onset energy via `librosa`).
- **High-motion scenes** — frame-difference / optical-flow magnitude via OpenCV.
- **Scene flashes** — sudden brightness changes (kills, abilities, explosions).
- **Kill-feed / on-screen text** — optional Tesseract OCR looking for game keywords.
- **Per-game presets** — Valorant, CS2, Fortnite, Minecraft, Apex, LoL, COD… each ships
  its own keyword list, weighting and overlay style.

### 🎬 Automatic Montage Creation
- One click **"Create Epic Montage"** picks the top **8–15** highlights.
- Dynamic ordering (intensity-aware: builds toward the biggest moment).
- **Slow-mo, punch-in zoom, camera shake**, glitch & zoom transitions.

### 🎚️ Automatic Effects
- **Music + beat sync** — drops cuts on detected beats (librosa beat tracking).
- **Animated gaming captions** — `faster-whisper` transcription with big outlined,
  shadowed, color word-pop captions.
- **Text overlays** — `INSANE 1v5 CLUTCH`, `ACE!`, kill counters, player name, etc.
- **Color grading** — cinematic / vibrant / HDR-like gaming looks.

### 📤 Export
- **YouTube (16:9)**, **TikTok / Shorts / Reels (9:16)**, **Twitch (16:9)**.
- **1080p** and **4K**.
- **H.264** and **H.265 (HEVC)**, optional NVENC GPU encoding.
- **Automatic thumbnail** grabbed from the most epic frame.

### 🧩 Advanced
- **JSON config templates** — save/load your own editing style.
- **Batch processing** — queue multiple sources.
- **Voiceover** via `edge-tts` (free, no key) — ElevenLabs adapter stubbed.
- **Progress bar + cancel**, **Settings page** (model size, device, FFmpeg path, GPU).

---

## 🛠️ Tech Stack

| Area | Library |
| --- | --- |
| GUI | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) |
| Video | [MoviePy](https://zulko.github.io/moviepy/) + FFmpeg, [OpenCV](https://opencv.org/) |
| Audio | [librosa](https://librosa.org/), [pydub](https://github.com/jiaaro/pydub) |
| Captions | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| OCR | [pytesseract](https://github.com/madmaze/pytesseract) |
| TTS | [edge-tts](https://github.com/rany2/edge-tts) |

---

## 📦 Installation

### 1. Prerequisites
- **Python 3.11+**
- **FFmpeg** on your `PATH` (MoviePy uses it). `imageio-ffmpeg` ships a fallback binary.
- *(Optional, for OCR)* **Tesseract OCR** binary.
- *(Optional, for GPU captions)* CUDA + cuDNN for `faster-whisper`.

<details>
<summary>Install FFmpeg & Tesseract per OS</summary>

```bash
# Windows (winget)
winget install Gyan.FFmpeg
winget install UB-Mannheim.TesseractOCR

# macOS (brew)
brew install ffmpeg tesseract

# Debian / Ubuntu
sudo apt update && sudo apt install -y ffmpeg tesseract-ocr
```
</details>

### 2. Clone & create a virtual env
```bash
git clone https://github.com/yoki/gamemontage-ai.git
cd gamemontage-ai

python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate
```

### 3. Install
```bash
# Core (montage engine + GUI)
pip install -r requirements.txt

# Optional AI extras (Whisper captions, OCR, TTS) — larger download
pip install -r requirements-ai.txt

# …or install as a package with extras
pip install -e ".[full]"
```

---

## ▶️ Usage

### Launch the GUI
```bash
python main.py
# or, if installed as a package:
gamemontage
```

### Typical workflow
1. **Import** → add gameplay files or a folder.
2. **Highlights** → pick your **Game Type**, click **Detect Highlights**, review the scored clips.
3. **Montage** → choose a **style preset**, music, captions on/off → **Create Epic Montage**.
4. **Export** → pick platform (YouTube / TikTok / Twitch), resolution & codec → **Export** + thumbnail.

### Headless / CLI (no GUI)
```bash
# Detect + build + export in one go from the terminal
python -m gamemontage.cli build \
    --input "C:/clips/" \
    --game valorant \
    --preset configs/valorant.json \
    --aspect 9:16 \
    --resolution 1080p \
    --output output/montage.mp4
```

---

## 🗂️ Project Structure

```
gamemontage-ai/
├── main.py                     # GUI entry point
├── pyproject.toml / setup.py   # packaging
├── requirements*.txt
├── configs/                    # JSON editing templates (per game)
├── examples/                   # sample configs + screenshots
└── src/gamemontage/
    ├── app_config.py           # global settings + paths
    ├── cli.py                  # headless pipeline
    ├── core/                   # the editing engine
    │   ├── video_manager.py
    │   ├── highlight_detector.py
    │   ├── audio_analyzer.py
    │   ├── montage_creator.py
    │   ├── effects.py
    │   ├── captions.py
    │   ├── color_grading.py
    │   ├── voiceover.py
    │   ├── thumbnail.py
    │   └── exporter.py
    ├── gui/                    # CustomTkinter UI
    │   ├── app.py
    │   ├── theme.py
    │   ├── widgets.py
    │   └── pages/
    ├── models/                 # dataclasses (Clip, Highlight, Project…)
    └── utils/                  # logger, ffmpeg helpers
```

---

## ⚙️ Configuration

Editing templates live in `configs/*.json`. Each game preset controls detection weighting,
keyword lists, overlay text and the default look. Duplicate one, tweak it, and load it from
the **Montage** page. See [`configs/default.json`](configs/default.json).

---

## 🗺️ Roadmap

- [ ] Drag-to-reorder timeline editor
- [ ] Real-time preview player
- [ ] Trained ML kill detector (ONNX) per game
- [ ] More transition packs & particle overlays
- [ ] ElevenLabs + OpenAI TTS adapters
- [ ] Auto-upload to YouTube/TikTok via API
- [ ] Multi-language captions

---

## 🤝 Contributing

PRs welcome! Please run `ruff`, `black` and `pytest` before submitting:
```bash
pip install -e ".[dev]"
ruff check . && black --check . && pytest -q
```

## 📄 License

[MIT](LICENSE) © 2026 yoki / GameMontage AI contributors.

> **Music & assets disclaimer:** ship only music you have the rights to. The app does not
> bundle copyrighted tracks; point it at your own/licensed library (e.g. Epidemic Sound).

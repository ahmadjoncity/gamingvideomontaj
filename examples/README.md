# Examples

This folder contains ready-to-use snippets and assets to help you get going.

## 1. Quick start (GUI)

```bash
python main.py
```

1. **Import** a folder of gameplay clips.
2. Go to **Highlights**, choose your game, hit **Detect Highlights**.
3. On **Montage**, pick a style and (optionally) some music.
4. On **Export**, choose `TikTok / Shorts (9:16)` + `1080p`, then **Export Montage**.

## 2. Headless (CLI) one-liner

```bash
python -m gamemontage.cli build \
    --input ./my_clips \
    --game valorant \
    --aspect 9:16 \
    --resolution 1080p \
    --codec h264 \
    --music ./music/hype.mp3 \
    --output output/valorant_montage.mp4
```

List the bundled game presets:

```bash
python -m gamemontage.cli presets
```

## 3. Custom preset

Copy [`custom_preset.example.json`](custom_preset.example.json) into the
`configs/` folder, rename it (e.g. `configs/my_style.json`), tweak the values,
and select it on the **Montage** page or pass `--preset configs/my_style.json`
to the CLI.

Key fields:

| Section | Field | Meaning |
| --- | --- | --- |
| `detection.weights` | `audio/motion/flash/text` | how much each signal counts toward a highlight score (auto-normalised) |
| `detection.min_score` | `0..1` | minimum fused score to keep a moment |
| `montage.target_highlights` | int | how many clips to include |
| `montage.transition` | `zoom\|glitch\|fade\|cut` | transition between clips |
| `style.color_grade` | `vibrant\|cinematic\|hdr\|cold\|warm\|none` | overall look |
| `overlays.*` | text | the big on-screen text per highlight type |

## 4. Screenshots

Drop UI screenshots into `examples/screenshots/` named `import.png`,
`highlights.png`, `montage.png` and `export.png` to populate the README gallery.

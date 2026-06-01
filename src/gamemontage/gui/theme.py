"""Centralised colors, fonts and spacing for a modern dark gaming look."""

from __future__ import annotations

# Neon-on-charcoal palette (Valorant/Apex-ish)
COLORS = {
    "bg": "#0E0F13",
    "bg_alt": "#15171E",
    "surface": "#1B1E27",
    "surface_alt": "#232733",
    "border": "#2C313E",
    "primary": "#00E5FF",      # cyan accent
    "primary_hover": "#33ECFF",
    "secondary": "#7C4DFF",    # purple
    "secondary_hover": "#9670FF",
    "success": "#21D07A",
    "warning": "#FFC542",
    "danger": "#FF4D6D",
    "danger_hover": "#FF6B85",
    "text": "#EAECEF",
    "text_dim": "#9AA0AC",
    "text_faint": "#5C6370",
}

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

FONTS = {
    "title": (FONT_FAMILY, 26, "bold"),
    "h1": (FONT_FAMILY, 20, "bold"),
    "h2": (FONT_FAMILY, 16, "bold"),
    "body": (FONT_FAMILY, 13),
    "body_bold": (FONT_FAMILY, 13, "bold"),
    "small": (FONT_FAMILY, 11),
    "nav": (FONT_FAMILY, 14, "bold"),
    "mono": (FONT_FAMILY_MONO, 11),
}

# Game presets exposed in the UI dropdown (name -> preset key/filename stem).
GAME_TYPES = [
    "default",
    "valorant",
    "cs2",
    "fortnite",
    "minecraft",
    "apex",
    "lol",
    "cod",
]

COLOR_GRADES = ["vibrant", "cinematic", "hdr", "cold", "warm", "none"]
TRANSITIONS = ["zoom", "glitch", "fade", "cut"]


def font(name: str):
    """Return a CTkFont-compatible tuple by semantic name."""
    return FONTS.get(name, FONTS["body"])

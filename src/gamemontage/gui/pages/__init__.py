"""GUI pages (one per workflow step)."""

from gamemontage.gui.pages.base import BasePage
from gamemontage.gui.pages.export_page import ExportPage
from gamemontage.gui.pages.highlights_page import HighlightsPage
from gamemontage.gui.pages.import_page import ImportPage
from gamemontage.gui.pages.montage_page import MontagePage
from gamemontage.gui.pages.settings_page import SettingsPage

__all__ = [
    "BasePage",
    "ImportPage",
    "HighlightsPage",
    "MontagePage",
    "ExportPage",
    "SettingsPage",
]

"""Virtual Desktop page composition."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static, TabPane

from plaivid_cli.presentation.theme import Palette

from .components import (
    DesktopAuditPanel,
    DesktopDetailPanel,
    DesktopInventoryPanel,
    DesktopSummary,
)


class VirtualDesktopPage(TabPane):
    """Compose Desktop summary, lifecycle controls, inventory, and detail panel."""

    def __init__(self, palette: Palette) -> None:
        super().__init__("Virtual Desktops", id="desktops")
        self._palette = palette

    def compose(self) -> ComposeResult:
        yield DesktopSummary(self._palette)
        yield DesktopInventoryPanel()
        yield Static("Selected Desktop · 0 target(s)", id="desktop-scope", markup=False)
        yield DesktopDetailPanel()
        yield DesktopAuditPanel()

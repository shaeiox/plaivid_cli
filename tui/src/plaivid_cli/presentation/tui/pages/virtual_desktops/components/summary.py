"""Virtual Desktop count, runtime, inventory, and refresh summary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button

from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import MetricTile


class DesktopSummary(Horizontal):
    """Group Desktop inventory counts and the page refresh action."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(id="desktop-summary")
        self._palette = palette

    def compose(self) -> ComposeResult:
        yield MetricTile(
            title="Defined Desktops",
            value_id="desktop-count",
            initial="—",
            palette=self._palette,
        )
        yield MetricTile(
            title="Running",
            value_id="desktop-running-label",
            initial="—",
            palette=self._palette,
        )
        yield MetricTile(
            title="Inventory",
            value_id="desktop-quality",
            initial="Not collected",
            palette=self._palette,
        )
        yield Button("Refresh", id="desktop-refresh", variant="primary")

"""Virtual Machine count, process, inventory, and refresh summary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button

from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import MetricTile


class VMSummary(Horizontal):
    """Group VM inventory counts and the page refresh action."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(id="fleet-summary")
        self._palette = palette

    def compose(self) -> ComposeResult:
        yield MetricTile(
            title="Defined VMs", value_id="vm-count", initial="—", palette=self._palette
        )
        yield MetricTile(
            title="Processes seen", value_id="process-count", initial="—", palette=self._palette
        )
        yield MetricTile(
            title="Inventory",
            value_id="inventory-quality",
            initial="Not collected",
            palette=self._palette,
        )
        yield Button("Refresh", id="refresh-button", variant="primary")

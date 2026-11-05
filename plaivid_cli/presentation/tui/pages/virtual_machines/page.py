"""Virtual Machine page composition."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static, TabPane

from plaivid_cli.presentation.theme import Palette

from .components import VMAuditPanel, VMDetailPanel, VMInventoryPanel, VMSummary


class VirtualMachinePage(TabPane):
    """Compose VM summary, inventory controls, and selected-record details."""

    def __init__(self, palette: Palette) -> None:
        super().__init__("Virtual Machines", id="fleet")
        self._palette = palette

    def compose(self) -> ComposeResult:
        yield VMSummary(self._palette)
        yield VMInventoryPanel()
        yield Static("Selected VM · 0 target(s)", id="vm-scope", markup=False)
        yield VMDetailPanel()
        yield VMAuditPanel()

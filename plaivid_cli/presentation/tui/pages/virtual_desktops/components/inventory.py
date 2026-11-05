"""Virtual Desktop search, action, selection, and table section."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from plaivid_cli.presentation.tui.components import CheckableTable, InventoryToolbar


class DesktopInventoryPanel(Vertical):
    """Own Desktop inventory controls and table layout, not listing or operations."""

    def __init__(self) -> None:
        super().__init__(id="desktop-list")

    def compose(self) -> ComposeResult:
        yield InventoryToolbar(
            id="desktop-toolbar",
            action_id="desktop-actions",
            selection_id="desktop-all",
            selection_label="Apply to all Desktops",
            audit_id="desktop-audit-toggle",
            search_id="desktop-search",
            search_placeholder="Search Desktop name",
        )
        yield CheckableTable(id="desktop-table", cursor_type="row", zebra_stripes=True)
        yield Static("No operation submitted.", id="desktop-action-status", markup=False)

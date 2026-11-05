"""Virtual Machine search, lifecycle-action, selection, and table section."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from plaivid_cli.presentation.tui.components import CheckableTable, InventoryToolbar


class VMInventoryPanel(Vertical):
    """Own the VM page inventory controls and table layout, not its data or operations."""

    def __init__(self) -> None:
        super().__init__(id="vm-list")

    def compose(self) -> ComposeResult:
        yield InventoryToolbar(
            id="vm-toolbar",
            action_id="bulk-actions",
            selection_id="select-all",
            selection_label="Apply to all VMs",
            audit_id="audit-toggle",
            search_id="vm-search",
            search_placeholder="Search VM name",
        )
        yield CheckableTable(id="fleet-table", cursor_type="row", zebra_stripes=True)
        yield Static("No operation submitted.", id="action-status", markup=False)

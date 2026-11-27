"""Virtual Desktop selected-record detail and audit panels."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from plaivid_cli.presentation.tui.audit import AuditTable


class DesktopDetailPanel(VerticalScroll):
    """Scroll a selected Desktop's presentation-only details."""

    def __init__(self) -> None:
        super().__init__(id="desktop-detail-scroll")

    def compose(self) -> ComposeResult:
        yield Static("Select a Desktop to inspect its details.", id="desktop-detail", markup=False)


class DesktopAuditPanel(AuditTable):
    """Render the read-only audit result associated with the Desktop page."""

    def __init__(self) -> None:
        super().__init__(id="desktop-audit-panel")

"""Virtual Machine selection detail and audit panels."""

from textual.widgets import Static

from plaivid_cli.presentation.tui.audit import AuditTable


class VMDetailPanel(Static):
    """Render selected VM identity and optional asynchronous detail fields."""

    def __init__(self) -> None:
        super().__init__("Select a VM to inspect its details.", id="detail-box", markup=False)


class VMAuditPanel(AuditTable):
    """Render the read-only audit result associated with the VM page."""

    def __init__(self) -> None:
        super().__init__(id="audit-panel")

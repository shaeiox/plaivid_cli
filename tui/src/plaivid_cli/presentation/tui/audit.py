"""Read-only audit tables and their Textual presentation behavior."""

from __future__ import annotations

from rich.text import Text
from textual import work
from textual.widgets import DataTable

from plaivid_cli.domain.models import AuditEntry
from plaivid_cli.domain.redaction import redact_text


class AuditTable(DataTable):
    """A shared, independently scrollable table for both audit panels."""

    def __init__(self, *, id: str) -> None:
        super().__init__(id=id, zebra_stripes=True, cursor_type="none", show_header=True)

    def on_mount(self) -> None:
        # DataTable measures column labels using the active app, so add them on mount.
        for key, label, width in (
            ("time", "Time", 19),
            ("user", "User", 15),
            ("user_ip", "IP", 15),
            ("product", "Product", 12),
            ("command", "Command", 30),
            ("result", "Result", 20),
            ("succeeded", "Status", 12),
        ):
            self.add_column(label, width=width, key=key)


class AuditMixin:
    """Audit behavior for the composed Textual application."""

    @work(thread=True, group="audit", exclusive=True)
    def _request_audit(self, panel_id: str = "audit-panel") -> None:
        if self.session is None:
            return
        session_epoch = self._session_epoch
        try:
            entries = self.application.recent_audit(20)
        except Exception as exc:
            result: tuple[AuditEntry, ...] | str = (
                f"Audit unavailable: {type(exc).__name__}. The database is read-only."
            )
        else:
            result = entries or "No audit rows available. The local database is queried read-only."
        # Table updates must run on the UI thread, never in this worker.
        self.call_from_thread(self._publish_audit, panel_id, result, session_epoch)

    def _publish_audit(
        self, panel_id: str, result: tuple[AuditEntry, ...] | str, session_epoch: int
    ) -> None:
        # Ignore reads that completed after logout or a new session started.
        if self.session is None or session_epoch != self._session_epoch:
            return
        table = self.query_one(f"#{panel_id}", DataTable)
        table.clear()
        if isinstance(result, str):
            # Auto-height keeps the entire message visible in the narrow first column.
            table.add_row(Text(redact_text(result)), "", "", "", "", "", "", height=None)
            return
        for entry in result:
            status = Text("✔ Success", style="green") if entry.succeeded else Text("✘ Failed", style="red")
            # Rich Text prevents literal log values (including [REDACTED]) becoming markup.
            table.add_row(
                Text(redact_text(entry.time)),
                Text(redact_text(entry.user)),
                Text(redact_text(entry.user_ip)),
                Text(redact_text(entry.product)),
                Text(redact_text(entry.command)),
                Text(redact_text(entry.result)),
                status,
                height=None,
            )

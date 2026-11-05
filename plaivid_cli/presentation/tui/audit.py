"""Textual presentation for the local PVM management application."""

from __future__ import annotations

from textual import work
from textual.widgets import (
    Static,
)

from plaivid_cli.domain.redaction import redact_text


class AuditMixin:
    """Audit behavior for the composed Textual application."""

    @work(thread=True, group="audit", exclusive=True)
    def _request_audit(self, panel_id: str = "audit-panel") -> None:
        if self.session is None:
            return
        try:
            entries = self.application.recent_audit(20)
        except Exception as exc:
            text = f"Audit unavailable: {type(exc).__name__}. The database is read-only."
        else:
            if not entries:
                text = "No audit rows available. The local database is queried read-only."
            else:
                lines = ["READ-ONLY AUDIT  ·  newest first"]
                lines.extend(
                    f"{entry.time}  {entry.user}  {entry.command}  {entry.result}"
                    for entry in entries
                )
                text = "\n".join(lines)
        self.call_from_thread(self._publish_audit, panel_id, text)

    def _publish_audit(self, panel_id: str, text: str) -> None:
        self.query_one(f"#{panel_id}", Static).update(redact_text(text))

"""Reusable table that posts a selection message when its checkbox column is clicked."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import DataTable


class CheckableTable(DataTable):
    """Row table whose first column toggles a UUID selection."""

    class CheckRequested(Message):
        def __init__(self, table: CheckableTable, key: str) -> None:
            super().__init__()
            self.table = table
            self.key = key

    async def _on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if meta.get("column") == 0 and "row" in meta and not meta.get("out_of_bounds", False):
            rows = self.ordered_rows
            index = meta["row"]
            if 0 <= index < len(rows):
                key = rows[index].key
                self.post_message(self.CheckRequested(self, str(getattr(key, "value", key))))
            return
        await super()._on_click(event)

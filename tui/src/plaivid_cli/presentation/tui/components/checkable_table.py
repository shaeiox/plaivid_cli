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
        """Claim only the checkbox cell; let the base class own every other click.

        Textual dispatches the naming-convention handler down the MRO, so this
        override *and* ``DataTable._on_click`` both run for one click. Forwarding
        with ``super()`` would therefore make the base class post every message
        twice — a duplicated ``HeaderSelected`` advanced a header-click sort two
        steps per click. The base handler runs on its own, so this one must not
        call it.
        """
        meta = event.style.meta
        if meta.get("column") == 0 and "row" in meta and not meta.get("out_of_bounds", False):
            rows = self.ordered_rows
            index = meta["row"]
            if 0 <= index < len(rows):
                key = rows[index].key
                self.post_message(self.CheckRequested(self, str(getattr(key, "value", key))))

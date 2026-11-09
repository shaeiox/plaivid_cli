"""Scrollable, centrally-owned task status board docked above the key hints.

Presentation only: it imports domain task values but never the application
layer, matching the repository's component boundary rule. A ``DataTable`` is used
rather than a ``RichLog`` because rows change state in place
(QUEUED -> RUNNING -> SUCCEEDED); an append-only log would either duplicate a
row per transition or lose the history.
"""

from __future__ import annotations

from datetime import UTC, datetime

from textual.message import Message
from textual.widgets import DataTable
from textual.widgets.data_table import ColumnKey

from plaivid_cli.domain.models import TaskRecord, TaskStatus
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import Palette

COLUMNS = ("Time", "Action", "Target", "State", "Detail")

_STATE_GLYPH = {
    TaskStatus.QUEUED: "·",
    TaskStatus.RUNNING: "▶",
    TaskStatus.SUCCEEDED: "✓",
    TaskStatus.FAILED: "✗",
    TaskStatus.REJECTED: "⊘",
    TaskStatus.UNKNOWN: "?",
}

# TaskStatus -> palette attribute. Unknown is warning-coloured, never error-
# coloured: an unestablished outcome is not a definite failure.
_STATE_COLOUR = {
    TaskStatus.QUEUED: "muted",
    TaskStatus.RUNNING: "primary",
    TaskStatus.SUCCEEDED: "success",
    TaskStatus.FAILED: "error",
    TaskStatus.REJECTED: "warning",
    TaskStatus.UNKNOWN: "warning",
}


class TaskViewFooter(DataTable):
    """Live task board. Hidden while empty so the tuned layout is untouched."""

    DEFAULT_CSS = ""

    class TaskSelected(Message):
        """A task row was activated (Enter); the app may reveal its target."""

        def __init__(self, footer: TaskViewFooter, task_id: str) -> None:
            super().__init__()
            self.footer = footer
            self.task_id = task_id

    def __init__(self, palette: Palette | None = None) -> None:
        super().__init__(id="task-footer", zebra_stripes=False)
        self._palette = palette
        self._rows: dict[str, TaskRecord] = {}
        self._order: list[str] = []
        self._column_keys: tuple[ColumnKey, ...] = ()
        self._elapsed_timer = None
        self.can_focus = True

    # ------------------------------------------------------------- lifecycle

    def on_mount(self) -> None:
        self._column_keys = tuple(self.add_columns(*COLUMNS))
        self._set_visible(False)
        self._update_border_title(0)

    def _set_visible(self, visible: bool) -> None:
        """Hidden while empty, so an idle footer costs no layout height."""
        self.display = visible
        self.set_class(visible, "-visible")

    # ------------------------------------------------------------------- API

    def apply_record(self, record: TaskRecord) -> None:
        """Insert or update one row in place, keyed by the stable task id."""
        task_id = record.task_id
        if not self.display:
            self._set_visible(True)
        if task_id in self._rows:
            self._rows[task_id] = record
        else:
            self._rows[task_id] = record
            self._order.append(task_id)
            self.add_row(*self._cells(record), key=task_id)
        self._refresh_row(record)
        self._sync_timer()
        self._update_border_title(self._active_count())
        self._follow_newest(record)

    def clear_board(self) -> None:
        """Drop every row and hide the board again."""
        self._stop_timer()
        self._rows.clear()
        self._order.clear()
        if self.row_count:
            self.clear(columns=False)
        self._set_visible(False)
        self._update_border_title(0)

    def record_count(self) -> int:
        return len(self._rows)

    def active_count(self) -> int:
        return self._active_count()

    def record(self, task_id: str) -> TaskRecord | None:
        return self._rows.get(task_id)

    # ------------------------------------------------------------- rendering

    def _cells(self, record: TaskRecord) -> tuple[object, str, str, str, str]:
        return (
            record.submitted_at.astimezone().strftime("%H:%M:%S"),
            record.key.action.value.upper(),
            _target_label(record),
            self._state_text(record),
            self._detail(record, datetime.now(UTC)),
        )

    def _refresh_row(self, record: TaskRecord) -> None:
        if record.task_id not in self._rows or not self._column_keys:
            return
        cells = self._cells(record)
        for index in range(1, len(cells)):  # column 0 (time) never changes
            self.update_cell(record.task_id, self._column_keys[index], cells[index])

    def _state_text(self, record: TaskRecord) -> str:
        glyph = _STATE_GLYPH.get(record.status, "·")
        text = f"{glyph} {record.status.value}"
        return self._colour(text, record.status)

    def _colour(self, text: str, status: TaskStatus) -> str:
        """Wrap in Textual markup only when the palette is decorative.

        16-colour and NO_COLOR output must stay readable without colour, so the
        glyph and the word carry the meaning on their own.
        """
        palette = self._palette
        if palette is None or not palette.decorative:
            return text
        attribute = _STATE_COLOUR.get(status)
        colour = getattr(palette, attribute, None) if attribute else None
        if not colour:
            return text
        return f"[{colour}]{text}[/]"

    def _detail(self, record: TaskRecord, now: datetime) -> str:
        safe = redact_text(record.message)
        if record.status is TaskStatus.RUNNING:
            elapsed = _elapsed(record.elapsed_seconds(now=now))
            return f"{elapsed} · {safe}" if safe else elapsed
        if record.status.is_terminal and record.finished_at is not None:
            elapsed = _elapsed(record.elapsed_seconds(now=now))
            return f"{elapsed} · {safe}" if safe else elapsed
        return safe

    def _follow_newest(self, record: TaskRecord) -> None:
        """Pin to the newest row only when the operator has not scrolled away."""
        if record.status.is_terminal:
            return
        try:
            if self.cursor_row >= max(0, self.row_count - 2):
                self.move_cursor(row=self.row_count - 1)
        except Exception:
            pass

    # ---------------------------------------------------------------- timers

    def _active_count(self) -> int:
        return sum(not record.status.is_terminal for record in self._rows.values())

    def _sync_timer(self) -> None:
        """Run the elapsed clock only while something is actually running."""
        if self._active_count() and self._elapsed_timer is None:
            self._elapsed_timer = self.set_interval(1.0, self._tick_elapsed)
        elif not self._active_count():
            self._stop_timer()

    def _stop_timer(self) -> None:
        timer = self._elapsed_timer
        self._elapsed_timer = None
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

    def _tick_elapsed(self) -> None:
        now = datetime.now(UTC)
        for record in list(self._rows.values()):
            if record.status.is_terminal:
                continue
            if not self._column_keys:
                return
            self.update_cell(
                record.task_id, self._column_keys[-1], self._detail(record, now)
            )

    def _update_border_title(self, active: int) -> None:
        total = len(self._rows)
        if not total:
            self.border_title = "Tasks"
            return
        self.border_title = (
            f"Tasks · {total} · {active} active" if active else f"Tasks · {total}"
        )


def _target_label(record: TaskRecord) -> str:
    label = redact_text(record.target.label or "")
    short = record.target.short
    if not label:
        return short
    return f"{label} {short}"


def _elapsed(seconds: float) -> str:
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


__all__ = ["COLUMNS", "TaskViewFooter"]

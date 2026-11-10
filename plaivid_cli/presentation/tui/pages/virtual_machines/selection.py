"""VM inventory selection, local search, and detail presentation."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.text import Text
from textual import on, work
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Checkbox, DataTable, Input, Static
from textual.widgets._data_table import CellDoesNotExist

from plaivid_cli.application.services import as_vm_detail
from plaivid_cli.domain.models import VMDetail, VMRecord
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import state_text

from ...components import CheckableTable
from ...components import display as _display
from ...components.sorting import (
    VM_SORT_COLUMNS,
    column_value,
    describe_sort,
    next_sort_state,
    sort_records,
)
from .components import (
    DetailPlaceholder,
    build_detail_placeholder,
    build_vm_detail,
)


class VMSelectionMixin:
    """Own the table's visible UUID selection and VM detail read model."""

    # Declared here so the composed app and the mixin agree on the detail state.
    _detail_record: VMRecord | None
    _detail_loaded: VMDetail | None
    _detail_uuid: str | None
    _detail_status: DetailPlaceholder | None

    @on(Checkbox.Changed, "#select-all")
    def vm_scope_changed(self) -> None:
        self._filter_vms()

    @on(Input.Changed, "#vm-search")
    def vm_search_changed(self) -> None:
        # Search is strictly local: changing the input never starts collection.
        self._filter_vms()

    def _check_cell(self, checked: bool) -> Text:
        if checked:
            return Text("☑", style=f"bold {self._palette.foreground}")
        return Text("☐", style=self._palette.muted)

    def _checked_group(self, table_id: str) -> set[str]:
        return self._vm_checked if table_id == "fleet-table" else self._desktop_checked

    def _set_check(self, table_id: str, uuid: str, checked: bool) -> None:
        group = self._checked_group(table_id)
        if checked:
            group.add(uuid)
        else:
            group.discard(uuid)
        table = self.query_one(f"#{table_id}", CheckableTable)
        columns = self._table_columns if table_id == "fleet-table" else self._desktop_columns
        try:
            table.update_cell(uuid, columns[0], self._check_cell(checked))
        except CellDoesNotExist:
            pass  # Row is hidden by the search filter; the state is applied when it reappears.
        if table_id == "fleet-table":
            self._filter_vms()  # refreshes the checked count; only changed cells are redrawn
        else:
            self._render_desktop_detail()

    @on(CheckableTable.CheckRequested)
    def check_requested(self, event: CheckableTable.CheckRequested) -> None:
        self._set_check(
            event.table.id or "",
            event.key,
            event.key not in self._checked_group(event.table.id or ""),
        )

    def _focused_checkable(self) -> CheckableTable | None:
        focused = self.focused
        if isinstance(focused, CheckableTable) and focused.id in ("fleet-table", "desktop-table"):
            return focused
        return None

    def action_toggle_check(self) -> None:
        table = self._focused_checkable()
        if table is None or table.cursor_row is None or not table.ordered_rows:
            return
        if not 0 <= table.cursor_row < len(table.ordered_rows):
            return
        key = table.ordered_rows[table.cursor_row].key
        uuid = str(getattr(key, "value", key))
        self._set_check(table.id or "", uuid, uuid not in self._checked_group(table.id or ""))

    def action_toggle_all(self) -> None:
        table = self._focused_checkable()
        if table is None:
            return
        shown = self._table_order if table.id == "fleet-table" else self._desktop_rows
        group = self._checked_group(table.id or "")
        everything = bool(shown) and all(uuid in group for uuid in shown)
        for uuid in shown:
            self._set_check(table.id or "", uuid, not everything)

    def _cell_text(self, column: int, cell: str) -> Text:
        # Column 2 is the object state (VM page) or cluster status (Virtual Desktops page).
        return state_text(cell, self._palette) if column == 2 else Text(cell)

    def _show_vm_sort_title(self) -> None:
        """Name the active sort in the panel title, so order is never implicit."""
        detail = describe_sort(self._vm_sort, VM_SORT_COLUMNS)
        title = "VM list" if not detail else f"VM list · {detail}"
        self._group_box(self.query_one("#vm-list", Vertical), "vms", title)

    def vm_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort the VM table from a column-header click.

        Registered only on the App (with a ``#fleet-table`` selector): decorating
        it here as well would fire the ascending/descending cycle twice per click
        and would also react to the Desktop table's headers.
        """
        self.action_sort_by_column(event.column_index)

    def action_sort_by_column(self, column: int) -> None:
        """Cycle the table's sort column (ascending -> descending -> default)."""
        previous = self._vm_sort
        self._vm_sort = next_sort_state(previous, column, VM_SORT_COLUMNS)
        if self._vm_sort != previous:
            self._filter_vms()

    def _vm_sort_key(self, column: int):
        """Comparable value per sortable column; absent values stay last."""
        by_column = {
            2: lambda item: column_value(item.name, item.uuid),
            3: lambda item: column_value(item.state, item.uuid),
            4: lambda item: column_value(item.process_seen, item.uuid, numeric=True),
            5: lambda item: column_value(item.vcpu, item.uuid, numeric=True),
            6: lambda item: column_value(item.mem_mb, item.uuid, numeric=True),
        }
        return by_column[column]

    def _filter_vms(self) -> None:
        query = self.query_one("#vm-search", Input).value.strip().casefold()
        outcome = sort_records(
            [record for record in self._records.values() if query in record.name.casefold()],
            self._vm_sort,
            # Default: VMs with observed process evidence first, then by name. This
            # is an evidence ordering, not an alphabetical one, so it is restored
            # only when no column sort is active.
            lambda item: (0 if item.process_seen else 1, item.name.casefold(), item.uuid),
            {column: self._vm_sort_key(column) for column in VM_SORT_COLUMNS},
        )
        records = outcome.records
        self._vm_sort = outcome.applied
        rows = {
            record.uuid: (
                str(index),
                redact_text(record.name),
                redact_text(record.state),
                "Observed" if record.process_seen else "Not observed",
                _display(record.vcpu),
                _display(record.mem_mb, suffix=" MB"),
            )
            for index, record in enumerate(records, start=1)
        }
        order = tuple(rows)
        table = self.query_one("#fleet-table", DataTable)
        if order != self._table_order:
            table.clear(columns=False)
            for uuid, cells in rows.items():
                table.add_row(
                    self._check_cell(uuid in self._vm_checked),
                    *(self._cell_text(index, cell) for index, cell in enumerate(cells)),
                    key=uuid,
                )
        else:
            for uuid, cells in rows.items():
                old = self._table_content.get(uuid, ())
                for column, cell in enumerate(cells):
                    if column >= len(old) or cell != old[column]:
                        table.update_cell(
                            uuid,
                            self._table_columns[column + 1],
                            self._cell_text(column, cell),
                            update_width=True,
                        )
        self._table_order, self._table_content = order, rows
        self._show_vm_sort_title()
        all_targets = self.query_one("#select-all", Checkbox).value
        count = len(self._records) if all_targets else int(bool(order))
        self.query_one("#vm-scope", Static).update(
            f"{'All unfiltered VMs' if all_targets else 'Selected VM'} · {count} target(s)"
            f" · {len(order)} shown · {len(self._vm_checked & set(self._records))} checked"
        )
        if self._selected_uuid not in rows:
            self._selected_uuid = order[0] if order else None
        if self._selected_uuid:
            table.move_cursor(row=order.index(self._selected_uuid), animate=False)
            self._render_record(self._records[self._selected_uuid])
        else:
            self._detail_record = None
            self._detail_loaded = None
            self._detail_uuid = None
            self._detail_status = None
            kind: DetailPlaceholder = (
                "no_match" if query and self._inventory is not None else "no_records"
            )
            self.query_one("#detail-box", Static).update(
                build_detail_placeholder(kind, self._palette)
            )

    @on(DataTable.RowHighlighted, "#fleet-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # A queued highlight may arrive while the screen is being torn down.
        if not self._running or not self.is_mounted(event.data_table):
            return
        key = getattr(event.row_key, "value", str(event.row_key))
        if str(key) not in self._table_order:
            return  # Ignore queued highlights for rows hidden by search.
        self._selected_uuid = str(key)
        record = self._records.get(self._selected_uuid)
        if record is not None:
            self._render_record(record)

    def _render_record(self, record: VMRecord) -> None:
        if self._detail_uuid != record.uuid:
            # Never show a previously highlighted VM's asynchronous read on this row.
            self._detail_uuid = record.uuid
            self._detail_loaded = None
            self._detail_status = None
        self._detail_record = record
        self._paint_detail()

    def _detail_view(self) -> RenderableType:
        if self._detail_record is None:
            return build_detail_placeholder("empty", self._palette)
        parts: list[RenderableType] = [
            build_vm_detail(
                self._detail_record,
                self._detail_loaded,
                self._palette,
                local_hostname=self._local_hostname,
                local_node_id=self._local_node_id,
                local_node_name=self._local_node_name,
            )
        ]
        if self._detail_status is not None:
            parts.append(build_detail_placeholder(self._detail_status, self._palette))
        return Group(*parts) if len(parts) > 1 else parts[0]

    def _paint_detail(self) -> None:
        try:
            box = self.query_one("#detail-box", Static)
        except NoMatches:
            return  # The screen is being torn down; a queued worker may still call this.
        box.update(self._detail_view())

    @work(thread=True, group="detail", exclusive=True)
    def _load_detail(self, uuid: str) -> None:
        session = self.session
        if session is None:
            self.call_from_thread(self._detail_failed, uuid)
            return
        try:
            section = self.application.detail(session.token, uuid)
            value = as_vm_detail(section)
        except Exception:
            self.call_from_thread(self._detail_failed, uuid)
            return
        self.call_from_thread(self._publish_detail, uuid, value)

    def _publish_detail(self, uuid: str, detail: VMDetail) -> None:
        if uuid != self._selected_uuid:
            return
        if detail.uuid != uuid:
            # A provider answer for another object is not evidence for this row.
            self._detail_failed(uuid)
            return
        self._detail_uuid = uuid
        self._detail_loaded = detail
        self._detail_status = None
        record = self._records.get(uuid)
        if record is not None:
            self._detail_record = record
            self._paint_detail()

    def _detail_failed(self, uuid: str) -> None:
        """Surface a failed detail read instead of leaving the pane silently unchanged."""
        if uuid != self._selected_uuid:
            return
        self._detail_uuid = uuid
        self._detail_loaded = None
        self._detail_status = "error"
        self._paint_detail()

    def action_details(self) -> None:
        uuid = self._selected_uuid
        if uuid not in self._table_order or self._detail_record is None:
            return
        if self._detail_status == "loading" and self._detail_uuid == uuid:
            return  # Enter is idempotent while a read for this row is in flight.
        self._detail_uuid = uuid
        self._detail_loaded = None
        self._detail_status = "loading"
        self._paint_detail()
        self._load_detail(uuid)

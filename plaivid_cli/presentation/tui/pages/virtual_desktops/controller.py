"""Textual presentation for the local PVM management application."""

from __future__ import annotations

import uuid as uuidlib

from textual import on, work
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Select,
    Static,
)

from plaivid_cli.application.operations import Admission
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    OperationPlan,
    OperationResult,
    SectionSnapshot,
)
from plaivid_cli.domain.models.tasks import TargetRef
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.tui.messages import OperationFinished


class DesktopMixin:
    """Desktop behavior for the composed Textual application."""

    def _render_desktops(self, section: SectionSnapshot[object] | None) -> None:
        if (
            section is None
            or section.generation <= self._desktop_min_generation
            or section.generation == self._desktop_generation
        ):
            return
        self._desktop_generation = section.generation
        self._desktop_section = section
        value = section.value if section.value is not None else section.last_good_value
        self._desktops = (
            {item.uuid: item for item in value if isinstance(item, VirtualDesktop)}
            if isinstance(value, tuple)
            else {}
        )
        quality = section.status.value.replace("_", " ").title()
        if section.error:
            quality += f" · {redact_text(section.error)}"
        if section.quality_issues:
            quality += f" · {len(section.quality_issues)} issue(s)"
        self.query_one("#desktop-quality", Static).update(quality)
        self.query_one("#desktop-quality", Static).styles.color = (
            self._palette.success
            if section.status is CollectionStatus.CURRENT
            else self._palette.warning
        )
        self.query_one("#desktop-count", Static).update(
            str(len(self._desktops)) if section.has_value else "—"
        )
        self._filter_desktops()

    @on(Input.Changed, "#desktop-search")
    def desktop_search_changed(self) -> None:
        self._filter_desktops()

    @on(Checkbox.Changed, "#desktop-all")
    def desktop_scope_changed(self) -> None:
        self._render_desktop_detail()

    def _filter_desktops(self) -> None:
        if not self.is_mounted(self.query_one("#desktop-table", DataTable)):
            return
        query = self.query_one("#desktop-search", Input).value.strip().casefold()
        records = sorted(
            (item for item in self._desktops.values() if query in item.name.casefold()),
            key=lambda item: (item.name.casefold(), item.uuid),
        )
        rows = {
            item.uuid: (
                redact_text(item.name),
                item.uuid[:8] + "…",
                redact_text(item.cluster_status or "N/A"),
                redact_text(item.os_type or "N/A"),
                str(item.vcpu) if item.vcpu is not None else "N/A",
            )
            for item in records
        }
        order = tuple(rows)
        table = self.query_one("#desktop-table", DataTable)
        if order != self._desktop_rows:
            table.clear(columns=False)
            for uuid, cells in rows.items():
                table.add_row(
                    self._check_cell(uuid in self._desktop_checked),
                    *(self._cell_text(index, cell) for index, cell in enumerate(cells)),
                    key=uuid,
                )
        else:
            for uuid, cells in rows.items():
                old = self._desktop_cells.get(uuid, ())
                for column, cell in enumerate(cells):
                    if column >= len(old) or cell != old[column]:
                        table.update_cell(
                            uuid,
                            self._desktop_columns[column + 1],
                            self._cell_text(column, cell),
                            update_width=True,
                        )
        self._desktop_rows, self._desktop_cells = order, rows
        if self._desktop_selected not in rows:
            self._desktop_selected = order[0] if order else None
        if self._desktop_selected:
            table.move_cursor(row=order.index(self._desktop_selected), animate=False)
        self._render_desktop_detail()

    @on(DataTable.RowHighlighted, "#desktop-table")
    def desktop_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._running or not self.is_mounted(event.data_table):
            return
        uuid = str(getattr(event.row_key, "value", event.row_key))
        if uuid in self._desktop_rows:
            self._desktop_selected = uuid
            self._render_desktop_detail()

    def _render_desktop_detail(self) -> None:
        if not self.is_mounted(self.query_one("#desktop-detail", Static)):
            return
        all_targets = self.query_one("#desktop-all", Checkbox).value
        uuids = (
            tuple(sorted(self._desktops))
            if all_targets
            else ((self._desktop_selected,) if self._desktop_selected else ())
        )
        checked = len(self._desktop_checked & set(self._desktops))
        scope = f"{'All unfiltered Desktops' if all_targets else 'Selected Desktop'} · {len(uuids)} target(s) · {checked} checked"
        self.query_one("#desktop-selected-label", Static).update(
            (self._desktop_selected or "—")[:8]
        )
        self.query_one("#desktop-scope", Static).update(scope)
        record = self._desktops.get(self._desktop_selected or "")
        if record is None or self._desktop_selected not in self._desktop_rows:
            detail = (
                "No matching Virtual Desktops."
                if self._desktop_section
                else "Waiting for Desktop discovery…"
            )
        else:
            detail = (
                f"{record.name} · {record.uuid}\n"
                f"Object enabled: {record.enabled or 'N/A'} · Local runtime: {record.local_status or 'N/A'}\n"
                f"Cluster runtime: {record.cluster_status or 'N/A'} · OS: {record.os_type or 'N/A'} {record.os_version or ''}\n"
                f"vCPU: {record.vcpu if record.vcpu is not None else 'N/A'} · RAM: N/A (raw size: {record.memory_size_raw or 'N/A'}, unit unverified)\n"
                f"Owner: N/A · Zone: N/A · Parent ID: {record.parent_id or 'N/A'}"
            )
        if all_targets:
            detail += "\nAll unfiltered target UUIDs: " + (", ".join(uuids) if uuids else "none")
        self.query_one("#desktop-detail", Static).update(redact_text(detail))

    @on(Select.Changed, "#desktop-actions")
    def desktop_action_requested(self, event: Select.Changed) -> None:
        if not isinstance(event.value, str):
            return
        action = Action(event.value)
        event.select.clear()
        if self.session is None:
            self._desktop_message("Sign in before submitting an operation.")
            return
        section = self._desktop_section
        self._desktop_checked.intersection_update(self._desktops)
        checked = tuple(sorted(self._desktop_checked))
        all_targets = self.query_one("#desktop-all", Checkbox).value
        if checked:
            targets = tuple(self._desktops[uuid] for uuid in checked)
            is_bulk = len(targets) > 1
        elif all_targets:
            targets = tuple(self._desktops[uuid] for uuid in sorted(self._desktops))
            is_bulk = True
        elif self._desktop_selected in self._desktop_rows:
            selected = self._desktops.get(self._desktop_selected or "")
            targets = (selected,) if selected else ()
            is_bulk = False
        else:
            targets = ()
            is_bulk = False
        if section is None:
            self._desktop_message("Refresh the Desktop inventory before choosing an action.")
            return
        if not targets:
            self._desktop_message("Select one or more Desktops first.")
            return
        try:
            plan = self.operations.create_desktop_plan(
                action, targets, section, is_bulk=is_bulk
            )
        except AppError as exc:
            self._desktop_message(str(exc))
            return
        # Selecting the action is the operator's intent; no extra confirmation.
        refs = tuple(TargetRef(item.uuid, item.name or "", "desktop") for item in targets)
        operation_id = str(uuidlib.uuid4())
        if self.tasks.admit(action, refs, operation_id) is not Admission.ADMITTED:
            # The TaskManager listener already surfaced the refusal inline.
            return
        self.query_one("#logout", Button).disabled = True
        self.query_one("#desktop-actions", Select).disabled = True
        self._desktop_message(f"{action.value.upper()} submitted for {len(targets)} Desktop(s)…")
        self._execute_desktop(action, targets, section, plan, self._session_epoch, operation_id)

    def _desktop_message(self, message: str) -> None:
        self.query_one("#desktop-action-status", Static).update(redact_text(message))

    @work(thread=True, group="desktop-operation", exclusive=False)
    def _execute_desktop(
        self,
        action: Action,
        targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object],
        plan: OperationPlan,
        epoch: int,
        operation_id: str,
    ) -> None:
        session = self.session
        if session is None or epoch != self._session_epoch:
            self.tasks.abandon(operation_id, "session ended before dispatch")
            return
        self.tasks.start(operation_id)
        try:
            result = self.operations.execute_desktop(
                session.token,
                action,
                targets,
                section,
                is_bulk=plan.is_bulk,
                plan=plan,
                on_progress=lambda target_uuid, state: self.tasks.progress(
                    operation_id, target_uuid, state
                ),
            )
        except AppError as exc:
            self.tasks.abandon(operation_id, str(exc))
            settled = OperationFinished(operation_id, error=str(exc), page="desktops")
        except Exception as exc:  # noqa: BLE001 - never lose an admitted task
            detail = f"{type(exc).__name__}: operation failed"
            self.tasks.abandon(operation_id, detail)
            settled = OperationFinished(operation_id, error=detail, page="desktops")
        else:
            self.tasks.finish(operation_id, result)
            settled = OperationFinished(operation_id, result=result, page="desktops")
        self.post_message(settled)

    def _desktop_result_text(self, result: OperationResult) -> str:
        """Long-form detail for the page status line (the board holds the rows)."""
        summary = "; ".join(f"{item.uuid}: {item.state.value}" for item in result.targets)
        return (
            f"{result.action.value.upper()} · {result.state.value} · "
            f"{result.message} · {summary}"
        )

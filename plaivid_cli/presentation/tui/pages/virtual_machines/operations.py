"""VM lifecycle-action admission, dispatch, and result presentation."""

from __future__ import annotations

import uuid as uuidlib

from textual import on, work
from textual.widgets import Button, Checkbox, Select, Static

from plaivid_cli.application.operations import Admission
from plaivid_cli.application.services import TargetSelection
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, OperationPlan, OperationResult, SectionSnapshot
from plaivid_cli.domain.models.tasks import TargetRef
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.tui.messages import OperationFinished


class VMOperationMixin:
    """Submit VM lifecycle operations through the application coordinator."""

    @on(Select.Changed, "#bulk-actions")
    def bulk_action_selected(self, event: Select.Changed) -> None:
        if not isinstance(event.value, str):
            return  # blank / no-selection sentinel
        action = Action(event.value)
        # Reset the dropdown so the same action can be chosen again later.
        event.select.clear()
        self._begin_action(action)

    def _begin_action(self, action: Action) -> None:
        section = self._inventory_section
        inventory = self._inventory
        if section is None or inventory is None:
            self._show_error("No inventory available. Refresh before operating a VM.")
            return
        self._vm_checked.intersection_update(self._records)
        checked = tuple(sorted(self._vm_checked))
        if checked:
            selectors = checked
        elif self.query_one("#select-all", Checkbox).value:
            selectors = ("all",)
        elif self._selected_uuid in self._table_order:
            selectors = (self._selected_uuid,)
        else:
            self._show_error("Select one or more VMs first.")
            return
        try:
            selection = self.application.resolve_targets(inventory, selectors)
        except AppError as exc:
            self._show_error(str(exc))
            return
        try:
            plan = self.operations.create_plan(
                action, selection.records, section, is_bulk=selection.is_bulk
            )
        except AppError as exc:
            self._show_error(str(exc))
            return
        self._launch_operation(action, selection, section, plan)

    def _launch_operation(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        plan: OperationPlan,
    ) -> None:
        """Admit the request per target, then dispatch it in a worker thread.

        Admission is synchronous on the UI thread: an exact duplicate is
        ignored, a conflicting action on a claimed target is refused, and one
        mutation group at a time is enforced by the task board.
        """
        refs = tuple(
            TargetRef(record.uuid, record.name or "") for record in selection.records
        )
        operation_id = str(uuidlib.uuid4())
        decision = self.tasks.admit(action, refs, operation_id)
        if decision is not Admission.ADMITTED:
            # The refused message has already been published through the
            # TaskManager listener, which shows it inline; nothing is dispatched.
            return
        self.query_one("#bulk-actions", Select).disabled = True
        self.query_one("#logout", Button).disabled = True
        self._execute_action(action, selection, section, plan, operation_id)

    @work(thread=True, group="operation", exclusive=False)
    def _execute_action(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        plan: OperationPlan,
        operation_id: str,
    ) -> None:
        session = self.session
        if session is None:
            self.tasks.abandon(operation_id, "sign in before submitting an operation")
            return
        self.tasks.start(operation_id)
        try:
            result = self.operations.execute(
                session.token,
                action,
                selection.records,
                section,
                is_bulk=selection.is_bulk,
                plan=plan,
                on_progress=lambda target_uuid, state: self.tasks.progress(
                    operation_id, target_uuid, state
                ),
            )
        except AppError as exc:
            self.tasks.abandon(operation_id, str(exc))
            settled = OperationFinished(operation_id, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - never lose an admitted task
            self.tasks.abandon(operation_id, f"{type(exc).__name__}: operation failed")
            settled = OperationFinished(
                operation_id, error=f"{type(exc).__name__}: operation failed"
            )
        else:
            self.tasks.finish(operation_id, result)
            settled = OperationFinished(operation_id, result=result)
        # post_message is thread-safe and returns False once the app is
        # closing, so a late completion is a no-op instead of a traceback.
        self.post_message(settled)

    def _show_operation(self, result: OperationResult) -> None:
        self.query_one("#action-status", Static).update(
            redact_text(f"{result.action.value.upper()} · {result.state.value} · {result.message}")
        )

    def _show_error(self, message: str) -> None:
        self.query_one("#action-status", Static).update(redact_text(message))

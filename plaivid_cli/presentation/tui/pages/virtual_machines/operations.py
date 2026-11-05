"""VM lifecycle-action admission, dispatch, and result presentation."""

from __future__ import annotations

from textual import on, work
from textual.widgets import Button, Checkbox, Select, Static

from plaivid_cli.application.services import TargetSelection
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, OperationPlan, OperationResult, SectionSnapshot
from plaivid_cli.domain.redaction import redact_text


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
        if self._operation_active:
            self._show_error("An operation is already in progress.")
            return
        section = self._inventory_section
        inventory = self._inventory
        if section is None or inventory is None:
            self._show_error("No inventory available. Refresh before operating a VM.")
            return
        if self.query_one("#select-all", Checkbox).value:
            selectors = ("all",)
        elif self._selected_uuid in self._table_order:
            selectors = (self._selected_uuid,)
        else:
            self._show_error("Select a VM row first.")
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
        if self._operation_active:
            self._show_error("An operation is already in progress.")
            return
        self._operation_active = True
        self.query_one("#bulk-actions", Select).disabled = True
        self.query_one("#logout", Button).disabled = True
        self._execute_action(action, selection, section, plan)

    @work(thread=True, group="operation", exclusive=False)
    def _execute_action(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        plan: OperationPlan,
    ) -> None:
        try:
            session = self.session
            if session is None:
                self.call_from_thread(self._show_error, "Sign in before submitting an operation.")
                return
            try:
                result = self.operations.execute(
                    session.token,
                    action,
                    selection.records,
                    section,
                    is_bulk=selection.is_bulk,
                    plan=plan,
                )
            except AppError as exc:
                self.call_from_thread(self._show_error, str(exc))
                self.call_from_thread(self._request_refresh)
                return
            self.call_from_thread(self._show_operation, result)
            self.call_from_thread(self._request_refresh)
        finally:
            try:
                self.call_from_thread(self._operation_finished)
            except RuntimeError:
                # Textual may already be shutting down; Runtime.close still
                # waits for the application-owned operation lane to finish.
                pass

    def _operation_finished(self) -> None:
        self._operation_active = False
        self.query_one("#bulk-actions", Select).disabled = False
        self.query_one("#logout", Button).disabled = False

    def _show_operation(self, result: OperationResult) -> None:
        self.query_one("#action-status", Static).update(
            redact_text(f"{result.action.value.upper()} · {result.state.value} · {result.message}")
        )

    def _show_error(self, message: str) -> None:
        self.query_one("#action-status", Static).update(redact_text(message))

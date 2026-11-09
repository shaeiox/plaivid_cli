"""Serialized lifecycle dispatch with inventory safeguards and uncertain outcomes."""

from __future__ import annotations

import threading
import uuid as uuidlib
from collections.abc import Callable
from datetime import UTC, datetime

from plaivid_cli.application.collection import CollectionCoordinator, CollectionSuperseded
from plaivid_cli.application.ports import PvmGateway
from plaivid_cli.config import Settings
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    ErrorKind,
    OperationPlan,
    OperationResult,
    OperationState,
    SectionSnapshot,
    TargetOutcome,
    VMRecord,
)
from plaivid_cli.domain.redaction import redact_text

from .desktop_executor import DesktopOperationExecutor
from .planner import OperationPlanner
from .results import _aggregate_message, aggregate_state

#: Per-target progress callback: ``(target_uuid, state)``. The sink is notified
#: before and after each dispatch so a view can show live per-target status. A
#: sink exception is swallowed: presentation must never corrupt a mutation.
ProgressSink = Callable[[str, OperationState], None]


def _report(sink: ProgressSink | None, target_uuid: str, state: OperationState) -> None:
    if sink is None:
        return
    try:
        sink(target_uuid, state)
    except Exception:
        pass


class OperationCoordinator:
    """Own lifecycle dispatch serialization, barriers, and result accounting."""

    def create_plan(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        return self._planner.create_plan(action, targets, inventory, is_bulk=is_bulk)

    def create_desktop_plan(
        self,
        action: Action,
        targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        return self._planner.create_desktop_plan(action, targets, section, is_bulk=is_bulk)

    def __init__(
        self,
        provider: PvmGateway,
        collection: CollectionCoordinator,
        settings: Settings,
    ) -> None:
        self._provider = provider
        self._collection = collection
        self._settings = settings
        self._planner = OperationPlanner(collection, lambda: self._settings)
        self._lane = threading.Lock()
        self._closing = threading.Event()
        self._desktop_executor = DesktopOperationExecutor(
            collection, self._lane, self._closing, self.create_desktop_plan, self._dispatch_one
        )

    def close(self) -> None:
        """Stop new operation admission and wait for active dispatch/reconciliation."""
        self._closing.set()
        with self._lane:
            return

    def execute_desktop(
        self,
        token: str,
        action: Action,
        targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object],
        *,
        is_bulk: bool,
        plan: OperationPlan,
        on_progress: ProgressSink | None = None,
    ) -> OperationResult:
        return self._desktop_executor.execute(
            token,
            action,
            targets,
            section,
            is_bulk=is_bulk,
            plan=plan,
            on_progress=on_progress,
        )

    @staticmethod
    def cancel(plan: OperationPlan) -> OperationResult:
        """Record an explicit cancellation before any target was dispatched."""
        now = datetime.now(UTC)
        outcomes = tuple(
            TargetOutcome(
                target_uuid,
                OperationState.CANCELLED_BEFORE_DISPATCH,
                "cancelled before dispatch",
                dispatched=False,
            )
            for target_uuid in plan.target_uuids
        )
        return OperationResult(
            operation_id=str(uuidlib.uuid4()),
            action=plan.action,
            state=OperationState.CANCELLED_BEFORE_DISPATCH,
            targets=outcomes,
            started_at=now,
            finished_at=now,
            message="cancelled before dispatch; no PVM command was sent",
        )

    def execute(
        self,
        token: str,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
        plan: OperationPlan | None = None,
        on_progress: ProgressSink | None = None,
    ) -> OperationResult:
        if self._closing.is_set():
            raise AppError(ErrorKind.POLICY, "operation coordinator is shutting down")
        with self._lane:
            if self._closing.is_set():
                raise AppError(ErrorKind.POLICY, "operation coordinator is shutting down")
            return self._execute_locked(
                token,
                action,
                targets,
                inventory,
                is_bulk=is_bulk,
                plan=plan,
                on_progress=on_progress,
            )

    def _execute_locked(
        self,
        token: str,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
        plan: OperationPlan | None,
        on_progress: ProgressSink | None = None,
    ) -> OperationResult:
        current_plan = self.create_plan(action, targets, inventory, is_bulk=is_bulk)
        if plan is not None and (
            plan.action is not current_plan.action
            or plan.target_uuids != current_plan.target_uuids
            or plan.inventory_generation != current_plan.inventory_generation
            or plan.inventory_succeeded_at != current_plan.inventory_succeeded_at
            or plan.is_bulk != current_plan.is_bulk
            or plan.freshness_limit_seconds != current_plan.freshness_limit_seconds
        ):
            raise AppError(
                ErrorKind.POLICY, "operation plan is stale or does not match current targets"
            )
        plan = plan or current_plan
        target_ids = plan.target_uuids

        started = datetime.now(UTC)
        operation_id = str(uuidlib.uuid4())
        try:
            self._collection.begin_mutation(
                target_ids,
                expected_inventory_generation=plan.inventory_generation,
                max_age_seconds=plan.freshness_limit_seconds,
                require_complete_inventory=plan.is_bulk,
            )
        except CollectionSuperseded as exc:
            raise AppError(
                ErrorKind.POLICY,
                "inventory changed or expired immediately before dispatch; review a new plan",
                code="OPERATION_PLAN_STALE",
            ) from exc
        outcomes: list[TargetOutcome] = []
        stop_bulk = False
        try:
            for record in targets:
                if stop_bulk:
                    outcomes.append(
                        TargetOutcome(
                            record.uuid,
                            OperationState.NOT_STARTED,
                            "not dispatched after an earlier definite failure or unknown outcome",
                        )
                    )
                    _report(on_progress, record.uuid, OperationState.NOT_STARTED)
                    continue
                outcomes.append(self._dispatch_one(token, action, record, on_progress=on_progress))
                outcome = outcomes[-1]
                if outcome.state in {
                    OperationState.FAILED,
                    OperationState.REJECTED,
                    OperationState.OUTCOME_UNKNOWN,
                }:
                    stop_bulk = is_bulk
        finally:
            self._collection.end_mutation(target_ids)

        # Reconcile through the same serialized read lane. This records current
        # observations but does not promote command acceptance to completion.
        try:
            self._collection.collect_once(token, sections=("inventory",))
        except Exception:
            pass
        aggregate = aggregate_state(tuple(outcomes))
        return OperationResult(
            operation_id=operation_id,
            action=action,
            state=aggregate,
            targets=tuple(outcomes),
            started_at=started,
            finished_at=datetime.now(UTC),
            message=_aggregate_message(aggregate, outcomes),
        )

    def _dispatch_one(
        self,
        token: str,
        action: Action,
        record: VMRecord | VirtualDesktop,
        *,
        on_progress: ProgressSink | None = None,
    ) -> TargetOutcome:
        outcome = self._dispatch_outcome(token, action, record)
        _report(on_progress, record.uuid, outcome.state)
        return outcome

    def _dispatch_outcome(
        self, token: str, action: Action, record: VMRecord | VirtualDesktop
    ) -> TargetOutcome:
        try:
            reply = self._provider.dispatch_action(token, action, record.uuid)
        except AppError as exc:
            if exc.kind is ErrorKind.POLICY:
                return TargetOutcome(
                    record.uuid, OperationState.REJECTED, str(exc), dispatched=False
                )
            if exc.code == "PROCESS_START_FAILED":
                return TargetOutcome(record.uuid, OperationState.FAILED, str(exc), dispatched=False)
            return TargetOutcome(
                record.uuid, OperationState.OUTCOME_UNKNOWN, str(exc), dispatched=True
            )
        except Exception as exc:
            return TargetOutcome(
                record.uuid,
                OperationState.OUTCOME_UNKNOWN,
                f"{type(exc).__name__} after dispatch; outcome is unknown",
                dispatched=True,
            )
        # Documented sbell/sabad envelope (docs/SBELL-SABAD.md section 3):
        # <status>success|failed</status>, and on failure <errno> and <what>.
        if reply.status == "success":
            return TargetOutcome(
                record.uuid,
                OperationState.SUCCEEDED,
                f"PVM accepted vm/{action.value}",
                dispatched=True,
            )
        if reply.status == "failed":
            code = f" (errno {reply.errno})" if reply.errno else ""
            detail = reply.message or "PVM rejected the command"
            return TargetOutcome(
                record.uuid,
                OperationState.FAILED,
                redact_text(f"PVM reported failure{code}: {detail}"),
                dispatched=True,
            )
        # Any other status is not part of the documented contract: stay uncertain.
        return TargetOutcome(
            record.uuid,
            OperationState.OUTCOME_UNKNOWN,
            "unexpected PVM status; reconcile independently and do not retry blindly",
            dispatched=True,
        )

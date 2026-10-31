"""Serialized lifecycle dispatch with explicit approval and uncertainty."""

from __future__ import annotations

import threading
import uuid as uuidlib
from datetime import UTC, datetime

from plaivid_cli.application.collection import CollectionCoordinator, CollectionSuperseded
from plaivid_cli.application.ports import PvmGateway
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    InventoryData,
    OperationApproval,
    OperationPlan,
    OperationResult,
    OperationState,
    SectionSnapshot,
    TargetOutcome,
    VMRecord,
)
from plaivid_cli.domain.policies import action_policy, bulk_may_dispatch
from plaivid_cli.domain.redaction import redact_text


class OperationCoordinator:
    """Owns lifecycle dispatch order, approval binding, and result accounting."""

    def __init__(
        self,
        provider: PvmGateway,
        collection: CollectionCoordinator,
        settings: Settings,
    ) -> None:
        self._provider = provider
        self._collection = collection
        self._settings = settings
        self._lane = threading.Lock()
        self._closing = threading.Event()

    def close(self) -> None:
        """Stop new operation admission and wait for active dispatch/reconciliation."""
        self._closing.set()
        with self._lane:
            return

    @staticmethod
    def confirmation_phrase(action: Action, targets: tuple[str, ...]) -> str:
        return f"{action.value.upper()} {','.join(targets)}"

    def create_plan(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        """Build an immutable, freshness-checked plan without dispatching."""
        return self._build_plan(action, targets, inventory, is_bulk=is_bulk)

    def _build_plan(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        target_ids = tuple(record.uuid for record in targets)
        if not target_ids or len(set(target_ids)) != len(target_ids):
            raise AppError(ErrorKind.POLICY, "operation targets must be non-empty and unique")
        if len(target_ids) > 1 and not is_bulk:
            raise AppError(ErrorKind.POLICY, "multiple targets must be declared as one bulk plan")
        current = self._collection.snapshot.section("inventory")
        if current is None or current.generation != inventory.generation:
            raise AppError(ErrorKind.POLICY, "inventory changed after target selection; refresh and retry")
        if not isinstance(inventory.value, InventoryData):
            raise AppError(ErrorKind.POLICY, "operation plan has no current inventory records")
        current_records = {record.uuid: record for record in inventory.value.records}
        if any(current_records.get(record.uuid) != record for record in targets):
            raise AppError(ErrorKind.POLICY, "operation targets do not exactly match current inventory records")
        object_section = self._collection.snapshot.section("objects")
        if (
            object_section is None
            or object_section.generation != inventory.generation
            or object_section.status is not CollectionStatus.CURRENT
            or object_section.value is None
            or object_section.succeeded_at is None
        ):
            raise AppError(ErrorKind.POLICY, "mutations require a current successful object inventory")
        max_age = self._settings.max_inventory_age_seconds
        if max_age is None:
            if is_bulk:
                raise AppError(
                    ErrorKind.POLICY,
                    "bulk operations are disabled until PLAIVID_MAX_INVENTORY_AGE_SECONDS is configured",
                )
            max_age = self._settings.refresh_interval * 2
        if not self._collection.is_fresh("objects", max_age_seconds=max_age):
            raise AppError(ErrorKind.POLICY, "object inventory is too old for a mutation; refresh and retry")
        if is_bulk and (
            inventory.status is not CollectionStatus.CURRENT
            or not self._collection.is_fresh("inventory", max_age_seconds=max_age)
        ):
            raise AppError(ErrorKind.POLICY, "bulk mutations require a complete current inventory")
        if any(record.state_disagreed or record.quality_issues for record in targets):
            raise AppError(ErrorKind.POLICY, "a selected VM has conflicting or incomplete state evidence")
        if is_bulk:
            complete = (
                inventory.status is CollectionStatus.CURRENT
                and not inventory.quality_issues
                and not any(record.state_disagreed for record in targets)
            )
            if not bulk_may_dispatch(
                action=action,
                is_bulk=True,
                complete=complete,
                fresh=True,
                max_age_seconds=self._settings.max_inventory_age_seconds,
            ):
                raise AppError(ErrorKind.POLICY, "bulk operation lacks complete fresh inventory evidence")
        return OperationPlan(
            action=action,
            target_uuids=target_ids,
            inventory_generation=inventory.generation,
            inventory_succeeded_at=object_section.succeeded_at,
            is_bulk=is_bulk,
            freshness_limit_seconds=max_age,
            created_at=datetime.now(UTC),
            confirmation=self.confirmation_phrase(action, target_ids),
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

    def approve(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        confirmation: str | None = None,
        interactive_confirmed: bool = False,
    ) -> OperationApproval:
        target_uuids = tuple(record.uuid for record in targets)
        if not target_uuids:
            raise AppError(ErrorKind.POLICY, "cannot approve an empty target set")
        expected = self.confirmation_phrase(action, target_uuids)
        if not interactive_confirmed and confirmation != expected:
            raise AppError(
                ErrorKind.POLICY,
                f"approval must exactly match: {expected}",
                code="APPROVAL_MISMATCH",
            )
        return OperationApproval(
            action=action,
            target_uuids=target_uuids,
            inventory_generation=inventory.generation,
            issued_at=datetime.now(UTC),
            confirmation=expected,
        )

    def execute(
        self,
        token: str,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
        approval: OperationApproval | None = None,
        plan: OperationPlan | None = None,
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
                approval=approval,
                plan=plan,
            )

    def _execute_locked(
        self,
        token: str,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
        approval: OperationApproval | None,
        plan: OperationPlan | None,
    ) -> OperationResult:
        current_plan = self._build_plan(action, targets, inventory, is_bulk=is_bulk)
        if plan is not None and (
            plan.action is not current_plan.action
            or plan.target_uuids != current_plan.target_uuids
            or plan.inventory_generation != current_plan.inventory_generation
            or plan.inventory_succeeded_at != current_plan.inventory_succeeded_at
            or plan.is_bulk != current_plan.is_bulk
            or plan.freshness_limit_seconds != current_plan.freshness_limit_seconds
            or plan.confirmation != current_plan.confirmation
        ):
            raise AppError(ErrorKind.POLICY, "operation plan is stale or does not match current targets")
        plan = plan or current_plan
        target_ids = plan.target_uuids
        policy = action_policy(action)
        must_confirm = policy.confirm_single or (is_bulk and policy.confirm_bulk)
        if must_confirm:
            expected = self.confirmation_phrase(action, target_ids)
            if (
                approval is None
                or approval.action is not action
                or approval.target_uuids != target_ids
                or approval.inventory_generation != inventory.generation
                or approval.confirmation != expected
            ):
                raise AppError(
                    ErrorKind.POLICY,
                    f"operation requires approval bound to current inventory: {expected}",
                    code="APPROVAL_REQUIRED",
                )

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
                    continue
                outcomes.append(self._dispatch_one(token, action, record))
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

    def _dispatch_one(self, token: str, action: Action, record: VMRecord) -> TargetOutcome:
        try:
            reply = self._provider.dispatch_action(token, action, record.uuid)
        except AppError as exc:
            if exc.kind is ErrorKind.POLICY:
                return TargetOutcome(record.uuid, OperationState.REJECTED, str(exc), dispatched=False)
            if exc.code == "PROCESS_START_FAILED":
                return TargetOutcome(record.uuid, OperationState.FAILED, str(exc), dispatched=False)
            return TargetOutcome(record.uuid, OperationState.OUTCOME_UNKNOWN, str(exc), dispatched=True)
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


def aggregate_state(outcomes: tuple[TargetOutcome, ...]) -> OperationState:
    """Apply the documented precedence without hiding any uncertain target."""
    if not outcomes:
        return OperationState.FAILED
    states = {outcome.state for outcome in outcomes}
    if OperationState.OUTCOME_UNKNOWN in states:
        return OperationState.OUTCOME_UNKNOWN
    if OperationState.COMMAND_ACCEPTED_UNCONFIRMED in states:
        return OperationState.COMMAND_ACCEPTED_UNCONFIRMED
    succeeded = sum(outcome.state is OperationState.SUCCEEDED for outcome in outcomes)
    if succeeded == len(outcomes):
        return OperationState.SUCCEEDED
    if succeeded:
        return OperationState.PARTIAL
    if OperationState.FAILED in states:
        return OperationState.FAILED
    if states <= {OperationState.REJECTED, OperationState.NOT_STARTED}:
        return OperationState.REJECTED
    if states == {OperationState.CANCELLED_BEFORE_DISPATCH}:
        return OperationState.CANCELLED_BEFORE_DISPATCH
    if OperationState.NOT_STARTED in states:
        return OperationState.PARTIAL
    return OperationState.FAILED


def _aggregate_message(state: OperationState, outcomes: list[TargetOutcome]) -> str:
    counts: dict[OperationState, int] = {}
    for outcome in outcomes:
        counts[outcome.state] = counts.get(outcome.state, 0) + 1
    summary = ", ".join(f"{count} {key.value}" for key, count in counts.items())
    failure = next(
        (outcome.message for outcome in outcomes if outcome.state is OperationState.FAILED),
        None,
    )
    if failure:
        summary = f"{summary}; {failure}"
    if state is OperationState.OUTCOME_UNKNOWN:
        return f"{summary}; do not retry until reconciled"
    if state is OperationState.COMMAND_ACCEPTED_UNCONFIRMED:
        return f"{summary}; accepted commands are not proof of completion"
    return summary

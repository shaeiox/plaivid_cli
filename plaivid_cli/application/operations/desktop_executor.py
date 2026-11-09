"""Serialized execution workflow for virtual-desktop lifecycle actions."""

from __future__ import annotations

import threading
import uuid as uuidlib
from _thread import LockType
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from plaivid_cli.application.collection import CollectionCoordinator, CollectionSuperseded
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
)
from plaivid_cli.domain.policies import batch_stop_reason, outcome_stops_batch

from .results import _aggregate_message, aggregate_state


class PlanFactory(Protocol):
    def __call__(
        self,
        action: Action,
        targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan: ...


DispatchOne = Callable[..., TargetOutcome]

#: Per-target progress callback, identical to the VM path: ``(uuid, state)``.
ProgressSink = Callable[[str, OperationState], None]


def _report(sink: ProgressSink | None, target_uuid: str, state: OperationState) -> None:
    if sink is None:
        return
    try:
        sink(target_uuid, state)
    except Exception:
        pass


class DesktopOperationExecutor:
    """Run Desktop actions sequentially behind the shared lifecycle lane."""

    def __init__(
        self,
        collection: CollectionCoordinator,
        lane: LockType,
        closing: threading.Event,
        create_plan: PlanFactory,
        dispatch_one: DispatchOne,
    ) -> None:
        self._collection = collection
        self._lane = lane
        self._closing = closing
        self._create_plan = create_plan
        self._dispatch_one = dispatch_one

    def execute(
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
        if self._closing.is_set():
            raise AppError(ErrorKind.POLICY, "operation coordinator is shutting down")
        with self._lane:
            if self._closing.is_set():
                raise AppError(ErrorKind.POLICY, "operation coordinator is shutting down")
            current = self._create_plan(action, targets, section, is_bulk=is_bulk)
            if (
                plan.action is not current.action
                or plan.target_uuids != current.target_uuids
                or plan.inventory_generation != current.inventory_generation
                or plan.inventory_succeeded_at != current.inventory_succeeded_at
                or plan.is_bulk != current.is_bulk
                or plan.freshness_limit_seconds != current.freshness_limit_seconds
            ):
                raise AppError(ErrorKind.POLICY, "Desktop plan changed after review")
            try:
                self._collection.begin_mutation(
                    plan.target_uuids,
                    expected_desktop_generation=plan.inventory_generation,
                    max_age_seconds=plan.freshness_limit_seconds,
                    require_complete_inventory=True,
                )
            except CollectionSuperseded as exc:
                raise AppError(
                    ErrorKind.POLICY, "Desktop inventory changed before dispatch"
                ) from exc
            started = datetime.now(UTC)
            outcomes: list[TargetOutcome] = []
            stop_reason: str | None = None
            try:
                for item in targets:
                    if stop_reason is not None:
                        outcomes.append(
                            TargetOutcome(
                                item.uuid,
                                OperationState.NOT_STARTED,
                                f"not dispatched: {stop_reason}",
                            )
                        )
                        _report(on_progress, item.uuid, OperationState.NOT_STARTED)
                        continue
                    outcome = self._dispatch_one(token, action, item, on_progress=on_progress)
                    outcomes.append(outcome)
                    # Scoped continuation (ADR 0012) — identical policy to the VM
                    # path; the two loops must never diverge.
                    if is_bulk and outcome_stops_batch(outcome):
                        stop_reason = batch_stop_reason(outcome)
            finally:
                self._collection.end_mutation(plan.target_uuids, section_name="desktops")
            try:
                self._collection.collect_once(token, sections=("desktops",))
            except Exception:
                pass  # The result remains an accepted/uncertain command, not an observed transition.
            state = aggregate_state(tuple(outcomes))
            return OperationResult(
                operation_id=str(uuidlib.uuid4()),
                action=action,
                state=state,
                targets=tuple(outcomes),
                started_at=started,
                finished_at=datetime.now(UTC),
                message=_aggregate_message(state, outcomes),
            )

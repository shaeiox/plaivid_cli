"""Bounded-parallel execution workflow for virtual-desktop lifecycle actions."""

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
    SectionSnapshot,
    TargetOutcome,
)
from plaivid_cli.domain.policies import (
    DAEMON_OFFLINE_REASON,
    batch_stop_reason,
    outcome_stops_batch,
)

from .bulk_dispatch import execute_bounded_batch
from .results import ProgressSink, _aggregate_message, aggregate_state


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


class DesktopOperationExecutor:
    """Run Desktop batches in a bounded pool behind the shared lifecycle lane."""

    def __init__(
        self,
        collection: CollectionCoordinator,
        lane: LockType,
        closing: threading.Event,
        create_plan: PlanFactory,
        dispatch_one: DispatchOne,
        max_concurrency: int = 3,
    ) -> None:
        self._collection = collection
        self._lane = lane
        self._closing = closing
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._create_plan = create_plan
        self._dispatch_one = dispatch_one
        self._max_concurrency = max_concurrency

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
            try:
                outcomes = execute_bounded_batch(
                    targets,
                    lambda item: self._dispatch_one(
                        token, action, item, on_progress=on_progress
                    ),
                    max_concurrency=self._max_concurrency,
                    is_bulk=is_bulk,
                    must_stop=lambda outcome: outcome_stops_batch(
                        outcome, daemon_alive=outcome.code != "DAEMON_OFFLINE"
                    ),
                    stop_reason_for=lambda outcome: batch_stop_reason(
                        outcome, daemon_alive=outcome.code != "DAEMON_OFFLINE"
                    ),
                    on_progress=on_progress,
                )
            finally:
                self._collection.end_mutation(plan.target_uuids, section_name="desktops")
            stop_reason = (
                DAEMON_OFFLINE_REASON
                if any(outcome.code == "DAEMON_OFFLINE" for outcome in outcomes)
                else next(
                    (
                        batch_stop_reason(outcome)
                        for outcome in outcomes
                        if is_bulk and outcome_stops_batch(outcome)
                    ),
                    None,
                )
            )
            if stop_reason != DAEMON_OFFLINE_REASON:
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

"""Bounded rolling dispatch for one mutation batch.

The caller owns the operation-level mutation barrier. This module only schedules
per-target work inside that barrier and reports targets that were never started.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Protocol, TypeVar

from plaivid_cli.domain.models import OperationState, TargetOutcome
from plaivid_cli.domain.policies import DAEMON_OFFLINE_REASON

from .results import ProgressSink, report_progress


class HasUuid(Protocol):
    uuid: str


T = TypeVar("T", bound=HasUuid)


def execute_bounded_batch(
    targets: Sequence[T],
    dispatch: Callable[[T], TargetOutcome],
    *,
    max_concurrency: int,
    is_bulk: bool,
    must_stop: Callable[[TargetOutcome], bool],
    stop_reason_for: Callable[[TargetOutcome], str],
    on_progress: ProgressSink | None = None,
) -> tuple[TargetOutcome, ...]:
    """Dispatch a batch using a bounded rolling window.

    Results are returned in the original target order. A worker that observes a
    batch-stopping result raises a shared stop event immediately; the supervisor
    cancels work that has not started, waits for work already in flight, and
    records only undispatched targets as ``NOT_STARTED``.
    """
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be positive")
    if not targets:
        return ()

    target_ids = tuple(target.uuid for target in targets)
    target_order = {target_uuid: index for index, target_uuid in enumerate(target_ids)}
    if len(target_order) != len(target_ids):
        raise ValueError("bulk dispatch targets must have unique UUIDs")

    stop_event = threading.Event()
    stop_lock = threading.Lock()
    stop_reason: list[str | None] = [None]

    def request_stop(reason: str) -> None:
        with stop_lock:
            if stop_reason[0] is None or reason == DAEMON_OFFLINE_REASON:
                # A confirmed daemon outage supersedes an earlier session
                # diagnosis so skipped rows and reconciliation policy are exact.
                stop_reason[0] = reason
            stop_event.set()

    def current_stop_reason() -> str | None:
        with stop_lock:
            return stop_reason[0]

    def run_one(target: T) -> TargetOutcome:
        try:
            outcome = dispatch(target)
        except Exception as exc:  # noqa: BLE001 - keep worker failures in the result model
            outcome = TargetOutcome(
                uuid=target.uuid,
                state=OperationState.OUTCOME_UNKNOWN,
                message=f"{type(exc).__name__} in dispatch worker; outcome is unknown",
                dispatched=True,
                code="WORKER_FAILURE",
            )
            if is_bulk:
                request_stop("an earlier dispatch worker failed unexpectedly")
            return outcome
        if is_bulk:
            with stop_lock:
                if must_stop(outcome):
                    reason = stop_reason_for(outcome)
                    if stop_reason[0] is None or reason == DAEMON_OFFLINE_REASON:
                        stop_reason[0] = reason
                    stop_event.set()
        return outcome

    ordered_outcomes: dict[str, TargetOutcome] = {}
    next_index = 0
    future_targets: dict[Future[TargetOutcome], T] = {}
    worker_count = min(max_concurrency, len(targets))

    def fill_window(pool: ThreadPoolExecutor) -> None:
        nonlocal next_index
        while next_index < len(targets) and len(future_targets) < worker_count:
            # Submission and worker stop publication share a lock. Thus once a
            # worker publishes a stop event, no later future can enter the pool.
            with stop_lock:
                if stop_event.is_set():
                    return
                target = targets[next_index]
                next_index += 1
                future_targets[pool.submit(run_one, target)] = target

    with ThreadPoolExecutor(
        max_workers=worker_count, thread_name_prefix="plaivid-mutation"
    ) as pool:
        fill_window(pool)
        while future_targets:
            completed, _ = wait(tuple(future_targets), return_when=FIRST_COMPLETED)
            # Deterministic processing of simultaneous completions simplifies
            # stop-reason selection; final outcomes are ordered independently.
            completed_ordered = sorted(
                completed, key=lambda future: target_order[future_targets[future].uuid]
            )
            for future in completed_ordered:
                target = future_targets.pop(future)
                target_uuid = target.uuid
                try:
                    ordered_outcomes[target_uuid] = future.result()
                except Exception as exc:  # defensive: run_one normally captures this
                    outcome = TargetOutcome(
                        uuid=target_uuid,
                        state=OperationState.OUTCOME_UNKNOWN,
                        message=f"{type(exc).__name__} in dispatch worker; outcome is unknown",
                        dispatched=True,
                        code="WORKER_FAILURE",
                    )
                    ordered_outcomes[target_uuid] = outcome
                    if is_bulk:
                        request_stop("an earlier dispatch worker failed unexpectedly")

            if stop_event.is_set():
                reason = current_stop_reason() or "bulk dispatch stopped"
                for future, target in tuple(future_targets.items()):
                    if future.cancel():
                        future_targets.pop(future)
                        message = (
                            reason
                            if reason == DAEMON_OFFLINE_REASON
                            else f"not dispatched: {reason}"
                        )
                        ordered_outcomes[target.uuid] = TargetOutcome(
                            target.uuid,
                            OperationState.NOT_STARTED,
                            message,
                        )
                # Do not submit additional targets. Running calls are allowed to
                # settle and retain their actual outcomes.
                continue
            fill_window(pool)

    reason = current_stop_reason()
    if is_bulk and reason is not None:
        for target in targets:
            if target.uuid not in ordered_outcomes:
                message = (
                    reason
                    if reason == DAEMON_OFFLINE_REASON
                    else f"not dispatched: {reason}"
                )
                ordered_outcomes[target.uuid] = TargetOutcome(
                    target.uuid,
                    OperationState.NOT_STARTED,
                    message,
                )

    outcomes: list[TargetOutcome] = []
    for target in targets:
        outcome = ordered_outcomes.get(target.uuid)
        if outcome is None:
            # This is only reachable for a non-bulk worker failure. Preserve an
            # explicit terminal state instead of leaving a task queued forever.
            outcome = TargetOutcome(
                target.uuid,
                OperationState.OUTCOME_UNKNOWN,
                "dispatch ended without a target outcome",
                dispatched=False,
                code="WORKER_FAILURE",
            )
        outcomes.append(outcome)
        if outcome.state is OperationState.NOT_STARTED:
            report_progress(on_progress, target.uuid, outcome.state, outcome.message)
    return tuple(outcomes)

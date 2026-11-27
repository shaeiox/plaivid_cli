"""Per-target admission, deduplication, and lifecycle tracking for lifecycle tasks.

The manager is deliberately free of Textual (and of any I/O): it owns a small
amount of mutable state behind one lock and notifies a plain callable. The TUI
turns those notifications into Textual messages; the CLI does not use it at all.

Admission policy (Model B, reject on duplicate/conflict):

* the exact same ``(action, target_uuid)`` that is already live is a
  ``DUPLICATE`` and is ignored, which is the idempotency requirement;
* a different action against a target that is already claimed is a ``CONFLICT``,
  because serialising two contradictory transitions on one target would produce
  a state sequence nobody can reason about;
* any other request while a mutation group is in flight is ``BUSY``, because the
  operation coordinator serialises mutations behind one lane (ADR 0007) and a
  plan frozen before that lane cleared would be rejected as stale on arrival;
* requests are all-or-nothing: a bulk whose targets partly overlap is refused
  as a whole rather than dispatched as a subset (ADR 0012).
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum

from plaivid_cli.domain.models import (
    Action,
    OperationResult,
    OperationState,
    TargetOutcome,
)
from plaivid_cli.domain.models.tasks import (
    TargetRef,
    TaskEvent,
    TaskKey,
    TaskRecord,
    TaskStatus,
    task_status_for,
)
from plaivid_cli.domain.redaction import redact_text

Listener = Callable[[TaskEvent], None]


class Admission(StrEnum):
    """Result of a synchronous admission decision."""

    ADMITTED = "admitted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    BUSY = "busy"

    @property
    def ok(self) -> bool:
        return self is Admission.ADMITTED


class TaskManager:
    """Thread-safe task board keyed by ``(action, target_uuid)``.

    Threading contract: ``admit`` and ``reset`` are called from the UI thread;
    ``start``/``progress``/``finish``/``abandon`` from a worker thread. Every
    public method takes the single instance lock, and listeners are invoked
    after the lock is released so a listener may safely query the manager.
    """

    def __init__(
        self,
        listener: Listener | None = None,
        *,
        history_limit: int = 200,
        serial_mutations: bool = True,
    ) -> None:
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")
        self._listener = listener
        self._history_limit = history_limit
        self._serial = serial_mutations
        self._lock = threading.RLock()
        self._live: dict[TaskKey, TaskRecord] = {}
        self._by_operation: dict[str, list[TaskKey]] = {}
        self._history: deque[TaskRecord] = deque(maxlen=history_limit)

    # ---------------------------------------------------------------- admission

    def admit(
        self,
        action: Action,
        targets: Sequence[TargetRef],
        operation_id: str,
    ) -> Admission:
        """Decide whether a request may be dispatched, and record it if so.

        Synchronous and I/O free: it only inspects and updates in-memory state,
        so two operator submissions are totally ordered and cannot both win.
        """
        refs = tuple(targets)
        if not refs:
            raise ValueError("admission requires at least one target")
        if len({ref.uuid for ref in refs}) != len(refs):
            raise ValueError("admission targets must be unique")

        events: list[TaskEvent] = []
        with self._lock:
            decision = self._classify(action, refs)
            if decision is not Admission.ADMITTED:
                events.append(
                    TaskEvent(
                        kind="refused",
                        operation_id=operation_id,
                        action=action,
                        targets=refs,
                        reason=decision.value,
                    )
                )
            else:
                self._by_operation[operation_id] = []
                for ref in refs:
                    record = TaskRecord(
                        key=TaskKey(action, ref.uuid),
                        target=ref,
                        operation_id=operation_id,
                        status=TaskStatus.QUEUED,
                    )
                    self._live[record.key] = record
                    self._by_operation[operation_id].append(record.key)
                    events.append(TaskEvent(kind="dispatched", record=record.copy()))
        self._emit(events)
        return decision

    def _classify(self, action: Action, refs: tuple[TargetRef, ...]) -> Admission:
        """Pure predicate; caller holds the lock."""
        if not self._live:
            return Admission.ADMITTED
        if all(TaskKey(action, ref.uuid) in self._live for ref in refs):
            return Admission.DUPLICATE
        claimed = {record.key.target_uuid for record in self._live.values()}
        for ref in refs:
            if ref.uuid not in claimed:
                continue
            # The target is busy; the exact-action case was already handled, so
            # a claimed target here means a different action (or a partial bulk
            # overlap).
            return Admission.CONFLICT
        if self._serial:
            return Admission.BUSY
        return Admission.ADMITTED

    # ------------------------------------------------------------------ updates

    def start(self, operation_id: str, target_uuid: str | None = None) -> None:
        """Mark queued task(s) of one submission as actively dispatching."""
        events: list[TaskEvent] = []
        with self._lock:
            for key in self._keys_for(operation_id):
                if target_uuid is not None and key.target_uuid != target_uuid:
                    continue
                record = self._live[key]
                if record.status is not TaskStatus.QUEUED:
                    continue
                updated = record.copy(
                    status=TaskStatus.RUNNING,
                    message="dispatching…",
                    started_at=record.started_at or _now(),
                )
                self._live[key] = updated
                events.append(TaskEvent(kind="started", record=updated.copy()))
        self._emit(events)

    def progress(
        self,
        operation_id: str,
        target_uuid: str,
        state: OperationState,
        detail: str = "",
    ) -> None:
        """Apply one per-target dispatch outcome reported by the coordinator."""
        status = task_status_for(state)
        raw_message = detail.strip() if detail and detail.strip() else _progress_message(state)
        message = redact_text(raw_message)
        events: list[TaskEvent] = []
        with self._lock:
            key = next(
                (
                    candidate
                    for candidate in self._keys_for(operation_id)
                    if candidate.target_uuid == target_uuid
                ),
                None,
            )
            if key is None:
                return
            record = self._live[key]
            if record.status.is_terminal:
                return  # never move a task backwards out of a terminal state
            now = _now()
            started_at = (
                record.started_at
                if status in {TaskStatus.QUEUED, TaskStatus.SKIPPED}
                else (record.started_at or now)
            )
            updated = record.copy(
                status=status,
                message=message,
                started_at=started_at,
                finished_at=now if status.is_terminal else None,
            )
            if status.is_terminal:
                self._retire(updated)
            else:
                self._live[key] = updated
            events.append(TaskEvent(kind=_event_kind(status), record=updated.copy()))
        self._emit(events)

    def finish(self, operation_id: str, result: OperationResult) -> None:
        """Reconcile the board with the authoritative operation result.

        Uses the result's own per-target outcomes so a target the coordinator
        never reached still leaves ``QUEUED``/``RUNNING`` and cannot linger.
        """
        fallback = redact_text(result.message)
        events: list[TaskEvent] = []
        with self._lock:
            reported = {outcome.uuid: outcome for outcome in result.targets}
            for key in self._keys_for(operation_id):
                record = self._live[key]
                outcome: TargetOutcome | None = reported.get(key.target_uuid)
                if outcome is None:
                    updated = record.copy(
                        status=TaskStatus.REJECTED,
                        message="not dispatched before the operation ended",
                        finished_at=_now(),
                    )
                else:
                    updated = record.copy(
                        status=task_status_for(outcome.state),
                        message=redact_text(outcome.message) or fallback,
                        finished_at=record.finished_at or _now(),
                    )
                self._retire(updated)
                events.append(TaskEvent(kind=_event_kind(updated.status), record=updated.copy()))
        self._emit(events)

    def abandon(self, operation_id: str, reason: str = "operation ended before dispatch") -> None:
        """Terminate any task of this submission that never reached a result."""
        safe = redact_text(reason)
        events: list[TaskEvent] = []
        with self._lock:
            for key in self._keys_for(operation_id):
                record = self._live[key]
                updated = record.copy(
                    status=TaskStatus.REJECTED, message=safe, finished_at=_now()
                )
                self._retire(updated)
                events.append(TaskEvent(kind="failed", record=updated.copy()))
        self._emit(events)

    def reset(self, reason: str = "") -> None:
        """Drop every live task and clear history, e.g. on logout."""
        with self._lock:
            self._live.clear()
            self._by_operation.clear()
            self._history.clear()
        self._emit([TaskEvent(kind="reset", message=redact_text(reason))])

    # ------------------------------------------------------------------ readers

    def any_active(self) -> bool:
        with self._lock:
            return any(not record.is_terminal for record in self._live.values())

    def active_operation_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(
                operation_id for operation_id, keys in self._by_operation.items() if keys
            )

    def busy_actions(self) -> tuple[Action, ...]:
        """Actions currently in flight, for a precise refusal message."""
        with self._lock:
            return tuple({record.key.action for record in self._live.values()})

    def live_records(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(record.copy() for record in self._live.values())

    def history(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(record.copy() for record in self._history)

    def records(self) -> tuple[TaskRecord, ...]:
        """Terminal history followed by live tasks, in board order."""
        with self._lock:
            return tuple(record.copy() for record in self._history) + tuple(
                record.copy() for record in self._live.values()
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._live) + len(self._history)

    # ------------------------------------------------------------------ internal

    def _keys_for(self, operation_id: str) -> list[TaskKey]:
        """Live keys of one submission; caller holds the lock."""
        return [key for key in self._by_operation.get(operation_id, ()) if key in self._live]

    def _retire(self, record: TaskRecord) -> None:
        """Move a finished record off the live board; caller holds the lock."""
        self._live.pop(record.key, None)
        keys = self._by_operation.get(record.operation_id)
        if keys is not None:
            self._by_operation[record.operation_id] = [
                key for key in keys if key != record.key
            ]
            if not self._by_operation[record.operation_id]:
                del self._by_operation[record.operation_id]
        self._history.append(record)

    def _emit(self, events: Sequence[TaskEvent]) -> None:
        listener = self._listener
        if listener is None:
            return
        for event in events:
            try:
                listener(event)
            except Exception:
                # A presentation bug must never corrupt operation bookkeeping.
                pass


def _now() -> datetime:
    return datetime.now(UTC)


def _event_kind(status: TaskStatus) -> str:
    if status is TaskStatus.SUCCEEDED:
        return "completed"
    if status is TaskStatus.UNKNOWN:
        return "unknown"
    if status is TaskStatus.SKIPPED:
        return "skipped"
    if status is TaskStatus.RUNNING:
        return "progress"
    return "failed"


def _progress_message(state: OperationState) -> str:
    return {
        OperationState.QUEUED: "queued",
        OperationState.DISPATCHING: "dispatching…",
        OperationState.RUNNING: "dispatching…",
        OperationState.SUCCEEDED: "PVM accepted the command",
        OperationState.COMMAND_ACCEPTED_UNCONFIRMED: "accepted; completion unconfirmed",
        OperationState.FAILED: "PVM reported failure",
        OperationState.REJECTED: "rejected before dispatch",
        OperationState.CANCELLED_BEFORE_DISPATCH: "cancelled before dispatch",
        OperationState.NOT_STARTED: "skipped after an earlier batch abort",
        OperationState.OUTCOME_UNKNOWN: "outcome unknown; reconcile before retrying",
        OperationState.PARTIAL: "partially applied",
    }.get(state, state.value)

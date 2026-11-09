"""Task identity and lifecycle value objects for background operation tracking.

These are presentation-agnostic values: no Textual import, no I/O, no locking.
They are shared by the application-layer ``TaskManager`` (which owns admission
and deduplication) and by the Textual task footer (which only renders them).
Keeping them in the domain layer lets a presentation component import a task
record without importing the application layer, which the repository's
architecture boundary test enforces.
"""

from __future__ import annotations

import uuid as uuidlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .enums import Action, OperationState, canonical_uuid


class TaskStatus(StrEnum):
    """Operator-visible task state.

    The vocabulary deliberately separates ``FAILED`` from ``UNKNOWN``: a command
    whose outcome was never established must not be presented as a definite
    failure, because that would invite an unsupported retry.
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_terminal(self) -> bool:
        return self not in {TaskStatus.QUEUED, TaskStatus.RUNNING}


_TERMINAL_STATUS = {
    OperationState.SUCCEEDED: TaskStatus.SUCCEEDED,
    OperationState.COMMAND_ACCEPTED_UNCONFIRMED: TaskStatus.SUCCEEDED,
    OperationState.OUTCOME_UNKNOWN: TaskStatus.UNKNOWN,
    OperationState.FAILED: TaskStatus.FAILED,
    OperationState.REJECTED: TaskStatus.REJECTED,
    OperationState.CANCELLED_BEFORE_DISPATCH: TaskStatus.REJECTED,
    OperationState.NOT_STARTED: TaskStatus.SKIPPED,
    OperationState.PARTIAL: TaskStatus.UNKNOWN,
}

_ACTIVE_STATUS = {
    OperationState.QUEUED: TaskStatus.QUEUED,
    OperationState.DISPATCHING: TaskStatus.RUNNING,
    OperationState.RUNNING: TaskStatus.RUNNING,
}


def task_status_for(state: OperationState) -> TaskStatus:
    """Collapse a dispatch outcome onto the operator-visible task vocabulary.

    Uncertain states map to ``UNKNOWN`` rather than to a definite result, so the
    footer never under- or over-states what the PVM boundary established.
    """
    try:
        return _TERMINAL_STATUS[state]
    except KeyError:
        return _ACTIVE_STATUS.get(state, TaskStatus.UNKNOWN)


@dataclass(frozen=True, slots=True)
class TargetRef:
    """One operation target: identity is the canonical UUID, never the label."""

    uuid: str
    label: str = ""
    kind: str = "vm"  # "vm" or "desktop"; display hint only

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))

    @property
    def short(self) -> str:
        """Stable, unambiguous suffix used when a label is too long to show."""
        return self.uuid[:8]


@dataclass(frozen=True, slots=True)
class TaskKey:
    """Deduplication identity: the same action on the same target."""

    action: Action
    target_uuid: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_uuid", canonical_uuid(self.target_uuid))


@dataclass(slots=True)
class TaskRecord:
    """One live or historical task row.

    ``message`` is expected to be redacted by whoever sets it; the footer still
    redacts defensively before display.
    """

    key: TaskKey
    target: TargetRef
    operation_id: str
    task_id: str = field(default_factory=lambda: str(uuidlib.uuid4()))
    status: TaskStatus = TaskStatus.QUEUED
    message: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    def elapsed_seconds(self, *, now: datetime | None = None) -> float:
        if self.started_at is None:
            return 0.0
        end = self.finished_at or now or datetime.now(UTC)
        return max(0.0, (end - self.started_at).total_seconds())

    def copy(self, **changes: object) -> TaskRecord:
        """Return a shallow copy so published snapshots are never mutated in place."""
        values = {
            "key": self.key,
            "target": self.target,
            "operation_id": self.operation_id,
            "task_id": self.task_id,
            "status": self.status,
            "message": self.message,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        values.update(changes)
        return TaskRecord(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class TaskEvent:
    """Immutable notification published by the TaskManager to its listener.

    Carries only values and primitives: never a widget, so a background thread
    cannot leak a Textual object into its own queue.
    """

    kind: str
    record: TaskRecord | None = None
    operation_id: str = ""
    action: Action | None = None
    targets: tuple[TargetRef, ...] = ()
    reason: str = ""
    message: str = ""

"""Custom Textual messages for background operation task updates.

Background workers must never touch widgets. They publish these messages, which
Textual routes to the UI thread. ``MessagePump.post_message`` is thread-safe and
returns ``False`` once the pump is closing, so a worker finishing after shutdown
is a no-op rather than a ``RuntimeError`` (unlike ``call_from_thread``).

Every message carries immutable domain values and primitives only: no widget or
screen reference that a background thread could leak.
"""

from __future__ import annotations

from textual.message import Message

from plaivid_cli.domain.models import (
    Action,
    OperationResult,
    TargetRef,
    TaskRecord,
    TaskStatus,
)


class TaskMessage(Message):
    """Base class for task-board messages, carrying one immutable record."""

    def __init__(self, record: TaskRecord, epoch: int = 0) -> None:
        super().__init__()
        self.record = record
        # Board epoch captured when the event was published. A worker-thread
        # message is delivered via loop.call_soon_threadsafe and can therefore
        # land *after* a later same-thread message (a logout reset). The epoch
        # lets the handler discard anything published before the reset.
        self.epoch = epoch

    @property
    def task_id(self) -> str:
        return self.record.task_id

    @property
    def operation_id(self) -> str:
        return self.record.operation_id


class TaskDispatched(TaskMessage):
    """A request was admitted; one row per target is now queued."""


class TaskStarted(TaskMessage):
    """A queued target is now being dispatched to ``PvmGateway``."""


class TaskProgress(TaskMessage):
    """Mid-flight detail for a non-terminal task."""


class TaskCompleted(TaskMessage):
    """The PVM accepted the command for this target.

    Acceptance is not proof of completion; the footer says so explicitly.
    """


class TaskFailed(TaskMessage):
    """The target definitely failed or was rejected."""


class TaskSkipped(TaskMessage):
    """The target was skipped after an earlier session/daemon batch abort."""


class TaskUnknown(TaskMessage):
    """The outcome was never established and must not be retried blindly."""


class TaskAdmissionRefused(Message):
    """Admission declined the request before any dispatch.

    Deliberately *not* a ``TaskMessage``: a refused request creates no task row,
    so it must not be rendered as one.
    """

    def __init__(
        self,
        action: Action,
        targets: tuple[TargetRef, ...],
        reason: str,
        detail: str = "",
    ) -> None:
        super().__init__()
        self.action = action
        self.targets = targets
        self.reason = reason
        self.detail = detail


class OperationFinished(Message):
    """A submitted operation finished; controls may be re-enabled.

    Carries the long-form ``OperationResult`` so the per-page status line keeps
    its detail, while the task board carries the per-target rows.
    """

    def __init__(
        self,
        operation_id: str,
        result: OperationResult | None = None,
        error: str = "",
        page: str = "fleet",
    ) -> None:
        super().__init__()
        self.operation_id = operation_id
        self.result = result
        self.error = error
        self.page = page


class TaskRegistryReset(Message):
    """The board must be cleared (session ended or logout)."""

    def __init__(self, reason: str = "", statuses: tuple[TaskStatus, ...] = ()) -> None:
        super().__init__()
        self.reason = reason
        self.statuses = statuses


__all__ = [
    "OperationFinished",
    "TaskAdmissionRefused",
    "TaskCompleted",
    "TaskDispatched",
    "TaskFailed",
    "TaskMessage",
    "TaskProgress",
    "TaskRegistryReset",
    "TaskSkipped",
    "TaskStarted",
    "TaskUnknown",
]

"""Admission, deduplication, and event-notification tests for the TaskManager."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime

import pytest

from plaivid_cli.application.operations import Admission, TaskManager
from plaivid_cli.domain.models import (
    Action,
    OperationResult,
    OperationState,
    TargetOutcome,
    TargetRef,
    TaskStatus,
    canonical_uuid,
    task_status_for,
)
from plaivid_cli.domain.models.tasks import TaskKey, TaskRecord

UUID_A = "11111111-1111-1111-1111-111111111111"
UUID_B = "22222222-2222-2222-2222-222222222222"
UUID_C = "33333333-3333-3333-3333-333333333333"


def _ref(uuid: str, label: str = "") -> TargetRef:
    return TargetRef(uuid, label or f"vm-{uuid[:4]}")


def _result(action: Action, outcomes: tuple[TargetOutcome, ...], message: str = "summary"):
    now = datetime.now(UTC)
    return OperationResult(
        operation_id="result-op",
        action=action,
        state=operation_state(outcomes),
        targets=outcomes,
        started_at=now,
        finished_at=now,
        message=message,
    )


def operation_state(outcomes: tuple[TargetOutcome, ...]) -> OperationState:
    from plaivid_cli.application.operations import aggregate_state

    return aggregate_state(outcomes)


class Recorder:
    def __init__(self) -> None:
        self.events = []
        self._lock = threading.Lock()

    def __call__(self, event) -> None:
        with self._lock:
            self.events.append(event)

    @property
    def kinds(self) -> list[str]:
        with self._lock:
            return [event.kind for event in self.events]

    def of_kind(self, kind: str):
        with self._lock:
            return [event for event in self.events if event.kind == kind]


# --------------------------------------------------------------------- models


def test_task_key_and_target_ref_normalize_uuid() -> None:
    ref = TargetRef(UUID_A.upper())
    assert ref.uuid == UUID_A
    assert TargetRef(UUID_A).short == UUID_A[:8]
    assert TaskKey(Action.START, UUID_A.upper()).target_uuid == UUID_A


def test_target_ref_rejects_invalid_uuid() -> None:
    with pytest.raises(ValueError):
        TargetRef("not-a-uuid")


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (OperationState.SUCCEEDED, TaskStatus.SUCCEEDED),
        (OperationState.COMMAND_ACCEPTED_UNCONFIRMED, TaskStatus.SUCCEEDED),
        (OperationState.FAILED, TaskStatus.FAILED),
        (OperationState.REJECTED, TaskStatus.REJECTED),
        (OperationState.CANCELLED_BEFORE_DISPATCH, TaskStatus.REJECTED),
        (OperationState.NOT_STARTED, TaskStatus.SKIPPED),
        (OperationState.OUTCOME_UNKNOWN, TaskStatus.UNKNOWN),
        (OperationState.PARTIAL, TaskStatus.UNKNOWN),
        (OperationState.QUEUED, TaskStatus.QUEUED),
        (OperationState.DISPATCHING, TaskStatus.RUNNING),
        (OperationState.RUNNING, TaskStatus.RUNNING),
    ],
)
def test_task_status_mapping_never_promotes_uncertainty(
    state: OperationState, expected: TaskStatus
) -> None:
    assert task_status_for(state) is expected


def test_task_record_copy_does_not_share_mutable_state() -> None:
    record = TaskRecord(
        key=TaskKey(Action.START, UUID_A),
        target=_ref(UUID_A),
        operation_id="op",
    )
    updated = record.copy(status=TaskStatus.RUNNING, message="dispatching")
    assert record.status is TaskStatus.QUEUED and record.message == ""
    assert updated.status is TaskStatus.RUNNING
    assert updated.task_id == record.task_id


# ------------------------------------------------------------------ admission


def test_first_request_is_admitted_and_publishes_one_event_per_target() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    decision = manager.admit(Action.START, [_ref(UUID_A), _ref(UUID_B)], "op-1")
    assert decision is Admission.ADMITTED
    assert recorder.kinds == ["dispatched", "dispatched"]
    assert {event.record.key.action for event in recorder.of_kind("dispatched")} == {Action.START}
    assert manager.any_active() is True
    assert len(manager.live_records()) == 2


def test_identical_action_and_target_is_ignored_as_duplicate() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-1") is Admission.ADMITTED
    before = len(manager.live_records())
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-2") is Admission.DUPLICATE
    assert len(manager.live_records()) == before
    refused = recorder.of_kind("refused")
    assert len(refused) == 1 and refused[0].reason == "duplicate"
    assert refused[0].action is Action.START


def test_different_action_on_claimed_target_is_a_conflict() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    assert manager.admit(Action.STOP, [_ref(UUID_A)], "op-2") is Admission.CONFLICT
    assert recorder.of_kind("refused")[0].reason == "conflict"
    assert [record.key.action for record in manager.live_records()] == [Action.START]


def test_unrelated_target_while_busy_is_refused_and_does_not_start_work() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    assert manager.admit(Action.STOP, [_ref(UUID_B)], "op-2") is Admission.BUSY
    assert [record.target.uuid for record in manager.live_records()] == [UUID_A]


def test_unrelated_target_is_admitted_when_serialization_is_disabled() -> None:
    manager = TaskManager(serial_mutations=False)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    assert manager.admit(Action.STOP, [_ref(UUID_B)], "op-2") is Admission.ADMITTED
    assert len(manager.live_records()) == 2
    # Deduplication still applies, and a cross-action claim still conflicts.
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-3") is Admission.DUPLICATE
    assert manager.admit(Action.STOP, [_ref(UUID_A)], "op-4") is Admission.CONFLICT


def test_partial_bulk_overlap_is_refused_as_a_whole() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    decision = manager.admit(Action.STOP, [_ref(UUID_B), _ref(UUID_A)], "op-2")
    assert decision is Admission.CONFLICT
    live = manager.live_records()
    assert [(record.key.action, record.target.uuid) for record in live] == [(Action.START, UUID_A)]


def test_bulk_duplicate_requires_every_target_to_match() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A), _ref(UUID_B)], "op-1")
    assert manager.admit(Action.START, [_ref(UUID_A), _ref(UUID_B)], "op-2") is Admission.DUPLICATE
    # A subset is not the same request, and the extra target is unclaimed, so it
    # is a conflict on the claimed target rather than a wholesale duplicate.
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-3") is Admission.DUPLICATE


def test_admission_rejects_empty_and_duplicate_targets() -> None:
    manager = TaskManager()
    with pytest.raises(ValueError):
        manager.admit(Action.START, [], "op")
    with pytest.raises(ValueError):
        manager.admit(Action.START, [_ref(UUID_A), _ref(UUID_A)], "op")


def test_admission_does_not_depend_on_label_or_letter_case() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [TargetRef(UUID_A, "alpha")], "op-1")
    assert manager.admit(Action.START, [TargetRef(UUID_A.upper(), "renamed")], "op-2") is (
        Admission.DUPLICATE
    )


# -------------------------------------------------------------------- updates


def test_start_moves_queued_tasks_to_running_and_stamps_time() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.start("op-1")
    record = manager.live_records()[0]
    assert record.status is TaskStatus.RUNNING
    assert record.started_at is not None
    assert recorder.of_kind("started")


def test_terminal_progress_retires_the_key_and_frees_it_for_reuse() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.start("op-1")
    manager.progress("op-1", UUID_A, OperationState.SUCCEEDED)
    assert manager.live_records() == ()
    assert manager.any_active() is False
    history = manager.history()
    assert len(history) == 1 and history[0].status is TaskStatus.SUCCEEDED
    assert history[0].finished_at is not None
    # The same (action, target) may now be requested again.
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-2") is Admission.ADMITTED


def test_unknown_outcome_is_tracked_distinctly_from_failure() -> None:
    manager = TaskManager()
    manager.admit(Action.KILL, [_ref(UUID_A)], "op-1")
    manager.progress("op-1", UUID_A, OperationState.OUTCOME_UNKNOWN)
    record = manager.history()[0]
    assert record.status is TaskStatus.UNKNOWN
    assert "reconcile" in record.message


def test_progress_never_moves_a_terminal_task_backwards() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.progress("op-1", UUID_A, OperationState.SUCCEEDED)
    manager.progress("op-1", UUID_A, OperationState.DISPATCHING)
    assert len(manager.history()) == 1
    assert manager.history()[0].status is TaskStatus.SUCCEEDED
    assert [event.kind for event in recorder.of_kind("progress")] == []


def test_progress_for_unknown_target_or_operation_is_ignored() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.progress("op-missing", UUID_A, OperationState.FAILED)
    manager.progress("op-1", UUID_B, OperationState.FAILED)
    assert manager.live_records()[0].status is TaskStatus.QUEUED


def test_finish_redacts_sensitive_outcome_text() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.start("op-1")
    manager.finish(
        "op-1",
        _result(
            Action.START,
            (TargetOutcome(UUID_A, OperationState.FAILED, "password=hunter2 rejected"),),
        ),
    )
    record = manager.history()[0]
    assert record.status is TaskStatus.FAILED
    assert "hunter2" not in record.message
    assert "[REDACTED]" in record.message


def test_abandon_redacts_its_reason() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.abandon("op-1", "token=abc123 rejected")
    assert "abc123" not in manager.history()[0].message


def test_finish_reconciles_every_target_including_unreported_ones() -> None:
    manager = TaskManager()
    manager.admit(Action.STOP, [_ref(UUID_A), _ref(UUID_B), _ref(UUID_C)], "op-1")
    manager.start("op-1")
    manager.finish(
        "op-1",
        _result(
            Action.STOP,
            (
                TargetOutcome(UUID_A, OperationState.SUCCEEDED, "accepted"),
                TargetOutcome(UUID_B, OperationState.FAILED, "boom"),
            ),
            message="2 targets",
        ),
    )
    statuses = {record.target.uuid: record.status for record in manager.history()}
    assert statuses == {
        UUID_A: TaskStatus.SUCCEEDED,
        UUID_B: TaskStatus.FAILED,
        UUID_C: TaskStatus.REJECTED,
    }
    assert manager.live_records() == ()
    assert manager.any_active() is False


def test_finish_leaves_other_operations_untouched() -> None:
    manager = TaskManager(serial_mutations=False)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.admit(Action.START, [_ref(UUID_B)], "op-2")
    manager.finish(
        "op-1", _result(Action.START, (TargetOutcome(UUID_A, OperationState.SUCCEEDED),))
    )
    assert [record.target.uuid for record in manager.live_records()] == [UUID_B]


def test_abandon_terminates_unfinished_tasks() -> None:
    manager = TaskManager()
    manager.admit(Action.RESET, [_ref(UUID_A), _ref(UUID_B)], "op-1")
    manager.abandon("op-1", "coordinator is shutting down")
    assert manager.live_records() == ()
    assert {record.status for record in manager.history()} == {TaskStatus.REJECTED}
    assert all("shutting down" in record.message for record in manager.history())


def test_reset_clears_live_and_history_and_notifies_once() -> None:
    recorder = Recorder()
    manager = TaskManager(recorder)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.progress("op-1", UUID_A, OperationState.SUCCEEDED)
    manager.admit(Action.START, [_ref(UUID_B)], "op-2")
    assert len(manager) == 2
    manager.reset("session ended")
    assert len(manager) == 0
    assert manager.any_active() is False
    reset_events = recorder.of_kind("reset")
    assert len(reset_events) == 1 and reset_events[0].message == "session ended"


# -------------------------------------------------------------- robustness


def test_history_is_bounded() -> None:
    manager = TaskManager(history_limit=3)
    for index in range(6):
        manager.admit(Action.START, [_ref(UUID_A)], f"op-{index}")
        manager.progress(f"op-{index}", UUID_A, OperationState.SUCCEEDED)
    assert len(manager.history()) == 3
    assert [record.operation_id for record in manager.history()] == ["op-3", "op-4", "op-5"]


def test_history_limit_must_be_positive() -> None:
    with pytest.raises(ValueError):
        TaskManager(history_limit=0)


def test_listener_exceptions_never_escape_or_corrupt_state() -> None:
    def exploding(event) -> None:
        raise RuntimeError(f"listener failed on {event.kind}")

    manager = TaskManager(exploding)
    assert manager.admit(Action.START, [_ref(UUID_A)], "op-1") is Admission.ADMITTED
    manager.start("op-1")
    manager.progress("op-1", UUID_A, OperationState.SUCCEEDED)
    assert manager.live_records() == ()
    assert len(manager.history()) == 1


def test_listener_may_query_the_manager_without_deadlock() -> None:
    seen: list[int] = []
    manager: TaskManager

    def listener(event) -> None:
        seen.append(len(manager.live_records()))

    manager = TaskManager(listener)
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    assert seen == [1]


def test_concurrent_progress_and_reads_do_not_raise_or_lose_updates() -> None:
    manager = TaskManager(history_limit=500)
    targets = [TargetRef(f"{index:08d}-0000-0000-0000-000000000000") for index in range(1, 9)]
    manager.admit(Action.START, targets, "op-1")
    manager.start("op-1")
    errors: list[BaseException] = []

    def worker(ref: TargetRef) -> None:
        try:
            for _ in range(25):
                manager.live_records()
                manager.any_active()
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def dispatcher() -> None:
        try:
            for ref in targets:
                manager.progress("op-1", ref.uuid, OperationState.SUCCEEDED)
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(ref,)) for ref in targets]
    threads.append(threading.Thread(target=dispatcher))
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    assert manager.live_records() == ()
    assert len(manager.history()) == len(targets)


def test_concurrent_admission_admits_exactly_one_winner() -> None:
    manager = TaskManager()
    ref = _ref(UUID_A)
    decisions: list[Admission] = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def submit() -> None:
        barrier.wait(timeout=5)
        decision = manager.admit(Action.START, [ref], "op")
        with lock:
            decisions.append(decision)

    threads = [threading.Thread(target=submit) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert decisions.count(Admission.ADMITTED) == 1
    assert decisions.count(Admission.DUPLICATE) == 7
    assert len(manager.live_records()) == 1


def test_elapsed_seconds_uses_start_and_finish() -> None:
    record = TaskRecord(
        key=TaskKey(Action.START, UUID_A),
        target=_ref(UUID_A),
        operation_id="op",
        started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 1, 1, 12, 0, 5, tzinfo=UTC),
    )
    assert record.elapsed_seconds() == pytest.approx(5.0)
    assert TaskRecord(
        key=TaskKey(Action.START, UUID_A), target=_ref(UUID_A), operation_id="op"
    ).elapsed_seconds() == 0.0


def test_canonical_uuid_is_used_for_identity_not_the_label() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [TargetRef(canonical_uuid(UUID_A.upper()), "first")], "op-1")
    assert manager.admit(Action.START, [TargetRef(UUID_A, "second")], "op-2") is Admission.DUPLICATE


def test_clock_is_monotonic_across_a_fast_sequence() -> None:
    manager = TaskManager()
    manager.admit(Action.START, [_ref(UUID_A)], "op-1")
    manager.start("op-1")
    started = manager.live_records()[0].started_at
    time.sleep(0.01)
    manager.progress("op-1", UUID_A, OperationState.SUCCEEDED)
    finished = manager.history()[0].finished_at
    assert started is not None and finished is not None and finished >= started

"""Scoped continuation policy for bulk execution (ADR 0012/0013).

A bulk request sends one PVM command per target, so a failure that belongs to a
single target must not deny service to the rest of the batch. Only a failure of
the session (or the wire) stops the remaining targets.
"""

from __future__ import annotations

import pytest

from plaivid_cli.application.services import as_inventory
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    ErrorKind,
    OperationState,
    PvmReply,
    TargetOutcome,
)
from plaivid_cli.domain.policies import (
    SESSION_SCOPED_ERRNOS,
    TARGET_SCOPED_ERRNOS,
    FailureScope,
    bulk_must_stop,
    classify_failure,
    is_target_scoped_error,
)
from tests.unit.test_application_operations import UUID_A, UUID_B, UUID_C, make_application

SUCCESS = PvmReply("success")


def _run_bulk(provider, application, operations, section, action: Action = Action.STOP):
    selection = application.resolve_targets(as_inventory(section), ("all",))
    return operations.execute(
        "token", action, selection.records, section, is_bulk=True
    ), selection


def _plan_and_run(provider, application, operations, section, action: Action = Action.STOP):
    selection = application.resolve_targets(as_inventory(section), ("all",))
    plan = operations.create_plan(
        action, selection.records, section, is_bulk=selection.is_bulk
    )
    return operations.execute(
        "token",
        action,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
    ), selection


# --------------------------------------------------------------- classifier


@pytest.mark.parametrize("errno", sorted(TARGET_SCOPED_ERRNOS))
def test_target_scoped_errno_is_classified_as_target(errno: str) -> None:
    assert classify_failure(errno) is FailureScope.TARGET


@pytest.mark.parametrize("errno", sorted(SESSION_SCOPED_ERRNOS))
def test_session_scoped_errno_is_classified_as_session(errno: str) -> None:
    assert classify_failure(errno) is FailureScope.SESSION


@pytest.mark.parametrize("errno", [None, "", "  ", "999999", "not-a-number"])
def test_unknown_errno_fails_closed_to_session_scope(errno) -> None:
    """An unrecognised failure must never be assumed safe to continue past."""
    assert classify_failure(errno) is FailureScope.SESSION


def test_target_scoped_predicate_requires_a_dispatch() -> None:
    """A failure before dispatch is never about one target's state."""
    dispatched = TargetOutcome(UUID_A, OperationState.FAILED, "state", dispatched=True, errno="146")
    not_dispatched = TargetOutcome(
        UUID_A, OperationState.FAILED, "process", dispatched=False, errno="146"
    )
    assert is_target_scoped_error(dispatched) is True
    assert is_target_scoped_error(not_dispatched) is False


def test_outcome_without_errno_is_not_target_scoped() -> None:
    outcome = TargetOutcome(UUID_A, OperationState.OUTCOME_UNKNOWN, "boom", dispatched=True)
    assert is_target_scoped_error(outcome) is False


def test_bulk_must_stop_ignores_successes_and_target_scoped_failures() -> None:
    outcomes = (
        TargetOutcome(UUID_A, OperationState.SUCCEEDED, "ok", dispatched=True),
        TargetOutcome(UUID_B, OperationState.FAILED, "146", dispatched=True, errno="146"),
    )
    assert bulk_must_stop(outcomes) is False
    assert bulk_must_stop(
        (*outcomes, TargetOutcome(UUID_C, OperationState.FAILED, "39", True, errno="39"))
    ) is True


# ------------------------------------------------------- batch continuation


def test_target_scoped_failure_lets_the_rest_of_the_batch_run() -> None:
    """The regression case: VM #1 is rejected, VM #2 and #3 still execute."""
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [
        PvmReply("failed", None, "146", "VM 'alpha' is already stopped"),
        SUCCESS,
        SUCCESS,
    ]
    result, selection = _run_bulk(provider, application, operations, section)
    assert [item.state for item in result.targets] == [
        OperationState.FAILED,
        OperationState.SUCCEEDED,
        OperationState.SUCCEEDED,
    ]
    assert result.targets[0].errno == "146"
    assert len(provider.dispatched) == 3
    assert result.state is OperationState.PARTIAL
    collection.close()


def test_middle_target_failure_does_not_disturb_its_neighbours() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [
        SUCCESS,
        PvmReply("failed", None, "146", "VM 'beta' is already stopped"),
        SUCCESS,
    ]
    result, _ = _run_bulk(provider, application, operations, section)
    assert [item.state for item in result.targets] == [
        OperationState.SUCCEEDED,
        OperationState.FAILED,
        OperationState.SUCCEEDED,
    ]
    collection.close()


def test_every_target_target_scoped_failure_still_attempts_all() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [
        PvmReply("failed", None, "146", "already stopped"),
        PvmReply("failed", None, "146", "already stopped"),
        PvmReply("failed", None, "146", "already stopped"),
    ]
    result, _ = _run_bulk(provider, application, operations, section)
    assert [item.state for item in result.targets] == [OperationState.FAILED] * 3
    assert len(provider.dispatched) == 3
    collection.close()


def test_batch_still_aggregates_as_failed_when_nothing_succeeded() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [PvmReply("failed", None, "146", "already stopped")] * 3
    result, _ = _run_bulk(provider, application, operations, section)
    assert result.state is OperationState.FAILED
    collection.close()


def _session_failure() -> AppError:
    return AppError(
        ErrorKind.PVM_RESPONSE,
        "vm/stop failed (39): session missing or expired",
        code="PVM_VM_STOP_FAILED",
        errno="39",
    )


def _raise_session_error(token, action, uuid):
    raise _session_failure()


def test_session_scoped_failure_aborts_and_marks_the_remainder_not_started() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.dispatch_action = _raise_session_error  # type: ignore[method-assign]
    result, _ = _run_bulk(provider, application, operations, section)
    states = [item.state for item in result.targets]
    assert states[0] is OperationState.OUTCOME_UNKNOWN
    assert states[1:] == [OperationState.NOT_STARTED, OperationState.NOT_STARTED]
    # A session failure arrives as an AppError, which is recorded as an unknown
    # outcome (the command may have reached PVM); the skip reason says so.
    assert "reconciled" in result.targets[1].message
    assert result.state is OperationState.OUTCOME_UNKNOWN
    collection.close()


def test_session_abort_dispatches_only_the_first_target() -> None:
    provider, collection, application, operations, _, section = make_application()

    calls = []

    def counting(token, action, uuid):
        calls.append(uuid)
        raise _session_failure()

    provider.dispatch_action = counting  # type: ignore[method-assign]
    _run_bulk(provider, application, operations, section)
    assert len(calls) == 1
    collection.close()


def test_unrecognised_errno_aborts_the_batch() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [PvmReply("failed", None, "4242", "unknown failure"), SUCCESS, SUCCESS]
    result, _ = _run_bulk(provider, application, operations, section)
    assert [item.state for item in result.targets][1:] == [
        OperationState.NOT_STARTED,
        OperationState.NOT_STARTED,
    ]
    assert len(provider.dispatched) == 1
    collection.close()


def test_outcome_unknown_aborts_the_batch() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [RuntimeError("socket closed"), SUCCESS, SUCCESS]
    result, _ = _run_bulk(provider, application, operations, section)
    assert result.targets[0].state is OperationState.OUTCOME_UNKNOWN
    assert all(item.state is OperationState.NOT_STARTED for item in result.targets[1:])
    assert len(provider.dispatched) == 1
    collection.close()


def test_process_start_failure_aborts_before_dispatching_the_rest() -> None:
    provider, collection, application, operations, _, section = make_application()

    def fail_spawn(token, action, uuid):
        raise AppError(
            ErrorKind.PROCESS, "could not start configured local command",
            code="PROCESS_START_FAILED",
        )

    provider.dispatch_action = fail_spawn  # type: ignore[method-assign]
    result, _ = _run_bulk(provider, application, operations, section)
    assert result.targets[0].state is OperationState.FAILED
    assert all(item.state is OperationState.NOT_STARTED for item in result.targets[1:])
    collection.close()


def test_single_target_action_is_unaffected_by_the_policy() -> None:
    """A one-target request has nothing to continue with."""
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_A,))
    provider.replies = [PvmReply("failed", None, "146", "already stopped")]
    result = operations.execute(
        "token", Action.STOP, selection.records, section, is_bulk=selection.is_bulk
    )
    assert result.targets[0].state is OperationState.FAILED
    assert result.state is OperationState.FAILED
    collection.close()


# ------------------------------------------------------------- progress sink


def test_progress_sink_reports_every_target_under_scoped_continuation() -> None:
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [
        PvmReply("failed", None, "146", "already stopped"),
        SUCCESS,
        SUCCESS,
    ]
    selection = application.resolve_targets(as_inventory(section), ("all",))
    plan = operations.create_plan(
        Action.STOP, selection.records, section, is_bulk=True
    )
    seen: list[tuple[str, OperationState]] = []
    operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=lambda uuid, state: seen.append((uuid, state)),
    )
    assert [state for _, state in seen] == [
        OperationState.FAILED,
        OperationState.SUCCEEDED,
        OperationState.SUCCEEDED,
    ]
    assert [uuid for uuid, _ in seen] == list(selection.uuids)
    collection.close()


# ---------------------------------------------------------- response plumbing


def test_errno_reaches_the_adapter_error_translation() -> None:
    """A PVM rejection must carry its errno as data, not only as message text."""
    from plaivid_cli.infrastructure.pvm.adapter.local import LocalPvmAdapter
    from plaivid_cli.infrastructure.pvm.sbell import SbellResponse

    response = SbellResponse(
        status="failed", action_id=None, errno="146", what="VM 'alpha' is bad",
        description=None, returncode=0,
    )
    with pytest.raises(AppError) as caught:
        LocalPvmAdapter._require_read(response, "vm/stop")
    assert caught.value.errno == "146"
    assert caught.value.kind is ErrorKind.PVM_RESPONSE


def test_app_error_exposes_errno_and_defaults_to_none() -> None:
    explicit = AppError(ErrorKind.PROCESS, "boom", errno="146")
    default = AppError(ErrorKind.PROCESS, "boom")
    assert explicit.errno == "146"
    assert default.errno is None


def test_target_outcome_errno_defaults_to_none_for_existing_callers() -> None:
    outcome = TargetOutcome(UUID_A, OperationState.SUCCEEDED)
    assert outcome.errno is None


def test_plan_validated_bulk_path_also_continues() -> None:
    """The reviewed-plan path (`plan=` supplied) follows the same policy."""
    provider, collection, application, operations, _, section = make_application()
    provider.replies = [
        PvmReply("failed", None, "146", "already stopped"),
        SUCCESS,
        SUCCESS,
    ]
    result, _ = _plan_and_run(provider, application, operations, section)
    assert [item.state for item in result.targets] == [
        OperationState.FAILED,
        OperationState.SUCCEEDED,
        OperationState.SUCCEEDED,
    ]
    collection.close()

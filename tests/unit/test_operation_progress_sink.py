"""The optional per-target progress sink must report every dispatch outcome.

The sink exists so a presentation can show live per-target status. It is
optional and additive: omitting it must leave dispatch behaviour identical, and
a broken sink must never abort or alter a bulk operation.
"""

from __future__ import annotations

from plaivid_cli.application.operations import aggregate_state
from plaivid_cli.application.services import as_inventory
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    ErrorKind,
    OperationState,
    PvmReply,
)
from tests.unit.test_application_operations import (
    UUID_A,
    UUID_B,
    UUID_C,
    make_application,
)


class Sink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, OperationState]] = []

    def __call__(self, target_uuid: str, state: OperationState) -> None:
        self.calls.append((target_uuid, state))

    @property
    def uuids(self) -> list[str]:
        return [uuid for uuid, _ in self.calls]


def _plan_for(application, operations, selectors, action: Action):
    _, section = application.inventory("token")
    inventory = as_inventory(section)
    selection = application.resolve_targets(inventory, selectors)
    plan = operations.create_plan(
        action, selection.records, section, is_bulk=selection.is_bulk
    )
    return selection, section, plan


def test_sink_reports_one_success_per_target() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(application, operations, (UUID_A,), Action.START)
    sink = Sink()
    result = operations.execute(
        "token",
        Action.START,
        selection.records,
        section,
        is_bulk=selection.is_bulk,
        plan=plan,
        on_progress=sink,
    )
    assert result.state is OperationState.SUCCEEDED
    assert sink.calls == [
        (UUID_A, OperationState.RUNNING),
        (UUID_A, OperationState.SUCCEEDED),
    ]
    collection.close()


def test_bulk_sink_reports_every_target_in_dispatch_order() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(
        application, operations, ("state:running",), Action.STOP
    )
    assert selection.uuids == (UUID_A, UUID_C)
    sink = Sink()
    operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=sink,
    )
    assert sink.calls == [
        (UUID_A, OperationState.RUNNING),
        (UUID_A, OperationState.SUCCEEDED),
        (UUID_C, OperationState.RUNNING),
        (UUID_C, OperationState.SUCCEEDED),
    ]
    collection.close()


def test_bulk_stop_reports_session_scoped_failure_and_not_started_for_the_remainder() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(
        application, operations, ("state:running",), Action.STOP
    )
    provider.replies = [PvmReply("failed", errno="39", message="session invalid")]
    sink = Sink()
    result = operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=sink,
    )
    # A session-scoped failure aborts the batch; UUID_C never enters RUNNING.
    assert result.state is OperationState.FAILED
    assert provider.dispatched == [(Action.STOP, UUID_A)]
    assert sink.calls == [
        (UUID_A, OperationState.RUNNING),
        (UUID_A, OperationState.FAILED),
        (UUID_C, OperationState.NOT_STARTED),
    ]
    collection.close()


def test_bulk_stop_continues_reporting_after_target_scoped_failure() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(
        application, operations, ("state:running",), Action.STOP
    )
    provider.replies = [
        PvmReply("failed", errno="146", message="VM 'alpha' is already stopped"),
        PvmReply("success"),
    ]
    sink = Sink()
    result = operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=sink,
    )
    # Target-scoped errno 146 isolates to UUID_A; UUID_C still dispatches and succeeds.
    assert result.state is OperationState.PARTIAL
    assert provider.dispatched == [(Action.STOP, UUID_A), (Action.STOP, UUID_C)]
    assert sink.calls == [
        (UUID_A, OperationState.RUNNING),
        (UUID_A, OperationState.FAILED),
        (UUID_C, OperationState.RUNNING),
        (UUID_C, OperationState.SUCCEEDED),
    ]
    collection.close()


def test_unknown_process_error_is_reported_as_unknown_and_stops_the_bulk() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(
        application, operations, ("state:running",), Action.RESET
    )

    def explode(token, action, uuid):
        raise AppError(ErrorKind.PROCESS, "synthetic process error", code="PVM_PROCESS_ERROR")

    provider.dispatch_action = explode  # type: ignore[method-assign]
    sink = Sink()
    result = operations.execute(
        "token",
        Action.RESET,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=sink,
    )
    assert [state for _, state in sink.calls] == [
        OperationState.RUNNING,
        OperationState.OUTCOME_UNKNOWN,
        OperationState.NOT_STARTED,
    ]
    assert result.state is OperationState.OUTCOME_UNKNOWN
    collection.close()


def test_sink_can_be_omitted_without_changing_behaviour() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(application, operations, (UUID_B,), Action.START)
    without = operations.execute(
        "token",
        Action.START,
        selection.records,
        section,
        is_bulk=selection.is_bulk,
        plan=plan,
    )
    assert without.state is OperationState.SUCCEEDED
    assert provider.dispatched == [(Action.START, UUID_B)]
    collection.close()


def test_a_broken_sink_never_aborts_or_alters_the_operation() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(
        application, operations, ("state:running",), Action.PAUSE
    )
    attempts: list[str] = []

    def broken(target_uuid: str, state: OperationState) -> None:
        attempts.append(target_uuid)
        raise RuntimeError("presentation bug")

    result = operations.execute(
        "token",
        Action.PAUSE,
        selection.records,
        section,
        is_bulk=True,
        plan=plan,
        on_progress=broken,
    )
    assert result.state is OperationState.SUCCEEDED
    assert attempts == [UUID_A, UUID_A, UUID_C, UUID_C]
    assert provider.dispatched == [(Action.PAUSE, UUID_A), (Action.PAUSE, UUID_C)]
    assert aggregate_state(result.targets) is OperationState.SUCCEEDED
    collection.close()


def test_sink_is_not_called_when_the_plan_is_rejected_before_dispatch() -> None:
    provider, collection, application, operations, _, _ = make_application()
    selection, section, plan = _plan_for(application, operations, (UUID_A,), Action.START)
    # Force the pre-dispatch barrier to fail by mutating inventory generation.
    application.collection.collect_once("token", sections=("inventory",))
    sink = Sink()
    try:
        operations.execute(
            "token",
            Action.START,
            selection.records,
            section,
            is_bulk=selection.is_bulk,
            plan=plan,
            on_progress=sink,
        )
    except AppError as exc:
        assert exc.kind.value == "policy"
    assert sink.calls == []
    assert provider.dispatched == []
    collection.close()

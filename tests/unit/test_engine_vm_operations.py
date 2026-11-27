from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pvm_control_engine.application.operations.vm.executor import VMOperationExecutor
from pvm_control_engine.application.operations.vm.kill_vm import KillVM
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    InventoryData,
    ObjectVM,
    OperationResult,
    OperationState,
    SectionSnapshot,
    TargetOutcome,
    VMRecord,
)

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"
UUID_B = "067928e8-631b-4f0a-b748-325990172e6e"
NOW = datetime.now(UTC)


def _record(uuid: str) -> VMRecord:
    return VMRecord(ObjectVM(uuid=uuid, name=f"vm-{uuid[:4]}"))


class FakeApplication:
    def __init__(self, records: tuple[VMRecord, ...]) -> None:
        self.records = records
        self.inventory_tokens: list[str] = []

    def inventory(self, token: str):
        self.inventory_tokens.append(token)
        section = SectionSnapshot(
            name="inventory",
            value=InventoryData(records=self.records),
            last_good_value=None,
            status=CollectionStatus.CURRENT,
            attempted_at=NOW,
            succeeded_at=NOW,
            generation=9,
            source="fake current inventory",
            succeeded_monotonic=10.0,
        )
        return object(), section


class FakeOperations:
    def __init__(self, *, execute_error: Exception | None = None) -> None:
        self.plan_calls = []
        self.execute_calls = []
        self.execute_error = execute_error
        self.plan = object()
        self.result = None

    def create_plan(self, action, records, section, *, is_bulk):
        self.plan_calls.append((action, records, section.generation, is_bulk))
        return self.plan

    def execute(self, token, action, records, section, *, is_bulk, plan):
        self.execute_calls.append((token, action, records, section.generation, is_bulk, plan))
        if self.execute_error is not None:
            raise self.execute_error
        return self.result


def _unknown_result(records: tuple[VMRecord, ...]) -> OperationResult:
    outcomes = tuple(
        TargetOutcome(
            record.uuid, OperationState.OUTCOME_UNKNOWN, "reply timed out", dispatched=True
        )
        for record in records
    )
    return OperationResult(
        operation_id="operation-1",
        action=Action.KILL,
        state=OperationState.OUTCOME_UNKNOWN,
        targets=outcomes,
        started_at=NOW,
        finished_at=NOW,
        message="outcome unknown; do not retry until reconciled",
    )


def _use_case(records: tuple[VMRecord, ...], operations: FakeOperations):
    application = FakeApplication(records)
    executor = VMOperationExecutor(application, operations)
    return KillVM(executor), application, operations


def test_kill_vm_single_target_uses_shared_plan_and_preserves_unknown_result():
    record = _record(UUID_A)
    operations = FakeOperations()
    expected = _unknown_result((record,))
    operations.result = expected
    kill, application, operations = _use_case((record,), operations)

    result = kill.execute("engine-session", UUID_A)

    assert result is expected
    assert application.inventory_tokens == ["engine-session"]
    assert operations.plan_calls == [(Action.KILL, (record,), 9, False)]
    assert operations.execute_calls == [
        ("engine-session", Action.KILL, (record,), 9, False, operations.plan)
    ]
    assert result.state is OperationState.OUTCOME_UNKNOWN


def test_kill_vm_bulk_targets_are_validated_once_and_sent_to_shared_batch_coordinator():
    records = (_record(UUID_A), _record(UUID_B))
    operations = FakeOperations()
    expected = _unknown_result(records)
    operations.result = expected
    kill, application, operations = _use_case(records, operations)

    result = kill.execute_many("engine-session", (UUID_A, UUID_B))

    assert result is expected
    assert application.inventory_tokens == ["engine-session"]
    assert operations.plan_calls == [(Action.KILL, records, 9, True)]
    assert operations.execute_calls == [
        ("engine-session", Action.KILL, records, 9, True, operations.plan)
    ]
    assert [outcome.uuid for outcome in result.targets] == [UUID_A, UUID_B]
    assert result.state is OperationState.OUTCOME_UNKNOWN


@pytest.mark.parametrize(
    ("records", "uuids", "error_code"),
    [
        ((_record(UUID_A),), (UUID_A.upper(),), "INVALID_UUID"),
        ((_record(UUID_A),), (UUID_A, UUID_A), "INVALID_UUID"),
        ((_record(UUID_A),), (UUID_B,), "VM_NOT_FOUND"),
        (
            (_record(UUID_A),),
            tuple(f"00000000-0000-4000-8000-{n:012x}" for n in range(101)),
            "INVALID_TARGET_COUNT",
        ),
    ],
)
def test_kill_vm_rejects_invalid_or_unsafe_targets_before_planning(records, uuids, error_code):
    operations = FakeOperations()
    kill, _application, operations = _use_case(records, operations)

    with pytest.raises(AppError) as caught:
        kill.execute_many("engine-session", uuids)

    assert caught.value.code == error_code
    assert operations.plan_calls == []
    assert operations.execute_calls == []


def test_kill_vm_does_not_hide_coordinator_policy_errors():
    failure = AppError(
        ErrorKind.POLICY, "inventory freshness admission failed", code="OPERATION_PLAN_STALE"
    )
    kill, _application, operations = _use_case(
        (_record(UUID_A),), FakeOperations(execute_error=failure)
    )

    with pytest.raises(AppError) as caught:
        kill.execute("engine-session", UUID_A)

    assert caught.value is failure
    assert len(operations.plan_calls) == 1
    assert len(operations.execute_calls) == 1

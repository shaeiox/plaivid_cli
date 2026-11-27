from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pvm_control_engine.config import load_settings
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import (
    Action,
    ApplicationSnapshot,
    CollectionStatus,
    ErrorKind,
    InventoryData,
    ObjectVM,
    OperationState,
    PvmReply,
    SectionSnapshot,
    VMRecord,
)
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator
from pvm_control_engine.infrastructure.sbell.commands.vm.kill import KillVM
from pvm_control_engine.infrastructure.sbell.commands.vm.pause import PauseVM
from pvm_control_engine.infrastructure.sbell.commands.vm.reset import ResetVM
from pvm_control_engine.infrastructure.sbell.commands.vm.resume import ResumeVM
from pvm_control_engine.infrastructure.sbell.commands.vm.start import StartVM
from pvm_control_engine.infrastructure.sbell.commands.vm.stop import StopVM
from pvm_control_engine.targets.vm_resolver import VMResolver

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"
UUID_B = "067928e8-631b-4f0a-b748-325990172e6e"
NOW = datetime.now(UTC)


def record(uuid: str) -> VMRecord:
    return VMRecord(ObjectVM(uuid=uuid, name=f"vm-{uuid[:4]}", state="stopped"))


class FakeAuth:
    def __init__(self) -> None:
        self.calls = 0

    def token(self) -> str:
        self.calls += 1
        return "session-token"


class FakeApplication:
    def __init__(self, records: tuple[VMRecord, ...]) -> None:
        self.records = records
        self.calls: list[str] = []
        self.inventory_section = SectionSnapshot(
            name="inventory",
            value=InventoryData(records=records),
            last_good_value=None,
            status=CollectionStatus.CURRENT,
            attempted_at=NOW,
            succeeded_at=NOW,
            generation=7,
            source="fake current inventory",
            succeeded_monotonic=20.0,
        )

    def inventory(self, token: str):
        self.calls.append(token)
        return object(), self.inventory_section


class FakeCollection:
    def __init__(self, records: tuple[VMRecord, ...], *, fresh: bool = True) -> None:
        self.inventory = SectionSnapshot(
            name="inventory",
            value=InventoryData(records=records),
            last_good_value=None,
            status=CollectionStatus.CURRENT,
            attempted_at=NOW,
            succeeded_at=NOW,
            generation=7,
            source="fake current inventory",
            succeeded_monotonic=20.0,
        )
        self.objects = SectionSnapshot(
            name="objects",
            value=tuple(item.object for item in records),
            last_good_value=None,
            status=CollectionStatus.CURRENT,
            attempted_at=NOW,
            succeeded_at=NOW,
            generation=7,
            source="fake current objects",
            succeeded_monotonic=20.0,
        )
        self.snapshot = ApplicationSnapshot(7, NOW, (self.inventory, self.objects))
        self.fresh = fresh
        self.barriers: list[tuple[tuple[str, ...], int, float | None, bool]] = []
        self.ended: list[tuple[str, ...]] = []
        self.reconciliations: list[tuple[str, ...]] = []

    def is_fresh(self, _name: str, *, max_age_seconds: float | None) -> bool:
        return bool(self.fresh and max_age_seconds is not None)

    def begin_mutation(self, target_uuids, **kwargs) -> None:
        self.barriers.append(
            (
                tuple(target_uuids),
                kwargs["expected_inventory_generation"],
                kwargs["max_age_seconds"],
                kwargs["require_complete_inventory"],
            )
        )

    def end_mutation(self, target_uuids) -> None:
        self.ended.append(tuple(target_uuids))

    def collect_once(self, _token: str, *, sections: tuple[str, ...]):
        self.reconciliations.append(sections)
        return self.snapshot


class FakeGateway:
    def __init__(self, *, alive: bool = True) -> None:
        self.alive = alive

    def is_daemon_alive(self, timeout=2.0, *, token=None) -> bool:
        return self.alive


class FakeSbell:
    def __init__(self, replies: tuple[object, ...] = ()) -> None:
        self.calls: list[tuple[str, str, str, str | None, float | None]] = []
        self.replies = list(replies)

    def call(self, module, command, params, token=None, *, timeout=None):
        self.calls.append((module, command, params, token, timeout))
        if self.replies:
            result = self.replies.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return Reply("success")


class Reply:
    def __init__(self, status: str, errno: str | None = None, message: str | None = None) -> None:
        self.status = status
        self.errno = errno
        self.message = message

    def reply(self):
        return PvmReply(self.status, errno=self.errno, message=self.message)


def create_commands(tmp_path: Path, records: tuple[VMRecord, ...], *, sbell=None, fresh=True):
    settings = load_settings(
        {
            "PLAIVID_STATE_DIR": str(tmp_path / "state"),
            "PLAIVID_MAX_INVENTORY_AGE_SECONDS": "30",
            "PLAIVID_MAX_CONCURRENCY": "1",
            "PLAIVID_ALLOW_CREDENTIAL_ARGV": "1",
        }
    )
    app = FakeApplication(records)
    collection = FakeCollection(records, fresh=fresh)
    coordinator = VMOperationCoordinator(FakeGateway(), collection, settings)
    auth = FakeAuth()
    transport = sbell or FakeSbell()
    resolver = VMResolver(app)
    commands = {
        Action.START: StartVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
        Action.STOP: StopVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
        Action.KILL: KillVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
        Action.RESET: ResetVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
        Action.PAUSE: PauseVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
        Action.RESUME: ResumeVM(
            auth, resolver, coordinator, transport, action_timeout=settings.action_timeout
        ),
    }
    return commands, app, collection, auth, transport


def test_each_vm_command_owns_fixed_sbell_action_and_exact_parameters(tmp_path):
    expected = {
        Action.START: (
            "start",
            "<vm_start><vm_key>" + UUID_A + "</vm_key><host>auto</host>"
            "<version_start><version_enable>no</version_enable><version_vkey></version_vkey>"
            "</version_start><exit_from_replicate>yes</exit_from_replicate></vm_start>",
        ),
        Action.STOP: ("stop", f"<vm_key>{UUID_A}</vm_key>"),
        Action.KILL: ("kill", f"<vm_key>{UUID_A}</vm_key>"),
        Action.RESET: ("reset", f"<vm_key>{UUID_A}</vm_key>"),
        Action.PAUSE: ("pause", f"<vm_key>{UUID_A}</vm_key>"),
        Action.RESUME: ("resume", f"<vm_key>{UUID_A}</vm_key>"),
    }
    commands, app, collection, auth, sbell = create_commands(tmp_path, (record(UUID_A),))

    for action, command in commands.items():
        result = command.execute(UUID_A)
        assert result.state is OperationState.SUCCEEDED
        assert command.MODULE == "vm"
        assert command.COMMAND == expected[action][0]
        assert sbell.calls[-1] == (
            "vm",
            expected[action][0],
            expected[action][1],
            "session-token",
            10.0,
        )

    assert auth.calls == len(Action)
    assert app.calls == ["session-token"] * len(Action)
    assert len(collection.barriers) == len(Action)
    assert collection.reconciliations == [("inventory",)] * len(Action)


def test_start_xml_escapes_untrusted_text_and_uuid_resolver_rejects_non_uuid(tmp_path):
    commands, app, _collection, _auth, sbell = create_commands(tmp_path, (record(UUID_A),))
    start = commands[Action.START]
    with pytest.raises(AppError) as caught:
        start.execute("<UUID_A>&not-a-uuid")
    assert caught.value.code == "INVALID_UUID"
    assert app.calls == []
    assert sbell.calls == []


def test_bulk_kill_is_validated_once_and_keeps_target_order(tmp_path):
    records = (record(UUID_A), record(UUID_B))
    commands, app, collection, auth, sbell = create_commands(tmp_path, records)

    result = commands[Action.KILL].execute_many((UUID_A, UUID_B))

    assert result.state is OperationState.SUCCEEDED
    assert tuple(target.uuid for target in result.targets) == (UUID_A, UUID_B)
    assert app.calls == ["session-token"]
    assert auth.calls == 1
    assert len(sbell.calls) == 2
    assert all(call[0:2] == ("vm", "kill") for call in sbell.calls)
    assert collection.barriers == [((UUID_A, UUID_B), 7, 30.0, True)]
    assert collection.ended == [(UUID_A, UUID_B)]


@pytest.mark.parametrize(
    ("inputs", "error_code"),
    [
        ((UUID_A.upper(),), "INVALID_UUID"),
        ((UUID_A, UUID_A), "INVALID_UUID"),
        ((UUID_B,), "VM_NOT_FOUND"),
        ((), "INVALID_UUID"),
        (tuple(f"00000000-0000-4000-8000-{n:012x}" for n in range(101)), "INVALID_TARGET_COUNT"),
    ],
)
def test_vm_resolver_rejects_unsafe_targets_before_dispatch(tmp_path, inputs, error_code):
    commands, app, collection, _auth, sbell = create_commands(tmp_path, (record(UUID_A),))

    with pytest.raises(AppError) as caught:
        commands[Action.KILL].execute_many(inputs)

    assert caught.value.code == error_code
    assert app.calls == (
        []
        if error_code == "INVALID_TARGET_COUNT"
        else ["session-token"]
        if error_code == "VM_NOT_FOUND"
        else []
    )
    assert sbell.calls == []
    assert collection.barriers == []


def test_freshness_rejection_and_unknown_timeout_never_claim_success(tmp_path):
    stale_commands, _, stale_collection, _, stale_sbell = create_commands(
        tmp_path / "stale", (record(UUID_A),), fresh=False
    )
    with pytest.raises(AppError) as stale:
        stale_commands[Action.STOP].execute(UUID_A)
    assert stale.value.kind is ErrorKind.POLICY
    assert stale_sbell.calls == []
    assert stale_collection.barriers == []

    timeout = AppError(ErrorKind.PROCESS, "bounded command timed out", code="PVM_COMMAND_TIMEOUT")
    commands, _, collection, _, sbell = create_commands(
        tmp_path / "timeout", (record(UUID_A),), sbell=FakeSbell((timeout,))
    )
    result = commands[Action.STOP].execute(UUID_A)
    assert result.state is OperationState.OUTCOME_UNKNOWN
    assert result.targets[0].state is OperationState.OUTCOME_UNKNOWN
    assert result.targets[0].code == "PVM_COMMAND_TIMEOUT"
    assert collection.ended == [(UUID_A,)]
    assert collection.reconciliations == [("inventory",)]
    assert "do not retry" in result.message


def test_bulk_stops_after_definite_failure_and_marks_unstarted_targets(tmp_path):
    sbell = FakeSbell((Reply("failed", "39", "session expired"), Reply("success")))
    commands, _, collection, _, _ = create_commands(
        tmp_path, (record(UUID_A), record(UUID_B)), sbell=sbell
    )

    result = commands[Action.STOP].execute_many((UUID_A, UUID_B))

    assert result.state is OperationState.FAILED
    assert [target.state for target in result.targets] == [
        OperationState.FAILED,
        OperationState.NOT_STARTED,
    ]
    assert len(sbell.calls) == 1
    assert collection.ended == [(UUID_A, UUID_B)]

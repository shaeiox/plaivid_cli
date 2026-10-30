from __future__ import annotations

import threading

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.application.operations import OperationCoordinator, aggregate_state
from plaivid_cli.application.services import PlaividApplication, as_inventory
from plaivid_cli.config import load_settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ObjectVM,
    OperationState,
    ProcessObservation,
    PvmReply,
    SourceResult,
    TargetOutcome,
    VMRecord,
)
from plaivid_cli.domain.policies import action_policy

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"
UUID_B = "800b0429-d82a-4e26-a5e2-225990172e6e"
UUID_C = "cee2b41d-c6c7-4202-9ff4-1510589294c9"


class FakeProvider:
    def __init__(self) -> None:
        self.objects = (
            ObjectVM(UUID_A, "alpha", state="started"),
            ObjectVM(UUID_B, "beta", state="stopped"),
            ObjectVM(UUID_C, "alpine", state="started"),
        )
        self.processes = (
            ProcessObservation(UUID_A, pid=10),
            ProcessObservation(UUID_C, pid=30),
        )
        self.replies: list[PvmReply | Exception] = []
        self.dispatched: list[tuple[Action, str]] = []
        self.fail_process_collection = False
        self.dispatch_gate: threading.Event | None = None
        self.dispatch_entered: threading.Event | None = None

    def list_objects(self, token):
        return SourceResult(self.objects, CollectionStatus.CURRENT, "user/objects")

    def list_processes(self):
        if self.fail_process_collection:
            raise RuntimeError("synthetic process helper outage")
        return SourceResult(self.processes, CollectionStatus.CURRENT, "pvm-running-vms")

    def host_status(self, token):
        return SourceResult(None, CollectionStatus.UNAVAILABLE, "sball/show")

    def host_metrics(self, token):
        return SourceResult(None, CollectionStatus.UNAVAILABLE, "monitoring/metrics")

    def vm_detail(self, token, uuid):
        raise NotImplementedError

    def tap_mapping(self, token):
        raise NotImplementedError

    def dispatch_action(self, token, action, uuid):
        if self.dispatch_entered is not None:
            self.dispatch_entered.set()
        if self.dispatch_gate is not None:
            self.dispatch_gate.wait(2)
        self.dispatched.append((action, uuid))
        result = self.replies.pop(0) if self.replies else PvmReply("success")
        if isinstance(result, Exception):
            raise result
        return result


def make_application(*, max_age: bool = True, process_failure: bool = False):
    provider = FakeProvider()
    provider.fail_process_collection = process_failure
    settings = load_settings(
        {"PLAIVID_MAX_INVENTORY_AGE_SECONDS": "30"} if max_age else {}
    )
    collection = CollectionCoordinator(provider)
    application = PlaividApplication(provider, collection, settings)
    operations = OperationCoordinator(provider, collection, settings)
    snapshot, section = application.inventory("token")
    return provider, collection, application, operations, snapshot, section


def test_target_resolution_supports_uuid_name_prefix_index_and_group_selectors():
    _, collection, application, _, _, section = make_application()
    inventory = as_inventory(section)
    by_uuid = application.resolve_targets(inventory, (UUID_B,))
    by_name = application.resolve_targets(inventory, ("beta",))
    by_prefix = application.resolve_targets(inventory, ("bet",))
    by_index = application.resolve_targets(inventory, ("1",))
    running = application.resolve_targets(inventory, ("state:running",))
    assert by_uuid.uuids == (UUID_B,)
    assert by_name.uuids == (UUID_B,)
    assert by_prefix.uuids == (UUID_B,)
    assert not by_prefix.is_bulk
    assert by_index.uuids == (UUID_A,)
    assert running.uuids == (UUID_A, UUID_C)
    assert running.is_bulk
    collection.close()


def test_ambiguous_prefix_and_duplicate_targets_are_rejected():
    _, collection, application, _, _, section = make_application()
    inventory = as_inventory(section)
    try:
        application.resolve_targets(inventory, ("alp",))
    except AppError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("ambiguous prefix was accepted")
    try:
        application.resolve_targets(inventory, (UUID_A, UUID_A))
    except AppError as exc:
        assert "more than once" in str(exc)
    else:
        raise AssertionError("duplicate target was accepted")
    collection.close()


def test_operation_plan_rejects_targets_not_in_the_current_inventory():
    provider, collection, application, operations, _, section = make_application()
    fabricated = VMRecord(
        ObjectVM("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", "not-in-inventory", state="stopped")
    )
    try:
        operations.create_plan(Action.START, (fabricated,), section, is_bulk=False)
    except AppError as exc:
        assert "do not exactly match" in str(exc)
    else:
        raise AssertionError("fabricated target was accepted")
    assert provider.dispatched == []
    collection.close()


def test_unverified_positive_reply_is_unknown_and_not_completion():
    provider, collection, application, operations, _, section = make_application()
    target = application.resolve_targets(as_inventory(section), (UUID_B,))
    result = operations.execute(
        "token", Action.START, target.records, section, is_bulk=False
    )
    assert result.state is OperationState.OUTCOME_UNKNOWN
    assert result.targets[0].state is OperationState.OUTCOME_UNKNOWN
    assert result.targets[0].dispatched
    assert "semantics are unverified" in result.targets[0].message
    assert provider.dispatched == [(Action.START, UUID_B)]
    assert collection.snapshot.section("inventory").status is CollectionStatus.CURRENT
    collection.close()


def test_single_operation_can_use_current_object_source_when_process_enrichment_is_partial():
    provider, collection, application, operations, _, section = make_application(process_failure=True)
    assert section.status is CollectionStatus.PARTIAL
    target = application.resolve_targets(as_inventory(section), (UUID_B,))
    result = operations.execute(
        "token", Action.START, target.records, section, is_bulk=False
    )
    assert result.state is OperationState.OUTCOME_UNKNOWN
    assert provider.dispatched == [(Action.START, UUID_B)]
    collection.close()


def test_explicit_plan_cancellation_reports_cancelled_before_dispatch():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_B,))
    plan = operations.create_plan(
        Action.STOP, selection.records, section, is_bulk=False
    )
    result = operations.cancel(plan)
    assert result.state is OperationState.CANCELLED_BEFORE_DISPATCH
    assert result.targets[0].state is OperationState.CANCELLED_BEFORE_DISPATCH
    assert not result.targets[0].dispatched
    assert provider.dispatched == []
    collection.close()


def test_stop_requires_exact_uuid_confirmation_bound_to_inventory_generation():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_B,))
    phrase = operations.confirmation_phrase(Action.STOP, selection.uuids)
    approval = operations.approve(
        Action.STOP, selection.records, section, confirmation=phrase
    )
    result = operations.execute(
        "token", Action.STOP, selection.records, section, is_bulk=False, approval=approval
    )
    assert result.state is OperationState.OUTCOME_UNKNOWN
    assert provider.dispatched == [(Action.STOP, UUID_B)]
    collection.close()


def test_immutable_operation_plan_is_invalidated_by_a_new_inventory_generation():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_B,))
    plan = operations.create_plan(
        Action.STOP, selection.records, section, is_bulk=False
    )
    assert plan.target_uuids == (UUID_B,)
    assert plan.inventory_generation == section.generation
    assert plan.confirmation == f"STOP {UUID_B}"
    approval = operations.approve(
        Action.STOP, selection.records, section, confirmation=plan.confirmation
    )
    newer_snapshot = collection.collect_once("token", sections=("inventory",))
    newer_section = newer_snapshot.section("inventory")
    assert newer_section is not None and newer_section.generation != section.generation
    try:
        operations.execute(
            "token",
            Action.STOP,
            selection.records,
            section,
            is_bulk=False,
            approval=approval,
            plan=plan,
        )
    except AppError as exc:
        assert "inventory changed" in str(exc)
    else:
        raise AssertionError("stale operation plan was accepted")
    assert provider.dispatched == []
    collection.close()


def test_stop_refuses_missing_or_wrong_confirmation_before_dispatch():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_B,))
    try:
        operations.approve(
            Action.STOP, selection.records, section, confirmation=f"STOP {UUID_A}"
        )
    except AppError as exc:
        assert exc.code == "APPROVAL_MISMATCH"
    else:
        raise AssertionError("wrong confirmation was accepted")
    try:
        operations.execute("token", Action.STOP, selection.records, section, is_bulk=False)
    except AppError as exc:
        assert exc.code == "APPROVAL_REQUIRED"
    else:
        raise AssertionError("stop dispatched without approval")
    assert provider.dispatched == []
    collection.close()


def test_bulk_stops_on_unverified_positive_reply_and_marks_remainder_not_started():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), ("all",))
    approval = operations.approve(
        Action.START,
        selection.records,
        section,
        confirmation=operations.confirmation_phrase(Action.START, selection.uuids),
    )
    provider.replies = [PvmReply("success"), PvmReply("success"), PvmReply("success")]
    result = operations.execute(
        "token", Action.START, selection.records, section, is_bulk=True, approval=approval
    )
    assert [item.state for item in result.targets] == [
        OperationState.OUTCOME_UNKNOWN,
        OperationState.NOT_STARTED,
        OperationState.NOT_STARTED,
    ]
    assert result.state is OperationState.OUTCOME_UNKNOWN
    assert len(provider.dispatched) == 1
    collection.close()


def test_aggregate_precedence_preserves_acceptance_unknown_and_partial_states():
    accepted = TargetOutcome(UUID_A, OperationState.COMMAND_ACCEPTED_UNCONFIRMED, dispatched=True)
    failed = TargetOutcome(UUID_B, OperationState.FAILED, dispatched=False)
    unknown = TargetOutcome(UUID_C, OperationState.OUTCOME_UNKNOWN, dispatched=True)
    success = TargetOutcome(UUID_A, OperationState.SUCCEEDED, dispatched=True)
    not_started = TargetOutcome(UUID_B, OperationState.NOT_STARTED)
    assert aggregate_state((accepted, failed)) is OperationState.COMMAND_ACCEPTED_UNCONFIRMED
    assert aggregate_state((accepted, failed, unknown)) is OperationState.OUTCOME_UNKNOWN
    assert aggregate_state((success, failed)) is OperationState.PARTIAL
    assert aggregate_state((success, not_started)) is OperationState.PARTIAL
    assert aggregate_state((failed,)) is OperationState.FAILED
    assert aggregate_state((TargetOutcome(UUID_A, OperationState.REJECTED),)) is OperationState.REJECTED


def test_multi_target_plan_cannot_be_mislabeled_single_before_dispatch():
    provider, collection, application, operations, _, section = make_application()
    inventory = as_inventory(section)
    selected = application.resolve_targets(inventory, (UUID_A, UUID_B))
    try:
        operations.create_plan(Action.START, selected.records, section, is_bulk=False)
    except AppError as exc:
        assert "declared as one bulk plan" in str(exc)
    else:
        raise AssertionError("multi-target single plan was accepted")
    assert provider.dispatched == []
    collection.close()


def test_all_six_lifecycle_actions_are_supported_but_unverified_replies_remain_unknown():
    for action in Action:
        provider, collection, application, operations, _, section = make_application()
        selection = application.resolve_targets(as_inventory(section), (UUID_B,))
        approval = None
        if action_policy(action).confirm_single:
            approval = operations.approve(
                action,
                selection.records,
                section,
                confirmation=operations.confirmation_phrase(action, selection.uuids),
            )
        result = operations.execute(
            "token", action, selection.records, section, is_bulk=False, approval=approval
        )
        assert result.action is action
        assert result.state is OperationState.OUTCOME_UNKNOWN
        assert provider.dispatched == [(action, UUID_B)]
        collection.close()


def test_close_waits_for_active_dispatch_and_rejects_new_operations():
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), (UUID_B,))
    entered = threading.Event()
    release = threading.Event()
    provider.dispatch_entered = entered
    provider.dispatch_gate = release
    worker = threading.Thread(
        target=lambda: operations.execute(
            "token", Action.START, selection.records, section, is_bulk=False
        )
    )
    worker.start()
    assert entered.wait(1)
    closer = threading.Thread(target=operations.close)
    closer.start()
    assert operations._closing.wait(1)
    assert closer.is_alive()
    try:
        operations.execute("token", Action.START, selection.records, section, is_bulk=False)
    except AppError as exc:
        assert "shutting down" in str(exc)
    else:
        raise AssertionError("new operation admitted after shutdown began")
    release.set()
    worker.join(2)
    closer.join(2)
    assert not worker.is_alive()
    assert not closer.is_alive()
    collection.close()


def test_bulk_is_default_denied_without_a_configured_inventory_age():
    provider, collection, application, operations, _, section = make_application(max_age=False)
    selection = application.resolve_targets(as_inventory(section), ("all",))
    phrase = operations.confirmation_phrase(Action.START, selection.uuids)
    approval = operations.approve(
        Action.START, selection.records, section, confirmation=phrase
    )
    try:
        operations.execute(
            "token", Action.START, selection.records, section, is_bulk=True, approval=approval
        )
    except AppError as exc:
        assert "PLAIVID_MAX_INVENTORY_AGE_SECONDS" in str(exc)
    else:
        raise AssertionError("bulk operation bypassed freshness configuration")
    assert provider.dispatched == []
    collection.close()

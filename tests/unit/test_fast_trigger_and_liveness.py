"""Tests for Two-Phase Fast Trigger + Daemon Liveness Probe + Scoped Fault Isolation.

Covers:
1. Bulk continuation to VM #2 / Desktop #2 when VM #1 times out with the 10 s
   fast action timeout (``PVM_COMMAND_TIMEOUT``) while ``is_daemon_alive()`` is True.
2. Fast bulk abort to ``SKIPPED`` (``OperationState.NOT_STARTED`` -> ``TaskStatus.SKIPPED``)
   with detail ``"Daemon Offline"`` when VM #1 fails or times out and the daemon
   liveness probe returns False.
3. Task Board / ``TaskViewFooter`` rendering of ``– SKIPPED`` in muted style,
   authoritative outcome details, and strictly sequential ``QUEUED -> RUNNING``
   transitions during bulk execution.
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import replace

from textual.widgets import Checkbox, Select

from plaivid_cli.application.services import as_inventory
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    OperationState,
    PvmReply,
    SourceResult,
    TargetOutcome,
    TaskStatus,
    task_status_for,
)
from plaivid_cli.domain.policies import (
    COMMAND_TIMEOUT_CODE,
    DAEMON_OFFLINE_REASON,
    is_target_scoped_error,
    outcome_stops_batch,
)
from plaivid_cli.presentation.theme import palette_for
from plaivid_cli.presentation.tui.app import PlaividTui
from plaivid_cli.presentation.tui.components import TaskViewFooter
from tests.unit.test_application_operations import UUID_A, UUID_B, make_application
from tests.unit.test_cli_and_tui import runtime as tui_runtime
from tests.unit.test_virtual_desktops import runtime as desktop_runtime


def _timeout_error() -> AppError:
    return AppError(
        ErrorKind.PROCESS,
        "local command timed out",
        code=COMMAND_TIMEOUT_CODE,
    )


# ------------------------------------------------ policy & coordinator unit tests


def test_command_timeout_is_target_scoped_only_when_daemon_is_alive() -> None:
    timed_out = TargetOutcome(
        UUID_A,
        OperationState.OUTCOME_UNKNOWN,
        "local command timed out",
        dispatched=True,
        code=COMMAND_TIMEOUT_CODE,
    )
    assert is_target_scoped_error(timed_out, daemon_alive=True) is True
    assert outcome_stops_batch(timed_out, daemon_alive=True) is False

    assert is_target_scoped_error(timed_out, daemon_alive=False) is False
    assert outcome_stops_batch(timed_out, daemon_alive=False) is True


def test_bulk_continues_to_vm2_when_vm1_hits_action_timeout_and_daemon_is_alive() -> None:
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), ("all",))
    probe_deadlines: list[float] = []

    def is_daemon_alive(timeout: float = 2.0, *, token: str | None = None) -> bool:
        probe_deadlines.append(timeout)
        return True

    provider.is_daemon_alive = is_daemon_alive  # type: ignore[attr-defined]
    provider.replies = [
        _timeout_error(),
        PvmReply("success"),
        PvmReply("success"),
    ]
    progress_details: list[tuple[str, OperationState, str]] = []

    result = operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        on_progress=lambda uuid, state, detail="": progress_details.append(
            (uuid, state, detail)
        ),
    )
    assert [t.state for t in result.targets] == [
        OperationState.OUTCOME_UNKNOWN,
        OperationState.SUCCEEDED,
        OperationState.SUCCEEDED,
    ]
    assert result.targets[0].code == COMMAND_TIMEOUT_CODE
    assert result.targets[0].message == "command timed out (10s), daemon healthy"
    # Aggregate retains OUTCOME_UNKNOWN precedence so VM #1 is never blindly retried.
    assert result.state is OperationState.OUTCOME_UNKNOWN
    # All three VMs were dispatched; liveness probe ran once (only for the timed-out VM).
    assert len(provider.dispatched) == 3
    assert probe_deadlines == [2.0]
    assert (
        selection.uuids[0],
        OperationState.OUTCOME_UNKNOWN,
        "command timed out (10s), daemon healthy",
    ) in progress_details
    collection.close()


def test_bulk_fast_aborts_to_skipped_when_vm1_fails_and_daemon_is_offline() -> None:
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), ("all",))
    probes = 0

    def is_daemon_alive(timeout: float = 2.0, *, token: str | None = None) -> bool:
        nonlocal probes
        probes += 1
        return False

    provider.is_daemon_alive = is_daemon_alive  # type: ignore[attr-defined]
    provider.replies = [
        PvmReply("failed", errno="146", message="connection reset"),
        PvmReply("success"),
        PvmReply("success"),
    ]
    progress_details: list[tuple[str, OperationState, str]] = []

    result = operations.execute(
        "token",
        Action.STOP,
        selection.records,
        section,
        is_bulk=True,
        on_progress=lambda uuid, state, detail="": progress_details.append(
            (uuid, state, detail)
        ),
    )
    assert [t.state for t in result.targets] == [
        OperationState.FAILED,
        OperationState.NOT_STARTED,
        OperationState.NOT_STARTED,
    ]
    assert [task_status_for(t.state) for t in result.targets] == [
        TaskStatus.FAILED,
        TaskStatus.SKIPPED,
        TaskStatus.SKIPPED,
    ]
    assert result.targets[0].message == DAEMON_OFFLINE_REASON
    assert result.targets[1].message == DAEMON_OFFLINE_REASON
    assert result.targets[2].message == DAEMON_OFFLINE_REASON
    # Fast abort: VM #2 and #3 were never dispatched and never entered RUNNING.
    assert len(provider.dispatched) == 1
    assert probes == 1
    assert progress_details == [
        (selection.uuids[0], OperationState.RUNNING, "dispatching…"),
        (selection.uuids[0], OperationState.FAILED, DAEMON_OFFLINE_REASON),
        (selection.uuids[1], OperationState.NOT_STARTED, DAEMON_OFFLINE_REASON),
        (selection.uuids[2], OperationState.NOT_STARTED, DAEMON_OFFLINE_REASON),
    ]
    collection.close()


def test_bulk_fast_aborts_when_vm1_times_out_and_daemon_is_offline() -> None:
    provider, collection, application, operations, _, section = make_application()
    selection = application.resolve_targets(as_inventory(section), ("all",))
    provider.is_daemon_alive = lambda timeout=2.0, *, token=None: False  # type: ignore[attr-defined]
    provider.replies = [_timeout_error(), PvmReply("success"), PvmReply("success")]

    result = operations.execute(
        "token", Action.STOP, selection.records, section, is_bulk=True
    )
    assert [t.state for t in result.targets] == [
        OperationState.FAILED,
        OperationState.NOT_STARTED,
        OperationState.NOT_STARTED,
    ]
    assert "command timed out (10s): Daemon Offline" == result.targets[0].message
    assert result.targets[1].message == DAEMON_OFFLINE_REASON
    assert result.targets[2].message == DAEMON_OFFLINE_REASON
    assert len(provider.dispatched) == 1
    collection.close()


def test_desktop_executor_shares_timeout_continuation_and_daemon_offline_abort(tmp_path) -> None:
    provider, collection, _, operations, _, settings = desktop_runtime(tmp_path)
    items = (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta"))
    reads: list[str] = []
    provider.list_desktops = lambda token: (
        reads.append(token) or SourceResult(items, CollectionStatus.CURRENT, "desktops")
    )
    operations._settings = replace(settings, max_inventory_age_seconds=30)

    # 1. Timeout on Desktop #1 + daemon alive -> Desktop #2 still runs and succeeds.
    section = collection.collect_once("fake", sections=("desktops",)).section("desktops")
    calls = 0

    def timeout_then_ok(token, action, uuid):
        nonlocal calls
        calls += 1
        provider.dispatched.append((action, uuid))
        if calls == 1:
            raise _timeout_error()
        return PvmReply("success")

    provider.dispatch_action = timeout_then_ok  # type: ignore[method-assign]
    provider.is_daemon_alive = lambda timeout=2.0, *, token=None: True  # type: ignore[attr-defined]
    try:
        plan = operations.create_desktop_plan(Action.STOP, items, section, is_bulk=True)
        res_alive = operations.execute_desktop(
            "fake", Action.STOP, items, section, is_bulk=True, plan=plan
        )
        assert [t.state for t in res_alive.targets] == [
            OperationState.OUTCOME_UNKNOWN,
            OperationState.SUCCEEDED,
        ]
        assert res_alive.targets[0].message == "command timed out (10s), daemon healthy"
        assert len(provider.dispatched) == 2

        # 2. Failure on Desktop #1 + daemon offline -> fast abort, no post-batch read hang.
        provider.dispatched.clear()
        reads_before = len(reads)
        section2 = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        reads_after_seed = len(reads)
        assert reads_after_seed == reads_before + 1
        provider.dispatch_action = lambda token, action, uuid: (  # type: ignore[method-assign]
            provider.dispatched.append((action, uuid)) or (_ for _ in ()).throw(_timeout_error())
        )
        provider.is_daemon_alive = lambda timeout=2.0, *, token=None: False  # type: ignore[attr-defined]
        plan2 = operations.create_desktop_plan(Action.STOP, items, section2, is_bulk=True)
        res_dead = operations.execute_desktop(
            "fake", Action.STOP, items, section2, is_bulk=True, plan=plan2
        )
        assert [t.state for t in res_dead.targets] == [
            OperationState.FAILED,
            OperationState.NOT_STARTED,
        ]
        assert res_dead.targets[1].message == DAEMON_OFFLINE_REASON
        assert len(provider.dispatched) == 1
        # Reconciliation read skipped because daemon was proven offline.
        assert len(reads) == reads_after_seed
    finally:
        collection.close()


# ------------------------------------------------ Task Board & TUI rendering


async def _wait_until(pilot, predicate, *, timeout: float = 3.0) -> bool:
    steps = max(1, int(timeout / 0.01))
    for _ in range(steps):
        if predicate():
            return True
        await pilot.pause(0.01)
    return predicate()


def test_task_footer_renders_skipped_in_muted_style_with_daemon_offline_detail(tmp_path) -> None:
    provider, collection, application, operations, sessions, settings = tui_runtime(tmp_path)
    operations._settings = replace(settings, max_inventory_age_seconds=30)
    provider.is_daemon_alive = lambda timeout=2.0, *, token=None: False  # type: ignore[attr-defined]
    provider.action_reply = PvmReply("failed", errno="146", message="error")

    palette = palette_for("truecolor", no_color=False)
    tui = PlaividTui(application, operations, sessions)
    tui._palette = palette

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.query_one("#select-all", Checkbox).value = True
            await pilot.pause(0.05)
            footer = tui.query_one("#task-footer", TaskViewFooter)
            footer._palette = palette
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value

            assert await _wait_until(
                pilot,
                lambda: len(footer._rows) == 2
                and all(r.status.is_terminal for r in footer._rows.values()),
            )
            records = [footer._rows[tid] for tid in footer._order]
            assert [r.status for r in records] == [TaskStatus.FAILED, TaskStatus.SKIPPED]
            skipped = records[1]
            assert skipped.started_at is None
            assert skipped.message == DAEMON_OFFLINE_REASON

            row_cells = footer.get_row(skipped.task_id)
            state_cell = str(row_cells[3])
            detail_cell = str(row_cells[4])
            assert "– SKIPPED" in state_cell
            assert "REJECTED" not in state_cell
            assert f"[{palette.muted}]" in state_cell
            assert detail_cell == DAEMON_OFFLINE_REASON

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_task_footer_keeps_second_target_queued_while_first_target_is_running(tmp_path) -> None:
    provider, collection, application, operations, sessions, settings = tui_runtime(tmp_path)
    operations._settings = replace(settings, max_inventory_age_seconds=30)

    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    release_second = threading.Event()
    original = provider.dispatch_action

    def gated_dispatch(token, action, uuid):
        if uuid == UUID_A:
            first_entered.set()
            release_first.wait(5)
        elif uuid == UUID_B:
            second_entered.set()
            release_second.wait(5)
        return original(token, action, uuid)

    provider.dispatch_action = gated_dispatch  # type: ignore[method-assign]
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.query_one("#select-all", Checkbox).value = True
            await pilot.pause(0.05)
            footer = tui.query_one("#task-footer", TaskViewFooter)
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value

            # Wait until VM #1 is actively inside dispatch_action and UI processed messages.
            assert await _wait_until(pilot, first_entered.is_set)
            assert await _wait_until(
                pilot,
                lambda: len(footer._rows) == 2
                and any(r.status is TaskStatus.RUNNING for r in footer._rows.values()),
            )
            by_uuid = {r.target.uuid: r for r in footer._rows.values()}
            assert by_uuid[UUID_A].status is TaskStatus.RUNNING
            assert by_uuid[UUID_A].started_at is not None
            # Crucial invariant: VM #2 is still QUEUED while VM #1 is running!
            assert by_uuid[UUID_B].status is TaskStatus.QUEUED
            assert by_uuid[UUID_B].started_at is None
            assert "· QUEUED" in str(footer.get_row(by_uuid[UUID_B].task_id)[3])

            # Release VM #1 -> VM #1 finishes SUCCEEDED and VM #2 enters RUNNING.
            release_first.set()
            assert await _wait_until(pilot, second_entered.is_set)
            assert await _wait_until(
                pilot,
                lambda: footer._rows[by_uuid[UUID_B].task_id].status is TaskStatus.RUNNING,
            )
            assert footer._rows[by_uuid[UUID_A].task_id].status is TaskStatus.SUCCEEDED
            assert footer._rows[by_uuid[UUID_B].task_id].status is TaskStatus.RUNNING

            # Release VM #2 -> both SUCCEEDED, timer stops.
            release_second.set()
            assert await _wait_until(
                pilot,
                lambda: all(r.status is TaskStatus.SUCCEEDED for r in footer._rows.values()),
            )
            assert footer.active_count() == 0
            assert footer._elapsed_timer is None

    try:
        asyncio.run(exercise())
    finally:
        release_first.set()
        release_second.set()
        collection.close()


def test_task_footer_displays_timeout_daemon_healthy_and_continues_to_vm2(tmp_path) -> None:
    provider, collection, application, operations, sessions, settings = tui_runtime(tmp_path)
    operations._settings = replace(settings, max_inventory_age_seconds=30, action_timeout=10.0)
    provider.is_daemon_alive = lambda timeout=2.0, *, token=None: True  # type: ignore[attr-defined]

    original = provider.dispatch_action

    def timeout_first(token, action, uuid):
        if uuid == UUID_A:
            provider.dispatched.append((action, uuid))
            raise _timeout_error()
        return original(token, action, uuid)

    provider.dispatch_action = timeout_first  # type: ignore[method-assign]
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.query_one("#select-all", Checkbox).value = True
            await pilot.pause(0.05)
            footer = tui.query_one("#task-footer", TaskViewFooter)
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value

            assert await _wait_until(
                pilot,
                lambda: len(footer._rows) == 2
                and all(r.status.is_terminal for r in footer._rows.values()),
            )
            by_uuid = {r.target.uuid: r for r in footer._rows.values()}
            assert by_uuid[UUID_A].status is TaskStatus.UNKNOWN
            assert "timed out (10s), daemon healthy" in by_uuid[UUID_A].message
            assert "timed out (10s)" in str(footer.get_row(by_uuid[UUID_A].task_id)[4])
            assert by_uuid[UUID_B].status is TaskStatus.SUCCEEDED

    try:
        asyncio.run(exercise())
    finally:
        collection.close()

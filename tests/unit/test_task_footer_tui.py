"""End-to-end task-board behaviour inside the real Textual application.

These exercise admission, deduplication, live footer rows, redaction, and the
session reset path against the fake provider (no PVM, no network).
"""

from __future__ import annotations

import asyncio
import threading

from textual.widgets import Footer, Select, Static

from plaivid_cli.domain.models import Action, OperationState, PvmReply
from plaivid_cli.domain.models.tasks import TargetRef
from plaivid_cli.presentation.tui.app import PlaividTui
from plaivid_cli.presentation.tui.components import TaskViewFooter
from tests.unit.test_cli_and_tui import UUID_A, UUID_B, runtime


def _footer(tui: PlaividTui) -> TaskViewFooter:
    return tui.query_one("#task-footer", TaskViewFooter)


def _cells(footer: TaskViewFooter, task_id: str) -> str:
    return " | ".join(str(cell) for cell in footer.get_row(task_id))


async def _wait_for(pilot, predicate, *, timeout: float = 3.0) -> bool:
    """Poll the app until ``predicate`` holds, instead of racing a fixed pause.

    Textual workers and message delivery are asynchronous; a fixed pause makes a
    test depend on machine load rather than on behaviour.
    """
    steps = max(1, int(timeout / 0.01))
    for _ in range(steps):
        if predicate():
            return True
        await pilot.pause(0.01)
    return predicate()


def _run(tui: PlaividTui, exercise, collection) -> None:
    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_footer_is_hidden_until_a_task_exists(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            footer = _footer(tui)
            assert footer.display is False
            assert footer.row_count == 0
            # The tuned layout is untouched while idle.
            assert tui.query_one(Footer).region.height == 1
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.query_one("#bulk-actions", Select).value = Action.START.value
            assert await _wait_for(pilot, lambda: footer.row_count == 1)
            assert footer.display is True
            assert tui.query_one(Footer).region.height == 1

    _run(tui, exercise, collection)


def test_dispatch_creates_a_succeeded_row_with_time_action_and_target(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            footer = _footer(tui)
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value
            assert await _wait_for(
                pilot,
                lambda: bool(footer._rows)
                and all(r.status.is_terminal for r in footer._rows.values()),
            )
            rows = footer._rows
            assert len(rows) == 1
            record = next(iter(rows.values()))
            assert record.key.action is Action.STOP
            assert record.target.uuid == UUID_A
            text = _cells(footer, record.task_id)
            assert "STOP" in text
            assert "SUCCEEDED" in text
            assert UUID_A[:8] in text
            # Task rows are terminal, so no clock is running and no row is live.
            assert footer.active_count() == 0
            assert tui.tasks.any_active() is False

    _run(tui, exercise, collection)


def test_duplicate_action_is_ignored_without_dispatch_or_extra_row(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            ref = TargetRef(UUID_A, "alpha")
            assert tui.tasks.admit(Action.START, (ref,), "op-seed") is not None
            tui.tasks.start("op-seed")
            footer = _footer(tui)
            assert await _wait_for(pilot, lambda: footer.row_count == 1)
            rows_before = footer.row_count
            dispatched_before = len(provider.dispatched)
            # A second identical request must be refused before dispatch.
            tui._begin_action(Action.START)
            await pilot.pause(0.25)
            assert len(provider.dispatched) == dispatched_before
            assert footer.row_count == rows_before
            status = str(tui.query_one("#action-status", Static).render()).lower()
            assert "already running" in status

    _run(tui, exercise, collection)


def test_conflicting_action_on_the_same_target_is_refused(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.tasks.admit(Action.START, (TargetRef(UUID_A, "alpha"),), "op-seed")
            tui.tasks.start("op-seed")
            await pilot.pause(0.05)
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value
            assert await _wait_for(
                pilot,
                lambda: "REFUSED" in str(tui.query_one("#action-status", Static).render()).upper(),
            )
            assert provider.dispatched == []
            status = str(tui.query_one("#action-status", Static).render()).upper()
            assert "REFUSED" in status

    _run(tui, exercise, collection)


def test_footer_renders_unknown_distinctly_from_failure(tmp_path) -> None:
    """An unestablished outcome must never be presented as a definite failure.

    Driven from the task board rather than through a provider race: the point
    under test is the rendering contract for ``TaskStatus.UNKNOWN``.
    """
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.tasks.admit(Action.KILL, (TargetRef(UUID_A, "alpha"),), "op-unknown")
            tui.tasks.start("op-unknown")
            await pilot.pause(0.05)
            tui.tasks.progress("op-unknown", UUID_A, OperationState.OUTCOME_UNKNOWN)
            await pilot.pause(0.05)
            footer = _footer(tui)
            record = next(iter(footer._rows.values()))
            text = _cells(footer, record.task_id)
            assert "UNKNOWN" in text
            assert "FAILED" not in text
            assert "reconcile" in text.lower()
            assert footer.active_count() == 0

    _run(tui, exercise, collection)


def test_stale_plan_after_admission_is_recorded_as_rejected(tmp_path) -> None:
    """A plan invalidated between admission and dispatch ends as a REJECTED row.

    This is the documented stale-plan path: the board must not leave the task
    stuck in QUEUED/RUNNING when the coordinator refuses to dispatch.
    """
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.tasks.admit(Action.START, (TargetRef(UUID_A, "alpha"),), "op-stale")
            tui.tasks.start("op-stale")
            tui.tasks.abandon("op-stale", "inventory changed after target selection")
            await pilot.pause(0.05)
            footer = _footer(tui)
            record = next(iter(footer._rows.values()))
            assert record.status.value == "REJECTED"
            assert footer.active_count() == 0
            assert tui.tasks.any_active() is False

    _run(tui, exercise, collection)


def test_failure_row_reports_redacted_detail(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            provider.action_reply = PvmReply(
                "failed", errno="13", message="password=synthetic-secret denied"
            )
            footer = _footer(tui)
            tui.query_one("#bulk-actions", Select).value = Action.STOP.value
            assert await _wait_for(
                pilot,
                lambda: bool(footer._rows)
                and all(r.status.is_terminal for r in footer._rows.values()),
            )
            record = next(iter(footer._rows.values()))
            text = _cells(footer, record.task_id)
            assert record.status.value == "FAILED"
            assert "synthetic-secret" not in text
            assert "FAILED" in text

    _run(tui, exercise, collection)


def test_running_task_shows_a_live_elapsed_clock(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    gate = threading.Event()
    entered = threading.Event()
    original = provider.dispatch_action

    def blocking_dispatch(token, action, uuid):
        entered.set()
        gate.wait(5)
        return original(token, action, uuid)

    provider.dispatch_action = blocking_dispatch  # type: ignore[method-assign]
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            tui.query_one("#bulk-actions", Select).value = Action.PAUSE.value
            # Wait until the worker is actually blocked inside dispatch.
            for _ in range(50):
                if entered.is_set():
                    break
                await pilot.pause(0.02)
            assert entered.is_set()
            footer = _footer(tui)
            # The worker entered dispatch, but its RUNNING message is delivered
            # asynchronously; wait for the board to catch up before asserting.
            for _ in range(100):
                rows = list(footer._rows.values())
                if rows and rows[0].status.value == "RUNNING":
                    break
                await pilot.pause(0.01)
            assert footer.active_count() == 1
            assert footer._elapsed_timer is not None
            record = next(iter(footer._rows.values()))
            assert record.status.value == "RUNNING"
            assert "PAUSE" in _cells(footer, record.task_id)
            gate.set()
            await pilot.pause(0.3)
            assert footer.active_count() == 0
            assert footer._elapsed_timer is None

    try:
        _run(tui, exercise, collection)
    finally:
        gate.set()


def test_session_reset_clears_the_board(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            footer = _footer(tui)
            tui.query_one("#bulk-actions", Select).value = Action.START.value
            assert await _wait_for(pilot, lambda: footer.row_count == 1)
            assert footer.display is True
            tui._session_ended("Local session cleared.")
            # The board clears synchronously through TaskManager.reset; the
            # TaskRegistryReset message is delivered on the next pump cycle.
            assert tui.tasks.any_active() is False
            assert len(tui.tasks) == 0
            assert await _wait_for(pilot, lambda: footer.row_count == 0)
            assert footer.display is False

    _run(tui, exercise, collection)


def test_late_worker_message_cannot_resurrect_a_cleared_row(tmp_path) -> None:
    """A worker event published before a reset must be discarded on arrival.

    Worker-thread messages go through loop.call_soon_threadsafe, so they can be
    delivered after a later same-thread message. Without the board epoch, a late
    TaskCompleted would re-create a row for a session that has already ended.
    """
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            footer = _footer(tui)
            stale = tui.tasks.admit(
                Action.START, (TargetRef(UUID_A, "alpha"),), "op-late"
            )
            assert stale is not None
            tui.tasks.start("op-late")
            assert await _wait_for(pilot, lambda: footer.row_count == 1)
            tui.tasks.reset("session ended")
            await pilot.pause(0.1)
            assert footer.row_count == 0
            # Emulate a straggler from the previous epoch.
            from plaivid_cli.presentation.tui.messages import TaskCompleted

            record = tui.tasks.history()
            assert record == ()
            late_record = _late_record()
            tui.post_message(TaskCompleted(late_record, epoch=0))
            await pilot.pause(0.1)
            assert footer.row_count == 0

    _run(tui, exercise, collection)


def _late_record():
    """A record from the pre-reset epoch, as a straggling worker would carry."""
    from datetime import UTC, datetime

    from plaivid_cli.domain.models import TaskStatus
    from plaivid_cli.domain.models.tasks import TaskKey, TaskRecord

    return TaskRecord(
        key=TaskKey(Action.START, UUID_A),
        target=TargetRef(UUID_A, "alpha"),
        operation_id="op-late",
        status=TaskStatus.SUCCEEDED,
        message="PVM accepted the command",
        finished_at=datetime.now(UTC),
    )


def test_footer_accepts_focus_and_scrolls(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            refs = tuple(TargetRef(uuid, f"vm{index}") for index, uuid in enumerate(
                [UUID_A, UUID_B], start=1
            ))
            tui.tasks.admit(Action.START, refs, "op-scroll")
            tui.tasks.start("op-scroll")
            await pilot.pause(0.1)
            footer = _footer(tui)
            assert footer.can_focus is True
            assert footer.row_count == 2
            footer.focus()
            await pilot.pause(0.05)
            assert tui.focused is footer
            await pilot.press("down")
            await pilot.pause(0.05)
            assert footer.cursor_row >= 0

    _run(tui, exercise, collection)


def test_admitted_but_unsubmitted_task_is_abandoned_by_reset(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.15)
            tui.tasks.admit(Action.STOP, (TargetRef(UUID_A, "alpha"),), "op-open")
            await pilot.pause(0.05)
            assert tui.tasks.any_active() is True
            tui._session_ended("Local session cleared.")
            assert tui.tasks.any_active() is False
            footer = _footer(tui)
            assert await _wait_for(pilot, lambda: footer.row_count == 0)

    _run(tui, exercise, collection)

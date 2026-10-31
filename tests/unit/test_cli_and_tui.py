from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

from textual.widgets import Select, TabbedContent

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication
from plaivid_cli.application.session import SessionManager, SessionStore
from plaivid_cli.cli import EXIT_OK, EXIT_REJECTED, EXIT_UNKNOWN, build_parser, run_command
from plaivid_cli.config import load_settings
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    HostMetrics,
    HostStatus,
    ObjectVM,
    ProcessObservation,
    PvmReply,
    PvmSession,
    SourceResult,
)
from plaivid_cli.domain.overview import DashboardSample, LocalHostSample, NicSample, PhysicalNic
from plaivid_cli.tui import PlaividTui

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"
UUID_B = "800b0429-d82a-4e26-a5e2-225990172e6e"


class FakeProvider:
    def __init__(self) -> None:
        self.dispatched: list[tuple[Action, str]] = []
        self.objects = (
            ObjectVM(UUID_A, "alpha", state="started"),
            ObjectVM(UUID_B, "beta", state="started"),
        )
        self.host_calls = 0
        self.local_calls = 0
        self.nic_calls = 0
        self.dashboard_calls = 0
        self.host_gate: threading.Event | None = None
        self.action_reply = PvmReply("success")
        self.logout_calls = 0

    def list_objects(self, token):
        return SourceResult(self.objects, CollectionStatus.CURRENT, "objects")

    def list_processes(self):
        return SourceResult(
            (ProcessObservation(UUID_A, pid=11), ProcessObservation(UUID_B, pid=22)),
            CollectionStatus.CURRENT,
            "processes",
        )

    def host_status(self, token):
        self.host_calls += 1
        if self.host_gate is not None:
            self.host_gate.wait(2)
        return SourceResult(HostStatus(name="node-a", sball_state="quorate"), CollectionStatus.CURRENT, "host")

    def host_metrics(self, token):
        return SourceResult(HostMetrics(cpu_pct=19.5), CollectionStatus.CURRENT, "metrics")

    def dashboard(self, token):
        self.dashboard_calls += 1
        return SourceResult(DashboardSample(host_name="node-a", host_id="host-1"), CollectionStatus.CURRENT, "dashboard")

    def local_host(self):
        self.local_calls += 1
        return SourceResult(LocalHostSample(hostname="node-a", cpu_percent=19.5, memory_used=512, memory_total=1024, load1=0.5), CollectionStatus.CURRENT, "local")

    def physical_nics(self, token):
        return SourceResult((PhysicalNic("eno1"), PhysicalNic("eno2")), CollectionStatus.CURRENT, "nics")

    def nic_samples(self, devices):
        self.nic_calls += 1
        return SourceResult(tuple(NicSample(name=nic.name, rx_bytes=12, tx_bytes=0) for nic in devices), CollectionStatus.CURRENT, "counters")

    def vm_detail(self, token, uuid):
        return SourceResult(None, CollectionStatus.UNAVAILABLE, "detail")

    def tap_mapping(self, token):
        return {}

    def dispatch_action(self, token, action, uuid):
        self.dispatched.append((action, uuid))
        return self.action_reply

    def validate_session(self, session):
        return True

    def login(self, username, password):
        return PvmSession(username, "synthetic-token")

    def logout(self, session):
        self.logout_calls += 1


class FakeAudit:
    def __init__(self) -> None:
        self.calls = 0

    def recent(self, limit):
        self.calls += 1
        return ()


def runtime(tmp_path: Path):
    settings = load_settings({"PLAIVID_STATE_DIR": str(tmp_path)})
    provider = FakeProvider()
    collection = CollectionCoordinator(provider, refresh_interval=100)
    audit = FakeAudit()
    provider.audit = audit
    application = PlaividApplication(provider, collection, settings, audit)
    operations = OperationCoordinator(provider, collection, settings)
    store = SessionStore(settings.session_file)
    store.save(PvmSession("operator", "synthetic-token"))
    sessions = SessionManager(provider, settings, store)
    return provider, collection, application, operations, sessions, settings


def test_cli_inventory_and_approval_gate_with_fake_provider(tmp_path, capsys):
    provider, collection, application, operations, sessions, settings = runtime(tmp_path)
    parser = build_parser()
    inventory_args = parser.parse_args(["inventory"])
    assert run_command(
        inventory_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == EXIT_OK
    assert "alpha" in capsys.readouterr().out
    json_args = parser.parse_args(["inventory", "--json"])
    assert run_command(
        json_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "current"
    assert payload["data"]["records"][0]["uuid"] == UUID_A
    assert payload["data"]["records"][0]["object"]["state"] == "started"

    stop_args = parser.parse_args(["stop", UUID_A])
    assert run_command(
        stop_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == EXIT_REJECTED
    assert provider.dispatched == []
    capsys.readouterr()

    stop_approved = parser.parse_args(["stop", UUID_A, "--approve", f"STOP {UUID_A}"])
    assert run_command(
        stop_approved,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == EXIT_OK
    output = capsys.readouterr().out
    assert "SUCCEEDED" in output
    assert provider.dispatched == [(Action.STOP, UUID_A)]

    provider.action_reply = PvmReply("maybe")
    unknown_args = parser.parse_args(["start", UUID_B])
    assert run_command(
        unknown_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == EXIT_UNKNOWN
    assert "OUTCOME_UNKNOWN" in capsys.readouterr().out
    assert provider.dispatched[-1] == (Action.START, UUID_B)
    collection.close()


def test_cli_redacts_sensitive_pvm_metadata_in_human_and_json_output(tmp_path, capsys):
    provider, collection, application, operations, sessions, settings = runtime(tmp_path)
    provider.objects = (ObjectVM(UUID_A, "token=synthetic-cli-secret", state="started"),)
    human_args = build_parser().parse_args(["inventory"])
    run_command(
        human_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    )
    human_output = capsys.readouterr().out
    assert "synthetic-cli-secret" not in human_output
    assert "token=[REDACTED]" in human_output

    json_args = build_parser().parse_args(["inventory", "--json"])
    run_command(
        json_args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    )
    json_output = capsys.readouterr().out
    assert "synthetic-cli-secret" not in json_output
    assert "token=[REDACTED]" in json_output
    collection.close()


def test_cli_json_preserves_partial_inventory_status_and_records(tmp_path, capsys):
    provider, collection, application, operations, sessions, settings = runtime(tmp_path)
    provider.list_processes = lambda: (_ for _ in ()).throw(RuntimeError("synthetic helper failure"))
    args = build_parser().parse_args(["inventory", "--json"])
    assert run_command(
        args,
        application=application,
        operations=operations,
        sessions=sessions,
        settings=settings,
    ) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "partial"
    assert payload["data"]["records"][0]["uuid"] == UUID_A
    assert "synthetic helper failure" not in str(payload)
    assert payload["error"]
    collection.close()


def test_tui_redacts_sensitive_pvm_names_and_descriptions(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (
        ObjectVM(
            UUID_A,
            "password=synthetic-tui-secret",
            state="started",
            description="token=synthetic-description-secret",
        ),
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.2)
            visible = str(tui.query_one("#fleet-table").render())
            detail = str(tui.query_one("#detail-box").render())
            assert "synthetic-tui-secret" not in visible + detail
            assert "synthetic-description-secret" not in visible + detail
            assert "[REDACTED]" in detail
            row = tui.query_one("#fleet-table").get_row(UUID_A)
            assert "synthetic-tui-secret" not in str(row[1])
            assert "[REDACTED]" in str(row[1])

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_tui_selection_is_retained_by_uuid_when_inventory_order_changes(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.15)
            table = tui.query_one("#fleet-table")
            table.move_cursor(row=1)
            await pilot.pause(0.05)
            assert tui._selected_uuid == UUID_B
            provider.objects = (
                ObjectVM(UUID_A, "zulu", state="started"),
                ObjectVM(UUID_B, "aardvark", state="started"),
            )
            tui._request_refresh()
            await pilot.pause(0.15)
            assert tui._selected_uuid == UUID_B
            assert table.cursor_row == 0

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_tui_navigation_remains_responsive_during_slow_collection(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    gate = threading.Event()
    provider.host_gate = gate
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.1)
            tabs = tui.query_one("#tabs", TabbedContent)
            assert tabs.active == "overview"
            await pilot.pause(0.05)
            assert provider.host_calls == 1
            tabs.active = "fleet"
            await pilot.pause(0.05)
            assert tabs.active == "fleet"
            gate.set()
            await pilot.pause(0.15)
            assert provider.host_calls == 1

    try:
        asyncio.run(exercise())
    finally:
        gate.set()
        collection.close()


def test_tui_blocks_duplicate_operation_and_logout_while_operation_is_active(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.15)
            tui._operation_active = True
            tui._begin_action(Action.START)
            tui.submit_logout()
            await pilot.pause(0.05)
            assert provider.dispatched == []
            assert provider.logout_calls == 0
            assert "already in progress" in str(tui.query_one("#action-status").render())

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_tui_bulk_action_dropdown_dispatches_directly_and_resets(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.15)
            assert not list(tui.query("#controls"))
            assert not list(tui.query("#start"))
            dropdown = tui.query_one("#bulk-actions", Select)
            dropdown.value = Action.STOP.value
            await pilot.pause(0.2)
            assert not any(type(screen).__name__ == "ConfirmScreen" for screen in tui.screen_stack)
            assert [action for action, _ in provider.dispatched] == [Action.STOP]
            assert "SUCCEEDED" in str(tui.query_one("#action-status").render())
            assert not isinstance(dropdown.value, str)

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_tui_mounts_dashboard_using_only_fake_local_provider(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.2)
            assert tui.query_one("#vm-count").render() == "2"
            assert tui.query_one("#tabs", TabbedContent).active == "overview"
            assert "node-a" in str(tui.query_one("#host-identity").render())
            tui.query_one("#tabs", TabbedContent).active = "fleet"
            tui.show_audit()
            await pilot.pause(0.1)
            assert "No audit rows" in str(tui.query_one("#audit-panel").render())
            first_audit_reads = provider.audit.calls
            assert first_audit_reads >= 1
            await pilot.pause(0.2)
            assert provider.audit.calls == first_audit_reads
            assert "operator" in str(tui.query_one("#session-label").render())

    try:
        asyncio.run(exercise())
    finally:
        collection.close()

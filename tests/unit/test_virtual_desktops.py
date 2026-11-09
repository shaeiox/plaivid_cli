"""Synthetic Desktop fixtures: not evidence of a PVM action protocol."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET

import pytest
from test_cli_and_tui import UUID_A, UUID_B, runtime
from textual.widgets import Checkbox, DataTable, Input, Select, Static, TabbedContent

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.models import Action, CollectionStatus, SourceResult
from plaivid_cli.infrastructure.process import ProcessResult
from plaivid_cli.infrastructure.pvm.adapter import DESKTOP_QUERY, LocalPvmAdapter
from plaivid_cli.infrastructure.pvm.desktops import parse_virtual_desktops
from plaivid_cli.infrastructure.pvm.sbell import SbellClient
from plaivid_cli.presentation.tui.app import PlaividTui


def description(*objects: str) -> ET.Element:
    return ET.fromstring("<description><sball-config><objects>" + "".join(objects) + "</objects></sball-config></description>")


def obj(uuid: str, name: str, *, kind: str = "pvm_desktop_lite_virtual_desktop") -> str:
    return (f"<pvm_desktop_obj><type>{kind}</type><uuid>{uuid}</uuid><name>{name}</name>"
            "<is_enabled>yes</is_enabled><virtual_machine><local_status>running</local_status>"
            "<cluster><cluster_status><status>started</status></cluster_status></cluster>"
            "<hardware><cpu><vcpu><socket>1</socket><core>2</core><thread>2</thread>"
            "</vcpu></cpu><memory><size>2048</size></memory></hardware>"
            "</virtual_machine></pvm_desktop_obj>")


def test_desktop_parser_multiple_empty_duplicates_and_independent_states() -> None:
    result = parse_virtual_desktops(description(obj(UUID_A, "alpha"), obj(UUID_B, "beta"),
                                                obj(UUID_A, "vm", kind="pvm_vmm_virtual_machine")))
    assert result.status is CollectionStatus.CURRENT
    assert len(result.value) == 2
    first = result.value[0]
    assert first.uuid == UUID_A
    assert (first.enabled, first.local_status, first.cluster_status) == ("yes", "running", "started")
    assert first.vcpu == 4
    assert first.memory_size_raw == "2048"  # No inferred MB unit.
    assert parse_virtual_desktops(description()).value == ()
    assert parse_virtual_desktops(ET.fromstring("<description/>")).status is CollectionStatus.UNAVAILABLE
    duplicate = parse_virtual_desktops(description(obj(UUID_A, "alpha"), obj(UUID_A, "other"), obj("invalid", "bad")))
    assert duplicate.status is CollectionStatus.PARTIAL and duplicate.value == ()
    assert len(duplicate.quality_issues) == 2


def test_adapter_one_batched_read_with_exact_query_and_token() -> None:
    class Runner:
        def __init__(self):
            self.calls = []

        def run(self, argv, *, timeout=None):
            self.calls.append(tuple(argv))
            payload = ET.tostring(description(obj(UUID_A, "a"), obj(UUID_B, "b")), encoding="unicode")
            return ProcessResult(0, f"<response><status>success</status>{payload}</response>", "", False, False, 0.01)

    runner = Runner()
    adapter = LocalPvmAdapter(SbellClient(("sbell",), runner), runner, ("pvm-running-vms",), allow_credential_argv=True)
    result = adapter.list_desktops("fake-session")
    assert len(result.value) == 2
    assert runner.calls == [("sbell", "user", "objects", DESKTOP_QUERY, "fake-session")]


def test_collection_last_good_and_one_read_per_refresh() -> None:
    class Provider:
        def __init__(self):
            self.calls = 0

        def list_desktops(self, token):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("synthetic failure")
            return SourceResult((VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta")),
                                CollectionStatus.CURRENT, "user/objects/desktops")

    provider = Provider()
    collection = CollectionCoordinator(provider)
    try:
        current = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        assert current.status is CollectionStatus.CURRENT and len(current.value) == 2
        stale = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        assert stale.status is CollectionStatus.STALE and len(stale.last_good_value) == 2
        assert provider.calls == 2
        collection.clear_desktop_session()
        assert collection.snapshot.section("desktops") is None
        fresh = collection.collect_once("new-session", sections=("desktops",)).section("desktops")
        assert fresh.status is CollectionStatus.CURRENT
        assert provider.calls == 3
    finally:
        collection.close()


@pytest.mark.parametrize("width", [80, 120])
def test_page_search_uuid_selection_and_direct_action(tmp_path, width) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.desktop_calls = 0

    def list_desktops(token):
        provider.desktop_calls += 1
        return SourceResult((VirtualDesktop(UUID_A, "alpha", enabled="yes"),
                             VirtualDesktop(UUID_B, "beta", cluster_status="started")),
                            CollectionStatus.CURRENT, "user/objects/desktops")

    provider.list_desktops = list_desktops
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test(size=(width, 30)) as pilot:
            # Switch tabs only once the initial overview collection has
            # settled. Otherwise the Desktop demand raised by tab activation is
            # dropped while the read lane is busy and is re-issued on a later
            # tick, which would race this "one read, no polling" assertion.
            for _ in range(300):
                if tui._inventory is not None and not tui._refresh_busy:
                    break
                await pilot.pause(0.01)
            tui.query_one("#tabs", TabbedContent).active = "desktops"
            for _ in range(300):
                if provider.desktop_calls:
                    break
                await pilot.pause(0.01)
            await pilot.pause(0.2)
            assert provider.desktop_calls == 1
            from textual.containers import Horizontal, Vertical
            from textual.widgets import Button

            assert tui.query_one("#desktop-summary", Horizontal).styles.height == tui.query_one("#fleet-summary", Horizontal).styles.height
            assert tui.query_one("#desktop-refresh", Button).styles.width == tui.query_one("#refresh-button", Button).styles.width
            assert tui.query_one("#desktop-actions", Select).styles.width == tui.query_one("#bulk-actions", Select).styles.width
            assert tui.query_one("#desktop-list", Vertical).styles.height == tui.query_one("#vm-list", Vertical).styles.height
            assert [node.id for node in tui.query_one("#desktop-toolbar", Horizontal).children][:3] == ["desktop-actions", "desktop-all", "desktop-audit-toggle"]
            assert str(tui.query_one("#desktop-count", Static).render()) == "2"
            table = tui.query_one("#desktop-table", DataTable)
            assert table.row_count == 2
            table.move_cursor(row=1)
            await pilot.pause(0.05)
            assert tui._desktop_selected == UUID_B
            tui.query_one("#desktop-search", Input).value = "beta"
            await pilot.pause(0.05)
            assert table.row_count == 1 and tui._desktop_selected == UUID_B
            tui.query_one("#desktop-all", Checkbox).value = True
            await pilot.pause(0.05)
            assert "2 target(s)" in str(tui.query_one("#desktop-scope", Static).render())
            assert UUID_A in str(tui.query_one("#desktop-detail", Static).render())
            # All-target action is denied before transport without a positive age bound.
            tui.query_one("#desktop-actions", Select).value = Action.START.value
            await pilot.pause(0.05)
            assert "PLAIVID_MAX_INVENTORY_AGE_SECONDS" in str(tui.query_one("#desktop-action-status", Static).render())
            tui.query_one("#desktop-all", Checkbox).value = False
            await pilot.pause(0.05)
            tui.query_one("#desktop-actions", Select).value = Action.START.value
            await pilot.pause(0.25)
            assert provider.dispatched == [(Action.START, UUID_B)]
            assert "SUCCEEDED" in str(tui.query_one("#desktop-action-status", Static).render())
            calls_before_refresh = provider.desktop_calls
            tui._request_refresh()
            await pilot.pause(0.15)
            assert provider.desktop_calls > calls_before_refresh and tui._desktop_selected == UUID_B
            tui._session_ended("test logout")
            assert table.row_count == 0 and tui._desktop_section is None

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_inflight_desktop_read_cannot_publish_after_session_change() -> None:
    import threading

    entered = threading.Event()
    release = threading.Event()

    class Provider:
        def list_desktops(self, token):
            if token == "old":
                entered.set()
                release.wait(2)
            return SourceResult((VirtualDesktop(UUID_A, token),), CollectionStatus.CURRENT,
                                "user/objects/desktops")

    collection = CollectionCoordinator(Provider())
    try:
        first = collection.request_refresh("old", sections=("desktops",))
        assert entered.wait(2)
        collection.clear_desktop_session()
        release.set()
        assert first.result(timeout=2).section("desktops") is None
        fresh = collection.collect_once("new", sections=("desktops",)).section("desktops")
        assert fresh.value[0].name == "new"
    finally:
        release.set()
        collection.close()


def test_desktop_operation_selected_and_bulk_fail_closed(tmp_path) -> None:

    from plaivid_cli.domain.errors import AppError
    from plaivid_cli.domain.models import PvmReply

    provider, collection, _, operations, _, settings = runtime(tmp_path)
    items = (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta"))
    provider.list_desktops = lambda token: SourceResult(items, CollectionStatus.CURRENT, "desktops")
    provider.action_reply = PvmReply("success")
    section = collection.collect_once("fake", sections=("desktops",)).section("desktops")
    try:
        plan = operations.create_desktop_plan(Action.START, (items[0],), section, is_bulk=False)
        with pytest.raises(AppError, match="bulk Desktop actions need"):
            operations.create_desktop_plan(Action.START, items, section, is_bulk=True)
        with pytest.raises(AppError, match="bulk Desktop actions need"):
            operations.create_desktop_plan(Action.START, (items[0],), section, is_bulk=True)
        result = operations.execute_desktop("fake", Action.START, (items[0],), section,
                                            is_bulk=False, plan=plan)
        assert result.targets[0].uuid == UUID_A
        assert provider.dispatched == [(Action.START, UUID_A)]
        # The old generation cannot be reused after reconciliation.
        with pytest.raises(AppError, match="current Desktop inventory"):
            operations.create_desktop_plan(Action.START, (items[0],), section, is_bulk=False)
        assert collection.snapshot.section("inventory") is None
    finally:
        collection.close()


def test_desktop_bulk_stops_on_failure_and_reconciles_once(tmp_path) -> None:
    from dataclasses import replace

    from plaivid_cli.domain.models import OperationState, PvmReply

    provider, collection, _, operations, _, settings = runtime(tmp_path)
    items = (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta"))
    reads = []

    def list_desktops(token):
        reads.append(token)
        return SourceResult(items, CollectionStatus.CURRENT, "desktops")

    provider.list_desktops = list_desktops
    operations._settings = replace(settings, max_inventory_age_seconds=30)
    section = collection.collect_once("fake", sections=("desktops",)).section("desktops")
    provider.action_reply = PvmReply("failed", errno="146", message="rejected")
    try:
        plan = operations.create_desktop_plan(Action.START, items, section, is_bulk=True)
        result = operations.execute_desktop("fake", Action.START, items, section,
                                            is_bulk=True, plan=plan)
        assert [item.state for item in result.targets] == [OperationState.FAILED, OperationState.NOT_STARTED]
        assert provider.dispatched == [(Action.START, UUID_A)]
        assert reads == ["fake", "fake"]
    finally:
        collection.close()


def test_desktop_start_dispatches_on_selection_without_dialog(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.list_desktops = lambda token: SourceResult(
        (VirtualDesktop(UUID_A, "alpha"),), CollectionStatus.CURRENT, "desktops"
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test() as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs", TabbedContent).active = "desktops"
            await pilot.pause(0.2)
            tui.query_one("#desktop-actions", Select).value = Action.START.value
            await pilot.pause(0.25)
            assert provider.dispatched == [(Action.START, UUID_A)]
            assert "SUCCEEDED" in str(tui.query_one("#desktop-action-status", Static).render())

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_desktop_rejects_partial_stale_and_changed_target_set(tmp_path) -> None:
    from dataclasses import replace

    from plaivid_cli.domain.errors import AppError

    provider, collection, _, operations, _, settings = runtime(tmp_path)
    items = (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta"))
    provider.list_desktops = lambda token: SourceResult(items, CollectionStatus.PARTIAL, "desktops",
                                                        quality_issues=("bad row",))
    operations._settings = replace(settings, max_inventory_age_seconds=30)
    try:
        partial = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        with pytest.raises(AppError, match="complete current"):
            operations.create_desktop_plan(Action.STOP, items, partial, is_bulk=True)
        provider.list_desktops = lambda token: SourceResult(items, CollectionStatus.CURRENT, "desktops")
        current = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        subset = operations.create_desktop_plan(Action.STOP, (items[1],), current, is_bulk=True)
        assert subset.target_uuids == (UUID_B,)
        plan = operations.create_desktop_plan(Action.STOP, items, current, is_bulk=True)
        collection.collect_once("fake", sections=("desktops",))
        with pytest.raises(AppError, match="current Desktop inventory"):
            operations.execute_desktop("fake", Action.STOP, items, current,
                                       is_bulk=True, plan=plan)
        assert provider.dispatched == []
    finally:
        collection.close()


def test_desktop_bulk_unknown_stops_and_marks_remaining_unattempted(tmp_path) -> None:
    from dataclasses import replace

    from plaivid_cli.domain.models import OperationState, PvmReply

    provider, collection, _, operations, _, settings = runtime(tmp_path)
    items = (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta"))
    provider.list_desktops = lambda token: SourceResult(items, CollectionStatus.CURRENT, "desktops")
    provider.action_reply = PvmReply("unexpected")
    operations._settings = replace(settings, max_inventory_age_seconds=30)
    try:
        section = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        plan = operations.create_desktop_plan(Action.START, items, section, is_bulk=True)
        result = operations.execute_desktop("fake", Action.START, items, section,
                                            is_bulk=True, plan=plan)
        assert result.state is OperationState.OUTCOME_UNKNOWN
        assert [item.state for item in result.targets] == [OperationState.OUTCOME_UNKNOWN, OperationState.NOT_STARTED]
        assert provider.dispatched == [(Action.START, UUID_A)]
    finally:
        collection.close()




@pytest.mark.parametrize("action", list(Action))
def test_every_desktop_action_reaches_fake_gateway(tmp_path, action) -> None:
    from plaivid_cli.domain.models import PvmReply

    provider, collection, _, operations, _, _ = runtime(tmp_path)
    item = VirtualDesktop(UUID_A, "alpha")
    provider.list_desktops = lambda token: SourceResult((item,), CollectionStatus.CURRENT, "desktops")
    provider.action_reply = PvmReply("success")
    try:
        section = collection.collect_once("fake", sections=("desktops",)).section("desktops")
        plan = operations.create_desktop_plan(action, (item,), section, is_bulk=False)
        assert provider.dispatched == []
        result = operations.execute_desktop("fake", action, (item,), section,
                                            is_bulk=False, plan=plan)
        assert result.targets[0].uuid == UUID_A
        assert provider.dispatched == [(action, UUID_A)]
    finally:
        collection.close()


def test_desktop_ui_all_targets_ignores_search_without_confirmation(tmp_path) -> None:
    from dataclasses import replace

    provider, collection, application, operations, sessions, settings = runtime(tmp_path)
    operations._settings = replace(settings, max_inventory_age_seconds=30)
    provider.list_desktops = lambda token: SourceResult(
        (VirtualDesktop(UUID_A, "alpha"), VirtualDesktop(UUID_B, "beta")),
        CollectionStatus.CURRENT, "desktops",
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 30)) as pilot:
            await pilot.pause(0.15)
            tui.query_one("#tabs", TabbedContent).active = "desktops"
            # Wait for the Desktop roster instead of a fixed pause: with nothing
            # loaded there is no target to act on and the assertion below would
            # fail for a timing reason rather than a behaviour one.
            for _ in range(300):
                if len(tui._desktops) == 2:
                    break
                await pilot.pause(0.01)
            assert len(tui._desktops) == 2
            tui.query_one("#desktop-search", Input).value = "beta"
            tui.query_one("#desktop-all", Checkbox).value = True
            tui.query_one("#desktop-actions", Select).value = Action.START.value
            await pilot.pause(0.1)
            await pilot.pause(0.3)
            assert provider.dispatched == [(Action.START, UUID_A), (Action.START, UUID_B)]

    try:
        asyncio.run(exercise())
    finally:
        collection.close()

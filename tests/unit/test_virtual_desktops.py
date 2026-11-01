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
from plaivid_cli.tui import PlaividTui


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
def test_page_search_uuid_selection_and_all_actions_blocked(tmp_path, width) -> None:
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
            await pilot.pause(0.15)
            tui.query_one("#tabs", TabbedContent).active = "desktops"
            await pilot.pause(0.25)
            assert provider.desktop_calls == 1
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
            for action in Action:
                tui.query_one("#desktop-actions", Select).value = action.value
                await pilot.pause(0.02)
                assert "blocked" in str(tui.query_one("#desktop-action-status", Static).render())
            tui.query_one("#desktop-all", Checkbox).value = False
            await pilot.pause(0.05)
            for action in Action:
                tui.query_one("#desktop-actions", Select).value = action.value
                await pilot.pause(0.02)
            assert provider.dispatched == []
            tui._request_refresh()
            await pilot.pause(0.15)
            assert provider.desktop_calls == 2 and tui._desktop_selected == UUID_B
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

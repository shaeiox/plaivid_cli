"""Monitoring contracts; all PVM responses are synthetic, never host captures."""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from test_cli_and_tui import runtime
from textual.widgets import Input, TabbedContent

from plaivid_cli.application.overview import OverviewSchedule, health
from plaivid_cli.domain.models import CollectionStatus, SectionSnapshot
from plaivid_cli.domain.overview import PhysicalNic
from plaivid_cli.infrastructure.local_monitor import LinuxMonitor
from plaivid_cli.infrastructure.pvm.adapter import DASHBOARD_QUERY
from plaivid_cli.infrastructure.pvm.overview import parse_dashboard, parse_nic_list
from plaivid_cli.tui import PlaividTui


def test_schedule_is_single_flight_cadenced_and_discovery_is_one_shot():
    scheduler = OverviewSchedule()
    scheduler.enter()
    first = scheduler.due(now=100)
    assert first.count("physical_nics") == 1
    assert first.count("dashboard") == 1
    assert not scheduler.due(now=101)
    scheduler.finished()
    assert not scheduler.due(now=101)
    assert scheduler.due(now=103) == ("local_host", "nic_samples")
    scheduler.finished()
    scheduler.leave()
    assert not scheduler.due(now=120)
    scheduler.enter()
    assert "physical_nics" not in scheduler.due(now=120)
    scheduler.finished()
    scheduler.set_interval(5)
    assert scheduler.interval == 5
    for invalid in (0, 0.5, 61, float("nan")):
        try:
            scheduler.set_interval(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid interval {invalid}")
    assert scheduler.interval == 5


def test_heartbeat_uses_success_timestamps_and_does_not_animate_success():
    instant = datetime.now(UTC)
    section = SectionSnapshot(
        "dashboard", object(), object(), CollectionStatus.CURRENT, instant, instant, 1,
        attempted_monotonic=100, succeeded_monotonic=100, latency_seconds=0.15,
    )
    assert health(section, 3, now=100).status == "ONLINE"
    assert health(section, 3, now=107).status == "WARNING"
    assert health(section, 3, now=140).status == "OFFLINE"
    assert health(section, 3, now=140).last_success == health(section, 3, now=100).last_success
    assert health(section, 3, now=100).latency == .15
    failed = SectionSnapshot("dashboard", None, None, CollectionStatus.UNAVAILABLE, instant, None, 2, attempted_monotonic=100)
    assert health(failed, 3, now=100).status == "WARNING"
    assert health(failed, 3, now=140).status == "OFFLINE"


def test_dashboard_query_preserves_requested_shape_and_parser_refuses_unverified_vdi():
    root = ET.fromstring(DASHBOARD_QUERY)
    assert root.findtext("query_path") == "/plaivid/overview/pvm_overview_dashboard"
    assert root.findtext("page_size") == "0"
    assert root.findtext("requested_page") == "1"
    description = ET.fromstring("<description><host_list><host_dashboard><name>node-a</name><id>42</id><average>17</average></host_dashboard></host_list><storage_list><pool><name>pool-a</name></pool></storage_list></description>")
    sample = parse_dashboard(description).value
    assert sample is not None
    assert sample.host_name == "node-a" and sample.host_id == "42"
    assert sample.vdis == ()
    assert parse_nic_list(ET.fromstring("<description><unverified/></description>")).status is CollectionStatus.UNSUPPORTED
    assert parse_nic_list(ET.fromstring("<description><nic_list><nic><device>eno1</device></nic></nic_list></description>")).value is None


def test_local_linux_cpu_memory_and_all_nic_rates_without_fabricating_missing_data(tmp_path):
    proc = tmp_path / "proc"
    net = tmp_path / "sys" / "class" / "net"
    proc.mkdir()
    for name in ("eno1", "eno2"):
        (net / name / "device").mkdir(parents=True)
        (net / name / "statistics").mkdir()
        (net / name / "operstate").write_text("up")
        for key, value in {"rx_bytes": 100, "tx_bytes": 10, "rx_packets": 0}.items():
            (net / name / "statistics" / key).write_text(str(value))
    (proc / "stat").write_text("cpu  20 0 10 70 0 0 0\n")
    (proc / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
    (proc / "loadavg").write_text("0.10 0.20 0.30 1/100 42\n")
    (proc / "uptime").write_text("120.5 80.2\n")
    monitor = LinuxMonitor(proc, net)
    first = monitor.host()
    assert first.cpu_percent is None and first.memory_used == 750 * 1024
    (proc / "stat").write_text("cpu  30 0 10 160 0 0 0\n")
    assert monitor.host().cpu_percent == 10
    devices = (PhysicalNic("eno1"), PhysicalNic("eno2"), PhysicalNic("../invalid"))
    assert monitor.physical("../invalid") is False
    baseline = monitor.nics(devices)
    assert len(baseline) == 2 and all(sample.rx_bytes_per_second is None for sample in baseline)
    time.sleep(.01)
    for name in ("eno1", "eno2"):
        (net / name / "statistics" / "rx_bytes").write_text("200")
    measured = monitor.nics(devices)
    assert len(measured) == 2 and all(sample.rx_bytes_per_second > 0 for sample in measured)
    (net / "eno1" / "statistics" / "rx_bytes").write_text("5")
    assert monitor.nics(devices)[0].rx_bytes_per_second is None
    assert measured[0].rx_errors is None and measured[0].rx_crc_errors is None


def test_overview_navigation_interval_nic_tabs_and_vm_operations_remain_available(tmp_path):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test(size=(80, 35)) as pilot:
            await pilot.pause(.2)
            assert tui.query_one("#tabs", TabbedContent).active == "overview"
            assert "Refresh: 3s" in str(tui.query_one("#refresh-label").render())
            assert "RUNNING VMS" in str(tui.query_one("#running-card").render())
            assert "eno2" in tui._nic_tab_names
            tui._nic_selected = "eno2"
            tui._render_overview(collection.snapshot)
            assert provider.nic_calls == 1
            tui.query_one("#interval-input", Input).value = "5"
            tui.apply_interval()
            assert tui._overview_schedule.interval == 5
            assert "Refresh: 5s" in str(tui.query_one("#refresh-label").render())
            tui.query_one("#interval-input", Input).value = "0"
            tui.apply_interval()
            assert tui._overview_schedule.interval == 5
            tui.action_vms_page()
            assert tui.query_one("#tabs", TabbedContent).active == "fleet"
            tui.action_overview_page()
            assert tui.query_one("#tabs", TabbedContent).active == "overview"
            assert not tui._overview_schedule.busy or tui._refresh_busy
            await pilot.pause(.1)
            assert provider.nic_calls <= 2
    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_resize_and_repeated_navigation_do_not_duplicate_pending_collection(tmp_path):
    import threading

    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    gate = threading.Event()
    provider.host_gate = gate
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test(size=(80, 35)) as pilot:
            await pilot.pause(.1)
            assert provider.host_calls == 1
            assert tui._refresh_busy
            for _ in range(3):
                tui.action_vms_page()
                tui.action_overview_page()
                tui._tick()
            assert provider.host_calls == 1
            assert tui._refresh_busy
            await pilot.resize_terminal(120, 40)
            tui._tick()
            assert "wide" in tui.query_one("#shell").classes
            await pilot.resize_terminal(80, 35)
            tui._tick()
            assert "wide" not in tui.query_one("#shell").classes
            gate.set()
            await pilot.pause(.2)
            assert provider.host_calls == 1
            assert tui._refresh_busy is False

    try:
        asyncio.run(exercise())
    finally:
        gate.set()
        collection.close()


def test_logout_clears_old_vm_and_monitoring_values_before_next_login(tmp_path):
    from plaivid_cli.domain.models import PvmSession

    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test() as pilot:
            await pilot.pause(.2)
            assert tui._inventory is not None
            assert "node-a" in str(tui.query_one("#host-identity").render())
            tui._session_ended("Signed out")
            assert tui._inventory is None and tui._selected_uuid is None
            assert not tui._overview_schedule.active
            assert "node-a" not in str(tui.query_one("#host-identity").render())
            tui._session_ready(PvmSession("second", "second-synthetic-token"))
            assert tui._inventory is None  # old session cannot authorize a VM action
            assert "node-a" not in str(tui.query_one("#host-identity").render())
            await pilot.pause(.2)
            assert tui._inventory is not None
            assert tui.query_one("#tabs", TabbedContent).active == "overview"

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_unsupported_rediscovery_keeps_last_nic_value_but_marks_it_stale(tmp_path):
    from plaivid_cli.domain.models import SourceResult

    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    try:
        original = application.refresh("synthetic-token", sections=("physical_nics",)).section("physical_nics")
        assert original.status is CollectionStatus.CURRENT
        provider.physical_nics = lambda token: SourceResult(
            None, CollectionStatus.UNSUPPORTED, "network/nic-list"
        )
        stale = application.refresh("synthetic-token", sections=("physical_nics",)).section("physical_nics")
        assert stale.status is CollectionStatus.STALE
        assert stale.value is None and stale.last_good_value == original.value
        assert stale.succeeded_at == original.succeeded_at
        assert health(stale, float("inf")).status == "WARNING"
    finally:
        collection.close()


def test_manual_refresh_during_slow_read_coalesces_one_pending_request(tmp_path):
    import threading

    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    gate = threading.Event()
    provider.host_gate = gate
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test() as pilot:
            await pilot.pause(.1)
            assert provider.host_calls == 1
            for _ in range(5):
                tui._request_refresh()
            assert tui._pending_manual_refresh is True
            gate.set()
            await pilot.pause(.3)
            assert provider.host_calls == 2
            assert tui._pending_manual_refresh is False

    try:
        asyncio.run(exercise())
    finally:
        gate.set()
        collection.close()


def test_unchanged_vm_rows_are_updated_without_clearing_table(tmp_path):
    from unittest.mock import patch

    from textual.widgets import DataTable

    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise():
        async with tui.run_test() as pilot:
            await pilot.pause(.2)
            table = tui.query_one("#fleet-table", DataTable)
            with patch.object(table, "clear", wraps=table.clear) as clear:
                tui.action_vms_page()
                await pilot.pause(.15)
                assert table.row_count == 2
                assert clear.call_count == 0
                tui._request_refresh()
                await pilot.pause(.15)
                assert clear.call_count == 0

    try:
        asyncio.run(exercise())
    finally:
        collection.close()

"""Presentation-only checks for the structured selected-VM detail pane."""

from __future__ import annotations

import asyncio
import io
import threading

from rich.console import Console, RenderableType
from rich.text import Text
from test_cli_and_tui import UUID_A, UUID_B, runtime
from textual.containers import VerticalScroll
from textual.widgets import Static
from tui_plain import plain

from plaivid_cli.domain.models import (
    CollectionStatus,
    ConsoleInfo,
    DiskInfo,
    NicInfo,
    ObjectVM,
    ProcessObservation,
    SourceResult,
    VMDetail,
    VMRecord,
    describe_host,
    resolve_console_port,
)
from plaivid_cli.domain.overview import LocalHostSample
from plaivid_cli.presentation.theme import (
    NO_COLOR,
    TRUECOLOR,
    state_badge,
    state_colour,
    state_text,
)
from plaivid_cli.presentation.tui.app import PlaividTui
from plaivid_cli.presentation.tui.pages.virtual_machines.components.details import (
    build_detail_placeholder,
    build_vm_detail,
)


def _render(renderable: RenderableType, *, width: int = 120) -> str:
    if isinstance(renderable, Text):
        return renderable.plain
    buffer = io.StringIO()
    Console(file=buffer, width=width, color_system=None).print(renderable)
    return buffer.getvalue()


def _record(**overrides: object) -> VMRecord:
    values: dict[str, object] = {
        "uuid": UUID_A,
        "name": "web-prod-01",
        "state": "stopped",
        "vcpu": 4,
        "mem_mb": 8192,
        "description": "Primary reverse proxy for the public edge.",
        "host": None,
        "configured_port": None,
        "process_port": None,
    }
    values.update(overrides)
    return VMRecord(
        ObjectVM(
            str(values["uuid"]),
            str(values["name"]),
            state=str(values["state"]),
            vcpu=values["vcpu"],  # type: ignore[arg-type]
            mem_mb=values["mem_mb"],  # type: ignore[arg-type]
            description=str(values["description"]),
            configured_port=values["configured_port"],  # type: ignore[arg-type]
            host=values["host"],  # type: ignore[arg-type]
        ),
        ProcessObservation(
            str(values["uuid"]), pid=4242, port=values["process_port"]  # type: ignore[arg-type]
        ),
    )


def _detail(
    uuid: str = UUID_A, *, host: str = "node-7", port: int | None = 5900
) -> VMDetail:
    return VMDetail(
        uuid,
        "web-prod-01",
        "stopped",
        host=host,
        machine="pc-q35-6.2",
        cpu_model="EPYC 7443",
        vcpu_topology="4/1/1",
        disks=(DiskInfo("vda"), DiskInfo("vdb")),
        nics=(NicInfo("eth0"),),
        console=ConsoleInfo(kind="vnc", port=port),
    )


def test_state_colour_is_the_single_classification_for_text_and_badges() -> None:
    expected = {
        "started": TRUECOLOR.success,
        "Running": TRUECOLOR.success,
        "stopped": TRUECOLOR.error,
        "off": TRUECOLOR.error,
        "failed": TRUECOLOR.error,
        "paused": TRUECOLOR.warning,
        "starting": TRUECOLOR.warning,
        "unknown": TRUECOLOR.muted,
        "N/A": TRUECOLOR.muted,
    }
    for value, colour in expected.items():
        assert state_colour(value, TRUECOLOR) == colour, value
        assert state_text(value, TRUECOLOR).style == f"bold {colour}", value
        badge = state_badge(value, TRUECOLOR)
        assert badge.plain == f"● {value}"
        assert {span.style for span in badge.spans} == {f"bold {colour}"}, value


def test_state_badge_keeps_its_word_when_colour_is_disabled() -> None:
    badge = state_badge("stopped", NO_COLOR)
    # NO_COLOR collapses semantic colours to white: the word, not the hue, carries the verdict.
    assert badge.plain == "● stopped"
    assert state_colour("stopped", NO_COLOR) == NO_COLOR.error == "#ffffff"
    assert {span.style for span in badge.spans} == {f"bold {NO_COLOR.error}"}


def test_build_vm_detail_aligns_pairs_and_keeps_the_full_uuid() -> None:
    record = _record(state="stopped", description="Primary reverse proxy.")
    lines = [
        line.rstrip()
        for line in _render(build_vm_detail(record, None)).splitlines()
        if line.strip()
    ]

    assert lines[0].startswith("web-prod-01")
    assert not any("STATE EVIDENCE CONFLICT" in line for line in lines)

    state_line = next(line for line in lines if line.startswith("Object state"))
    pid_line = next(line for line in lines if line.startswith("PID"))
    memory_line = next(line for line in lines if line.startswith("Memory"))
    console_line = next(line for line in lines if line.startswith("Console"))
    uuid_line = next(line for line in lines if line.startswith("UUID"))

    value_column = state_line.index("● stopped")
    assert pid_line.index("4242") == value_column
    assert memory_line.index("8 192 MB") == value_column
    assert uuid_line.index(UUID_A) == value_column
    assert uuid_line.rstrip().endswith(UUID_A)  # full 36-character UUID, never truncated
    # The right-hand pairs share their own aligned column, including the description row.
    right_column = state_line.index("Process")
    assert pid_line.index("vCPU") == right_column
    assert memory_line.index("Host") == right_column
    assert console_line.index("Description") == right_column
    assert "Primary reverse proxy." in console_line
    console_cell = console_line[: console_line.index("Description")]
    assert console_cell.split("Console", 1)[1].strip() == "—"  # no console evidence yet
    assert lines[-1].startswith("Console")

    for label in (
        "Object state",
        "PID",
        "Memory",
        "Console",
        "Process",
        "vCPU",
        "Host",
        "Description",
    ):
        assert label in "\n".join(lines), label


def test_build_vm_detail_reports_state_conflict_separately_from_the_state() -> None:
    record = VMRecord(
        ObjectVM(UUID_A, "web-prod-01", state="stopped"),
        ProcessObservation(UUID_A, pid=4242),
        state_disagreed=True,
    )
    lines = [line.rstrip() for line in _render(build_vm_detail(record, None)).splitlines()]
    conflict = next(line for line in lines if "STATE EVIDENCE CONFLICT" in line)
    state = next(line for line in lines if line.startswith("Object state"))

    assert conflict.startswith("▲")
    assert "stopped" not in conflict
    assert "● stopped" in state
    assert "STATE EVIDENCE CONFLICT" not in state


def test_build_vm_detail_renders_console_port_and_redacts_every_value() -> None:
    record = VMRecord(
        ObjectVM(
            UUID_A,
            "password=synthetic-detail-name",
            state="started",
            vcpu=8,
            mem_mb=16384,
            description="token=synthetic-detail-description",
        ),
        ProcessObservation(UUID_A, pid=4242),
    )
    text = _render(build_vm_detail(record, _detail(host="password=synthetic-host")))

    assert "synthetic-detail-name" not in text
    assert "synthetic-detail-description" not in text
    assert "synthetic-host" not in text
    assert text.count("[REDACTED]") >= 3

    assert "vnc : 5900" in text  # the detail read is the only port source here
    assert "16 384 MB" in text
    # Detail-owned fields stay absent (never fabricated) until Enter reads them.
    assert "Host" in _render(build_vm_detail(_record(), None))
    assert "node-7" not in _render(build_vm_detail(_record(), None))


def test_removed_detail_fields_are_not_rendered() -> None:
    text = _render(build_vm_detail(_record(), _detail()))
    for label in ("Machine", "Topology", "Disks / NICs", "CPU model"):
        assert label not in text, label
    for value in ("pc-q35-6.2", "4/1/1", "2 / 1", "EPYC 7443"):
        assert value not in text, value


def test_host_renders_from_the_native_object_record_before_enter() -> None:
    text = _render(build_vm_detail(_record(host="node-a"), None))
    assert "node-a" in text
    # No asynchronous detail was read, so nothing may be borrowed from it.
    assert "node-7" not in text


def test_host_falls_back_to_the_detail_read_and_then_to_unknown() -> None:
    assert "node-7" in _render(build_vm_detail(_record(), _detail(host="node-7")))
    hostless = _render(build_vm_detail(_record(), _detail(host="")))
    assert "node-7" not in hostless


LOCAL_IDENTITY = {
    "local_hostname": "spongebob",
    "local_node_id": "1",
    "local_node_name": "node-a",
}


def test_describe_host_only_decorates_a_proven_local_node() -> None:
    # Matched by node name or node number: keep the raw identifier, append the hostname.
    assert describe_host("node-a", **LOCAL_IDENTITY) == "node-a (spongebob)"
    assert describe_host("1", **LOCAL_IDENTITY) == "1 (spongebob)"
    assert describe_host("NODE-A", **LOCAL_IDENTITY) == "NODE-A (spongebob)"
    # The node already is the hostname: never duplicate it.
    assert describe_host("spongebob", **LOCAL_IDENTITY) == "spongebob"
    assert describe_host("SpongeBob", **LOCAL_IDENTITY) == "spongebob"
    # A remote node never borrows this machine's hostname.
    assert describe_host("node-b", **LOCAL_IDENTITY) == "node-b"
    # A local match without a known hostname stays the raw identifier.
    assert describe_host("node-a", local_node_name="node-a") == "node-a"
    # PVM's placement marker and unknown values are not decorated.
    assert describe_host("auto", **LOCAL_IDENTITY) == "auto"
    assert describe_host("", **LOCAL_IDENTITY) == "—"
    assert describe_host(None) == "—"
    assert describe_host("—") == "—"


def test_build_vm_detail_decorates_the_local_node_with_its_hostname() -> None:
    by_name = _render(build_vm_detail(_record(host="node-a"), None, **LOCAL_IDENTITY))
    assert "node-a (spongebob)" in by_name
    by_id = _render(build_vm_detail(_record(host="1"), None, **LOCAL_IDENTITY))
    assert "1 (spongebob)" in by_id


def test_build_vm_detail_leaves_remote_auto_and_unknown_hosts_undecorated() -> None:
    remote = _render(build_vm_detail(_record(host="node-b"), None, **LOCAL_IDENTITY))
    assert "node-b" in remote
    assert "spongebob" not in remote

    auto = _render(build_vm_detail(_record(host="auto"), None, **LOCAL_IDENTITY))
    assert "auto" in auto
    assert "spongebob" not in auto

    unknown = _render(build_vm_detail(_record(host=None), None, **LOCAL_IDENTITY))
    assert "spongebob" not in unknown


def test_tui_decorates_the_local_node_with_the_snapshot_hostname(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (ObjectVM(UUID_A, "web-prod-01", state="started", host="node-a"),)
    provider.local_host = lambda: SourceResult(
        LocalHostSample(hostname="spongebob"), CollectionStatus.CURRENT, "local"
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)
            for _ in range(20):
                if "spongebob" in plain(box):
                    break
                await pilot.pause(0.1)
            assert "node-a (spongebob)" in plain(box)

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_console_port_uses_live_then_configured_then_detail_evidence() -> None:
    detail = _detail(port=5901)
    live = VMRecord(
        ObjectVM(UUID_A, "vm-a", state="started", configured_port=5900),
        ProcessObservation(UUID_A, pid=1234, port=6054),
    )
    assert resolve_console_port(live, detail) == 6054
    assert "vnc : 6054" in _render(build_vm_detail(live, detail))

    configured = VMRecord(ObjectVM(UUID_A, "vm-a", configured_port=5900))
    assert resolve_console_port(configured, detail) == 5900
    assert "vnc : 5900" in _render(build_vm_detail(configured, detail))

    no_object_port = VMRecord(ObjectVM(UUID_A, "vm-a"))
    assert resolve_console_port(no_object_port, detail) == 5901
    assert "vnc : 5901" in _render(build_vm_detail(no_object_port, detail))
    assert resolve_console_port(no_object_port, None) is None

    kind_only = _detail(port=None)
    assert resolve_console_port(no_object_port, kind_only) is None
    assert "vnc : —" in _render(build_vm_detail(no_object_port, kind_only))


def test_console_without_kind_or_port_is_unknown_not_a_dangling_separator() -> None:
    text = _render(build_vm_detail(_record(), None))
    assert "— :" not in text
    console_line = next(line for line in text.splitlines() if line.startswith("Console"))
    console_cell = console_line[: console_line.index("Description")]
    assert console_cell.split("Console", 1)[1].strip() == "—"


def test_detail_placeholders_cover_empty_loading_and_failure() -> None:
    assert build_detail_placeholder("empty").plain == "Select a VM to inspect its details."
    assert build_detail_placeholder("no_match").plain.startswith("No matching VMs")
    assert build_detail_placeholder("no_records").plain.startswith("No VM records")
    loading = build_detail_placeholder("loading", TRUECOLOR)
    error = build_detail_placeholder("error", TRUECOLOR)
    assert loading.plain == "Reading full detail…"
    assert loading.style == TRUECOLOR.primary
    assert error.plain == "Detail read failed · press Enter to retry"
    assert error.style == TRUECOLOR.error


def test_detail_pane_renders_every_field_without_clipping_at_80_columns(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (
        ObjectVM(
            UUID_A,
            "web-prod-01",
            state="stopped",
            vcpu=4,
            mem_mb=8192,
            description="Primary reverse proxy.",
            host="node-a",
            configured_port=5900,
        ),
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)
            scroll = tui.query_one("#detail-scroll", VerticalScroll)
            text = plain(box, width=box.size.width)

            for field in (
                "web-prod-01",
                "UUID",
                "Object state",
                "PID",
                "Memory",
                "Console",
                "Process",
                "vCPU",
                "Host",
                "Description",
            ):
                assert field in text, field
            assert UUID_A in text
            # Native node and configured port survive without an Enter read.
            assert "node-a" in text
            assert "— : 5900" in text
            # The wrapper gives the body room: nothing is clipped and no scroll is needed.
            assert box.virtual_size.height <= box.size.height
            assert box.virtual_size.width <= box.size.width
            assert scroll.max_scroll_y == 0
            assert "Selected VM" in Text.from_markup(str(scroll.border_title)).plain

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_long_description_is_reachable_through_the_scroll_wrapper(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (
        ObjectVM(UUID_A, "alpha", state="started", description="word " * 120),
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)
            scroll = tui.query_one("#detail-scroll", VerticalScroll)
            assert box.size.height > scroll.size.height
            assert scroll.max_scroll_y > 0

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_enter_reports_loading_then_publishes_detail(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    gate = threading.Event()

    def slow_detail(token: str, uuid: str) -> SourceResult[object]:
        gate.wait(3)
        return SourceResult(_detail(uuid), CollectionStatus.CURRENT, "detail")

    provider.vm_detail = slow_detail
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)

            tui.action_details()
            await pilot.pause(0.1)
            assert "Reading full detail…" in plain(box)

            gate.set()
            for _ in range(20):
                if "node-7" in plain(box):
                    break
                await pilot.pause(0.1)
            text = plain(box)
            assert "node-7" in text and "vnc : 5900" in text
            assert "Reading full detail…" not in text

    try:
        asyncio.run(exercise())
    finally:
        gate.set()
        collection.close()


def test_failed_detail_read_is_visible_and_retryable(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)

            tui.action_details()
            for _ in range(20):
                if "Detail read failed" in plain(box):
                    break
                await pilot.pause(0.1)
            assert "Detail read failed · press Enter to retry" in plain(box)

    try:
        asyncio.run(exercise())
    finally:
        collection.close()


def test_highlighting_another_vm_drops_the_previous_rows_detail_read(tmp_path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (
        ObjectVM(UUID_A, "alpha", state="started"),
        ObjectVM(UUID_B, "beta", state="started"),
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> None:
        async with tui.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            tui.action_vms_page()
            await pilot.pause(0.1)
            box = tui.query_one("#detail-box", Static)

            tui._publish_detail(UUID_A, _detail(UUID_A, host="node-7"))
            assert "node-7" in plain(box)

            tui.query_one("#fleet-table").move_cursor(row=1)
            await pilot.pause(0.1)
            assert tui._selected_uuid == UUID_B
            assert "node-7" not in plain(box)

    try:
        asyncio.run(exercise())
    finally:
        collection.close()

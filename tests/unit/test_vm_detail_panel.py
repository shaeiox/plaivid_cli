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
)
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
        ),
        ProcessObservation(str(values["uuid"]), pid=4242),
    )


def _detail(uuid: str = UUID_A, *, host: str = "node-7") -> VMDetail:
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
        console=ConsoleInfo(kind="vnc"),
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
    process_line = next(line for line in lines if "Process" in line)
    uuid_line = next(line for line in lines if line.startswith("UUID"))

    value_column = state_line.index("● stopped")
    assert pid_line.index("4242") == value_column
    assert memory_line.index("8 192 MB") == value_column
    assert uuid_line.index(UUID_A) == value_column
    assert uuid_line.rstrip().endswith(UUID_A)  # full 36-character UUID, never truncated
    # The right-hand pair shares its own aligned column.
    assert process_line.index("Process") == state_line.index("Process")
    assert pid_line.index("vCPU") == state_line.index("Process")
    assert lines[-1].startswith("Description")

    for label in (
        "Object state",
        "PID",
        "Memory",
        "Machine",
        "Topology",
        "Disks / NICs",
        "Process",
        "vCPU",
        "Host",
        "CPU model",
        "Console",
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


def test_build_vm_detail_adds_detail_fields_and_redacts_every_value() -> None:
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

    for value in ("pc-q35-6.2", "EPYC 7443", "4/1/1", "2 / 1", "vnc"):
        assert value in text, value
    assert "16 384 MB" in text
    # Detail-owned fields stay absent (never fabricated) until Enter reads them.
    assert "Host" in _render(build_vm_detail(_record(), None))
    assert "node-7" not in _render(build_vm_detail(_record(), None))


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
                "Process",
                "PID",
                "vCPU",
                "Memory",
                "Description",
                "Disks / NICs",
            ):
                assert field in text, field
            assert UUID_A in text
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
            assert "node-7" in text and "EPYC 7443" in text
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

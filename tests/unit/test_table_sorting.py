"""Column sorting for the VM and Desktop inventory tables.

The tables are sorted in Python so ``_table_order`` / ``_desktop_rows`` stay the
single source of row order: a click must move the *rows*, keep each row's
checkbox with its VM, and leave the cursor on the same record.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from test_cli_and_tui import UUID_A, UUID_B, runtime
from textual.widgets import DataTable, Input

from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.models import (
    CollectionStatus,
    ObjectVM,
    ProcessObservation,
    PvmSession,
    SourceResult,
)
from plaivid_cli.presentation.tui.app import PlaividTui
from plaivid_cli.presentation.tui.components import CheckableTable
from plaivid_cli.presentation.tui.components.sorting import (
    DESKTOP_SORT_COLUMNS,
    VM_SORT_COLUMNS,
    column_value,
    describe_sort,
    next_sort_state,
    sort_records,
)

# A third identity so a sort has something to reorder without touching UUID_A/B.
UUID_C = "5d2f2ba4-6d5a-4a2f-9a1c-0d5f6a7b8c9d"

VM_NAME_COLUMN = 2
VM_VCPU_COLUMN = 5
DESKTOP_VCPU_COLUMN = 5


# --------------------------------------------------------------------- helpers


def _header_click(pilot, table_id: str, column_index: int) -> None:
    """Click a column header exactly as an operator would.

    ``pilot.click`` goes through ``DataTable._on_click``, so this exercises the
    real ``HeaderSelected`` path rather than calling the handler directly. The
    header row sits below the table's ``round`` border and one cell padding
    column in, so the click uses *screen* coordinates derived from the table's
    own column geometry.
    """

    async def click() -> None:
        table = pilot.app.query_one(f"#{table_id}", DataTable)
        column = table._get_column_region(column_index)
        x = table.region.x + column.x + table.cell_padding
        y = table.region.y + table.gutter.top
        await pilot.click(offset=(x, y))

    return click()


def _row_uuids(table: DataTable) -> list[str]:
    return [str(getattr(row.key, "value", row.key)) for row in table.ordered_rows]


def _vcpu_cells(table: DataTable, column: int) -> list[str]:
    keys = [row.key for row in table.ordered_rows]
    return [str(table.get_row(key)[column]) for key in keys]


def _needs_sorting_provider(tmp_path: Path):
    """A provider whose VMs prove numeric, textual and absent-value ordering."""
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.objects = (
        ObjectVM(UUID_A, "alpha", state="started", vcpu=10, mem_mb=8192),
        ObjectVM(UUID_B, "beta", state="stopped", vcpu=2, mem_mb=512),
        ObjectVM(UUID_C, "gamma", state="started", vcpu=None, mem_mb=None),
    )
    # Only alpha/beta are observed: this makes the *default* order
    # (evidence first, then name) differ from every column order.
    provider.list_processes = lambda: SourceResult(
        (ProcessObservation(UUID_A, pid=11),), CollectionStatus.CURRENT, "processes"
    )
    return provider, collection, application, operations, sessions


# ------------------------------------------------------- pure sorting behaviour


def test_sort_state_cycles_through_ascending_descending_and_default() -> None:
    assert next_sort_state(None, VM_VCPU_COLUMN, VM_SORT_COLUMNS) == (VM_VCPU_COLUMN, False)
    ascending = (VM_VCPU_COLUMN, False)
    assert next_sort_state(ascending, VM_VCPU_COLUMN, VM_SORT_COLUMNS) == (VM_VCPU_COLUMN, True)
    descending = (VM_VCPU_COLUMN, True)
    assert next_sort_state(descending, VM_VCPU_COLUMN, VM_SORT_COLUMNS) is None
    # A different column restarts at ascending instead of inheriting the direction.
    assert next_sort_state(descending, VM_NAME_COLUMN, VM_SORT_COLUMNS) == (VM_NAME_COLUMN, False)


def test_unsortable_columns_never_change_the_order() -> None:
    # Column 0 is the checkbox and column 1 is the regenerated "#" column.
    assert next_sort_state(None, 0, VM_SORT_COLUMNS) is None
    assert next_sort_state(None, 1, VM_SORT_COLUMNS) is None
    assert next_sort_state((5, True), 0, VM_SORT_COLUMNS) == (5, True)
    assert next_sort_state(None, 0, DESKTOP_SORT_COLUMNS) is None


def test_sort_description_names_the_column_and_direction() -> None:
    assert describe_sort((VM_VCPU_COLUMN, False), VM_SORT_COLUMNS) == "sorted by vCPU ▲"
    assert describe_sort((VM_VCPU_COLUMN, True), VM_SORT_COLUMNS) == "sorted by vCPU ▼"
    assert describe_sort(None, VM_SORT_COLUMNS) == ""


def test_numeric_columns_compare_as_numbers_not_text() -> None:
    class Row:
        def __init__(self, name: str, vcpu: int) -> None:
            self.name, self.vcpu, self.uuid = name, vcpu, name

    rows = [Row("ten", 10), Row("two", 2), Row("four", 4)]
    keys = {5: lambda row: column_value(row.vcpu, row.uuid, numeric=True)}
    outcome = sort_records(rows, (5, False), lambda row: row.uuid, keys)
    # Text order would put "10" before "2".
    assert [row.vcpu for row in outcome.records] == [2, 4, 10]


def test_absent_values_sort_last_in_both_directions() -> None:
    class Row:
        def __init__(self, name: str, vcpu: int | None) -> None:
            self.name, self.vcpu, self.uuid = name, vcpu, name

    rows = [Row("missing", None), Row("ten", 10), Row("two", 2)]
    keys = {5: lambda row: column_value(row.vcpu, row.uuid, numeric=True)}
    ascending = sort_records(rows, (5, False), lambda row: row.uuid, keys)
    descending = sort_records(rows, (5, True), lambda row: row.uuid, keys)
    assert [row.vcpu for row in ascending.records] == [2, 10, None]
    assert [row.vcpu for row in descending.records] == [10, 2, None]


def test_a_column_with_no_values_falls_back_to_the_default_order() -> None:
    class Row:
        def __init__(self, name: str) -> None:
            self.name, self.vcpu, self.uuid = name, None, name

    rows = [Row("b"), Row("a")]
    outcome = sort_records(
        rows, (5, False), lambda row: row.uuid, {5: lambda row: column_value(row.vcpu, row.uuid,
                                                                            numeric=True)}
    )
    assert outcome.applied is None  # Reported as unsorted rather than "sorted by vCPU".
    assert [row.name for row in outcome.records] == ["a", "b"]


# ------------------------------------------------------- Virtual Machines table


def test_vm_header_clicks_cycle_sort_and_reorder_rows(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions = _needs_sorting_provider(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.3)
            table = tui.query_one("#fleet-table", CheckableTable)
            seen: dict[str, object] = {}

            # Default order is evidence-first: alpha (observed) before beta / gamma.
            seen["initial"] = _row_uuids(table)
            assert str(tui.query_one("#vm-list").border_title).find("sorted by") == -1

            await _header_click(pilot, "fleet-table", VM_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["ascending_state"] = tui._vm_sort
            seen["ascending"] = _vcpu_cells(table, VM_VCPU_COLUMN)
            seen["ascending_title"] = str(tui.query_one("#vm-list").border_title)

            await _header_click(pilot, "fleet-table", VM_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["descending_state"] = tui._vm_sort
            seen["descending"] = _vcpu_cells(table, VM_VCPU_COLUMN)
            seen["descending_title"] = str(tui.query_one("#vm-list").border_title)

            await _header_click(pilot, "fleet-table", VM_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["default_state"] = tui._vm_sort
            seen["restored"] = _row_uuids(table)
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    assert seen["initial"] == [UUID_A, UUID_B, UUID_C]
    # Ascending: 2, then 10, with the absent vCPU last despite its "—" text.
    assert seen["ascending_state"] == (VM_VCPU_COLUMN, False)
    assert seen["ascending"][:3] == ["2", "10", "—"]
    assert "sorted by vCPU ▲" in str(seen["ascending_title"])
    # Descending: 10, then 2, and the absent value is *still* last.
    assert seen["descending_state"] == (VM_VCPU_COLUMN, True)
    assert seen["descending"][:3] == ["10", "2", "—"]
    assert "sorted by vCPU ▼" in str(seen["descending_title"])
    # Third click returns to the evidence-first default and drops the indicator.
    assert seen["default_state"] is None
    assert seen["restored"] == [UUID_A, UUID_B, UUID_C]


def test_vm_name_and_checkbox_columns(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions = _needs_sorting_provider(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.3)
            table = tui.query_one("#fleet-table", CheckableTable)
            seen: dict[str, object] = {}

            await _header_click(pilot, "fleet-table", VM_NAME_COLUMN)
            await pilot.pause(0.2)
            seen["by_name"] = _row_uuids(table)

            # The checkbox header must not reorder anything.
            before = _row_uuids(table)
            await _header_click(pilot, "fleet-table", 0)
            await pilot.pause(0.2)
            seen["checkbox_click_changed"] = _row_uuids(table) != before
            seen["state_after_checkbox"] = tui._vm_sort
            # The regenerated "#" column is not sortable either.
            await _header_click(pilot, "fleet-table", 1)
            await pilot.pause(0.2)
            seen["state_after_number"] = tui._vm_sort
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    assert seen["by_name"] == [UUID_A, UUID_B, UUID_C]  # alpha, beta, gamma
    assert seen["checkbox_click_changed"] is False
    assert seen["state_after_checkbox"] == (VM_NAME_COLUMN, False)
    assert seen["state_after_number"] == (VM_NAME_COLUMN, False)


def test_vm_checked_rows_keep_their_check_after_sorting(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions = _needs_sorting_provider(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.3)
            table = tui.query_one("#fleet-table", CheckableTable)
            table.focus()
            # Check gamma (last row in the default order).
            table.move_cursor(row=2)
            await pilot.press("space")
            await pilot.pause(0.2)
            seen: dict[str, object] = {"checked": set(tui._vm_checked)}

            await _header_click(pilot, "fleet-table", VM_VCPU_COLUMN)
            await pilot.pause(0.3)
            seen["checked_after_sort"] = set(tui._vm_checked)
            # The tick must still be on gamma's row even though it moved.
            seen["checkbox_cell"] = str(table.get_row(UUID_C)[0])
            seen["gamma_row"] = _row_uuids(table).index(UUID_C)
            # "Select all" still covers the sorted set.
            await pilot.press("a")
            await pilot.pause(0.2)
            seen["all_checked"] = set(tui._vm_checked)
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    assert seen["checked"] == {UUID_C}
    assert seen["checked_after_sort"] == {UUID_C}
    assert "☑" in str(seen["checkbox_cell"])
    assert seen["gamma_row"] == 2  # Absent vCPU sorts last.
    assert seen["all_checked"] == {UUID_A, UUID_B, UUID_C}


# ------------------------------------------------------- Virtual Desktops table


def test_desktop_header_clicks_cycle_sort_including_missing_values(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.list_desktops = lambda token: SourceResult(
        (
            VirtualDesktop(UUID_A, "alpha", cluster_status="started", vcpu=10),
            VirtualDesktop(UUID_B, "beta", cluster_status="stopped", vcpu=2),
            VirtualDesktop(UUID_C, "gamma", cluster_status=None, vcpu=None),
        ),
        CollectionStatus.CURRENT,
        "user/objects/desktops",
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "desktops"
            for _ in range(100):
                if tui.query_one("#desktop-table", DataTable).row_count == 3:
                    break
                await pilot.pause(0.05)
            table = tui.query_one("#desktop-table", DataTable)
            seen: dict[str, object] = {"initial": _row_uuids(table)}

            await _header_click(pilot, "desktop-table", DESKTOP_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["ascending_state"] = tui._desktop_sort
            seen["ascending"] = _vcpu_cells(table, DESKTOP_VCPU_COLUMN)

            await _header_click(pilot, "desktop-table", DESKTOP_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["descending_state"] = tui._desktop_sort
            seen["descending"] = _vcpu_cells(table, DESKTOP_VCPU_COLUMN)
            seen["title"] = str(tui.query_one("#desktop-list").border_title)

            await _header_click(pilot, "desktop-table", DESKTOP_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen["default_state"] = tui._desktop_sort
            seen["restored"] = _row_uuids(table)
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    assert seen["initial"] == [UUID_A, UUID_B, UUID_C]
    assert seen["ascending_state"] == (DESKTOP_VCPU_COLUMN, False)
    assert seen["ascending"][:2] == ["2", "10"]
    assert seen["descending_state"] == (DESKTOP_VCPU_COLUMN, True)
    assert seen["descending"][:2] == ["10", "2"]
    assert "sorted by vCPU ▼" in str(seen["title"])
    assert seen["default_state"] is None
    assert seen["restored"] == [UUID_A, UUID_B, UUID_C]


def test_desktop_sort_survives_a_refresh_and_is_cleared_by_logout(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    provider.list_desktops = lambda token: SourceResult(
        (
            VirtualDesktop(UUID_A, "alpha", vcpu=10),
            VirtualDesktop(UUID_B, "beta", vcpu=2),
        ),
        CollectionStatus.CURRENT,
        "user/objects/desktops",
    )
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "desktops"
            for _ in range(100):
                if tui.query_one("#desktop-table", DataTable).row_count == 2:
                    break
                await pilot.pause(0.05)
            table = tui.query_one("#desktop-table", DataTable)
            await _header_click(pilot, "desktop-table", DESKTOP_VCPU_COLUMN)
            await pilot.pause(0.2)
            seen: dict[str, object] = {"sorted": _row_uuids(table)}

            # A collection refresh must not silently drop the operator's order.
            tui._request_refresh()
            await pilot.pause(0.4)
            seen["after_refresh"] = _row_uuids(table)
            seen["state_after_refresh"] = tui._desktop_sort

            tui._session_ended("test logout")
            await pilot.pause(0.2)
            seen["state_after_logout"] = tui._desktop_sort
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    assert seen["sorted"] == [UUID_B, UUID_A]
    assert seen["after_refresh"] == [UUID_B, UUID_A]
    assert seen["state_after_refresh"] == (DESKTOP_VCPU_COLUMN, False)
    assert seen["state_after_logout"] is None


def test_vm_search_still_filters_while_sorted(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions = _needs_sorting_provider(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 50)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.3)
            table = tui.query_one("#fleet-table", CheckableTable)
            await _header_click(pilot, "fleet-table", VM_VCPU_COLUMN)
            await pilot.pause(0.2)
            tui.query_one("#vm-search", Input).value = "a"
            await pilot.pause(0.3)
            seen = {"filtered": _row_uuids(table), "state": tui._vm_sort}
            tui.query_one("#vm-search", Input).value = ""
            await pilot.pause(0.3)
            seen["restored"] = _vcpu_cells(table, VM_VCPU_COLUMN)[:3]
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()

    # All three names contain "a", so the filter keeps every row — still in the
    # operator's order (2, 10, then the absent value), not alphabetical.
    assert seen["filtered"] == [UUID_B, UUID_A, UUID_C]
    assert seen["state"] == (VM_VCPU_COLUMN, False)
    assert seen["restored"] == ["2", "10", "—"]

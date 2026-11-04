from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import DataTable, Input

from plaivid_cli.domain.models import PvmSession
from plaivid_cli.presentation.charts import LOAD_COLOURS, ChartView
from plaivid_cli.tui import CheckableTable, PlaividTui
from test_cli_and_tui import UUID_A, UUID_B, runtime


def _checkbox(table: DataTable, uuid: str) -> str:
    return str(table.get_row(uuid)[0])


def test_checkboxes_toggle_by_space_select_all_and_survive_filtering(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> dict[str, object]:
        async with tui.run_test(size=(140, 60)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            table = tui.query_one("#fleet-table", CheckableTable)
            table.focus()
            await pilot.pause(0.1)
            seen: dict[str, object] = {}
            seen["initial"] = _checkbox(table, UUID_A)
            table.move_cursor(row=0)
            await pilot.press("space")
            await pilot.pause(0.1)
            seen["after_space"] = _checkbox(table, tui._table_order[0])
            seen["checked"] = set(tui._vm_checked)
            await pilot.press("space")
            await pilot.pause(0.1)
            seen["after_second_space"] = set(tui._vm_checked)
            await pilot.press("a")
            await pilot.pause(0.1)
            seen["after_select_all"] = set(tui._vm_checked)
            # A checked machine stays checked when the search hides it and then shows it again.
            tui.query_one("#vm-search", Input).value = "alpha"
            await pilot.pause(0.2)
            tui.query_one("#vm-search", Input).value = ""
            await pilot.pause(0.2)
            seen["after_filter"] = set(tui._vm_checked)
            seen["checkbox_after_filter"] = _checkbox(table, UUID_A)
            # Clicking the checkbox message toggles the same state as Space.
            table.post_message(CheckableTable.CheckRequested(table, UUID_B))
            await pilot.pause(0.2)
            seen["after_message"] = set(tui._vm_checked)
            seen["count_label"] = str(tui.query_one("#vm-scope").render())
            return seen

    try:
        seen = asyncio.run(exercise())
    finally:
        collection.close()
    assert seen["initial"] == "☐"
    assert seen["after_space"] == "☑"
    assert len(seen["checked"]) == 1
    assert seen["after_second_space"] == set()
    assert seen["after_select_all"] == {UUID_A, UUID_B}
    assert seen["after_filter"] == {UUID_A, UUID_B}
    assert seen["checkbox_after_filter"] == "☑"
    assert seen["after_message"] == {UUID_A}
    assert "1 checked" in str(seen["count_label"])


def test_load_graph_is_a_single_blue_one_minute_line(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def exercise() -> tuple[object, ...]:
        async with tui.run_test(size=(140, 60)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            await pilot.pause(0.6)
            tui._history.values["load"].extend([(0.0, 0.4), (3.0, 0.5)])
            tui._history.values["load5"].extend([(0.0, 1.1), (3.0, 1.2)])
            tui._history.values["load15"].extend([(0.0, 2.0), (3.0, 2.1)])
            tui._render_charts()
            chart = tui.query_one("#load-chart", ChartView)
            series = chart._spec[0] if chart._spec else ()
            return tuple((item.name, item.colour) for item in series), LOAD_COLOURS[0]

    try:
        series, blue = asyncio.run(exercise())
    finally:
        collection.close()
    assert [name for name, _ in series] == ["1m"]  # 5m and 15m are header text only
    assert series[0][1] == blue

import asyncio
from pathlib import Path

from test_cli_and_tui import runtime

from plaivid_cli.application.overview import OverviewSchedule
from plaivid_cli.domain.models import PvmSession
from plaivid_cli.presentation.tui import PlaividTui


def test_background_sampling_only_runs_when_overview_is_not_visible() -> None:
    scheduler = OverviewSchedule(interval=1.0)
    scheduler.enter()
    assert scheduler.background_due(now=100.0) == ()  # the Overview's own schedule covers it
    scheduler.finished()
    scheduler.leave()
    assert scheduler.background_due(now=101.0) == ("local_host",)
    assert scheduler.background_due(now=101.5) == ()  # busy until the read finishes
    scheduler.finished()
    assert scheduler.background_due(now=102.1) == ("local_host",)


def test_graph_history_keeps_growing_while_another_tab_is_shown(tmp_path: Path) -> None:
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)

    async def run() -> tuple[int, int, int]:
        async with tui.run_test(size=(140, 60)) as pilot:
            tui._session_ready(PvmSession("operator", "synthetic-token"))
            tui._overview_schedule.set_interval(1)
            await pilot.pause(0.6)
            tui.query_one("#tabs").active = "fleet"
            await pilot.pause(0.2)
            calls_before = provider.local_calls
            samples_before = len(tui._history.values["cpu"])
            await pilot.pause(3.6)
            return provider.local_calls - calls_before, samples_before, len(tui._history.values["cpu"])

    try:
        new_calls, before, after = asyncio.run(run())
    finally:
        collection.close()
    assert new_calls >= 2
    assert after > before

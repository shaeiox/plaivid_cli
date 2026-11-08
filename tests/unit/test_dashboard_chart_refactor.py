"""Regression coverage for the dashboard/chart layout and scaling refactor."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from rich.text import Text
from test_cli_and_tui import runtime
from textual.app import App, ComposeResult
from textual.widgets import Static

from plaivid_cli.application.overview import HISTORY_WINDOW_SECONDS, OverviewHistory, window_points
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot
from plaivid_cli.domain.overview import LocalHostSample
from plaivid_cli.presentation.charts import (
    CPU_GREEN,
    GRID_STYLE,
    ChartView,
    Series,
    dynamic_top,
    render_chart,
    stable_top,
    window_peak,
    y_axis_labels,
)
from plaivid_cli.presentation.charts.grid import _series_dots
from plaivid_cli.presentation.theme import NO_COLOR
from plaivid_cli.presentation.tui.app import PlaividTui
from plaivid_cli.presentation.tui.pages.overview.components.cpu import CPUCard
from plaivid_cli.presentation.tui.pages.overview.components.load import LoadCard

FLAT = tuple((float(t), 50.0) for t in range(0, 61, 3))


def _snapshot(stamp: float, cpu: float, load: float, generation: int) -> ApplicationSnapshot:
    now = datetime.now(UTC)
    sample = LocalHostSample(cpu_percent=cpu, load1=load, load5=load / 2, load15=load / 4)
    section = SectionSnapshot(
        "local_host",
        sample,
        sample,
        CollectionStatus.CURRENT,
        now,
        now,
        generation,
        succeeded_monotonic=stamp,
    )
    return ApplicationSnapshot(generation, now, (section,))


def _mounted(tmp_path, coroutine, size=(140, 60)):
    provider, collection, application, operations, sessions, _ = runtime(tmp_path)
    tui = PlaividTui(application, operations, sessions)
    try:
        return asyncio.run(coroutine(tui, size))
    finally:
        collection.close()


# --- Card layout -----------------------------------------------------------


def test_metrics_running_vms_and_chart_order_puts_time_axis_last(tmp_path) -> None:
    async def exercise(tui, size):
        async with tui.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            load = tui.query_one("#load-box", LoadCard)
            cpu = tui.query_one("#cpu-box", CPUCard)
            assert [child.id for child in load.children] == [
                "load-card",
                "running-card",
                "load-chart",
            ]
            assert [child.id for child in cpu.children] == ["cpu-card", "cpu-chart"]
            # The ChartView is the last child, so its time-axis row is the
            # bottom-most element of each card container.
            assert isinstance(load.children[-1], ChartView)
            assert isinstance(cpu.children[-1], ChartView)
            return True

    assert _mounted(tmp_path, exercise)


def test_status_is_centralised_in_the_card_header_not_child_widgets(tmp_path) -> None:
    async def exercise(tui, size):
        async with tui.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            bodies = {
                widget_id: str(tui.query_one(f"#{widget_id}", Static).render())
                for widget_id in ("cpu-card", "load-card", "running-card", "memory-card")
            }
            assert all("ONLINE" not in body for body in bodies.values()), bodies
            header = tui.query_one("#cpu-box", CPUCard).border_title
            assert "ONLINE" in getattr(header, "plain", str(header))
            return True

    assert _mounted(tmp_path, exercise)


def test_compose_mounts_charts_with_palette_without_parameter_errors(tmp_path) -> None:
    async def exercise(tui, size):
        async with tui.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            for chart_id in ("cpu-chart", "load-chart"):
                chart = tui.query_one(f"#{chart_id}", ChartView)
                assert chart._palette is tui._palette
            return True

    assert _mounted(tmp_path, exercise)


# --- Sliding window / dynamic scale ---------------------------------------


def test_wall_clock_pruning_advances_without_new_samples() -> None:
    history = OverviewHistory()
    history.add(_snapshot(100.0, 50.0, 2.0, 1))
    history.add(_snapshot(130.0, 5.0, 1.0, 2))
    assert history.peak("cpu", t_end=130.0) == 50.0
    # No new collection at all: the clock alone must retire the old peak.
    assert history.prune(now=161.0) >= 1
    assert all(value != 50.0 for _, value in history.values["cpu"])
    assert history.peak("cpu", t_end=161.0) == 5.0
    assert window_points(((100.0, 50.0), (130.0, 5.0)), 161.0) == ((130.0, 5.0),)
    assert HISTORY_WINDOW_SECONDS == 60.0

    wall = OverviewHistory()
    wall.add(_snapshot(0.0, 50.0, 2.0, 1), now=100.0)
    assert not wall.values["cpu"]  # a sample outside the current window is dropped


def test_dynamic_scale_shrinks_immediately_when_a_peak_exits_the_window() -> None:
    points = tuple(
        [(float(t), 50.0) for t in range(0, 30, 3)] + [(float(t), 5.0) for t in range(30, 61, 3)]
    )
    assert dynamic_top(points, t_end=60.0) >= 50.0
    shrunk = dynamic_top(points, t_end=100.0)
    assert shrunk == 6.0
    assert window_peak(points, 100.0) == 5.0
    # strict mode ignores the previous ceiling, while legacy hysteresis is intact
    assert stable_top(3.0, 8.0) == 8.0
    assert stable_top(3.0, 8.0, strict=True) == 4.0
    assert stable_top(20.0, 64.0) == 24.0  # a stale 50-peak no longer pins the axis
    assert shrunk == stable_top(window_peak(points, 100.0), strict=True)


def test_controller_scale_shrinks_when_the_high_peak_leaves_the_window(tmp_path) -> None:
    async def exercise(tui, size):
        async with tui.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            tui._history.values["cpu"].extend(
                [(float(t), 50.0) for t in range(0, 30, 3)]
                + [(float(t), 5.0) for t in range(30, 61, 3)]
            )
            tui._render_charts(now=60.0)
            high = tui._cpu_scale
            tui._render_charts(now=100.0)
            return high, tui._cpu_scale

    high, low = _mounted(tmp_path, exercise)
    assert high >= 50.0
    assert low < high
    assert low == 12.0  # CPU_MIN_SCALE floor, not the stale 64 ceiling


# --- Rendering overhaul ----------------------------------------------------


def test_y_axis_labels_show_max_mid_and_zero_on_the_left_gutter() -> None:
    assert y_axis_labels(100.0) == ("100", "50", "0")
    text = render_chart(
        (Series("cpu", CPU_GREEN, FLAT),),
        width=40,
        height=9,
        t_end=60.0,
        scale_top=100.0,
    )
    rows = text.plain.split("\n")
    assert rows[0].lstrip().startswith("100")
    assert any(row.lstrip().startswith("50") for row in rows[1:-2])
    assert "0" in rows[-2][:6]
    assert all(len(row) == 40 for row in rows)

    forced = render_chart(
        (Series("cpu", CPU_GREEN, FLAT),),
        width=40,
        height=6,
        t_end=60.0,
        scale_top=100.0,
        y_labels=True,
    )
    assert forced.plain.split("\n")[0].lstrip().startswith("100")
    bare = render_chart(
        (Series("cpu", CPU_GREEN, FLAT),),
        width=40,
        height=9,
        t_end=60.0,
        scale_top=100.0,
        y_labels=False,
    )
    assert "┤" not in bare.plain


def test_grid_layer_is_faint_and_never_data_coloured() -> None:
    text = render_chart(
        (Series("cpu", CPU_GREEN, FLAT),),
        width=40,
        height=9,
        t_end=60.0,
        scale_top=100.0,
    )
    styles = {str(span.style) for span in text.spans}
    assert GRID_STYLE in styles  # dim gray background layer
    assert CPU_GREEN in styles  # data layer keeps its own colour
    plain = text.plain
    rows = plain.split("\n")
    offsets: list[int] = []
    total = 0
    for row in rows:
        offsets.append(total)
        total += len(row) + 1

    def style_at(row: int, col: int) -> set[str]:
        offset = offsets[row] + col
        return {str(span.style) for span in text.spans if span.start <= offset < span.end}

    grid_seen = False
    for row_index in range(1, len(rows) - 2):
        for col_index, char in enumerate(rows[row_index]):
            if 0x2800 < ord(char) <= 0x28FF:  # a braille grid/data cell
                at = style_at(row_index, col_index)
                if GRID_STYLE in at:
                    assert CPU_GREEN not in at  # grid dots are not data artefacts
                    grid_seen = True
    assert grid_seen


def test_braille_lines_are_one_dot_thick() -> None:
    series = Series("cpu", CPU_GREEN, FLAT)
    # A flat 50% trace across 40 dot columns is exactly 40 dots: no y+1 ribbon.
    dots = _series_dots(series, 0.0, 40, 32, 100.0, 5.0)
    assert len(dots) == 40
    assert len({y for _, y in dots}) == 1
    text = render_chart((series,), width=40, height=9, t_end=60.0, scale_top=100.0)
    braille = [
        char for row in text.plain.split("\n") for char in row if 0x2800 < ord(char) <= 0x28FF
    ]
    assert braille
    assert all(bin(ord(char) - 0x2800).count("1") <= 2 for char in braille)


def test_time_axis_is_a_smooth_unicode_rule_with_ticks() -> None:
    text = render_chart(
        (Series("cpu", CPU_GREEN, FLAT),),
        width=40,
        height=6,
        t_end=60.0,
        scale_top=100.0,
    )
    axis = text.plain.split("\n")[-1]
    assert axis.startswith("-60s") and axis.rstrip().endswith("now")
    assert "-30s" in axis
    assert "─" in axis and "┴" in axis
    assert "·" not in axis


def test_chart_view_tolerates_palette_and_extra_composition_kwargs() -> None:
    class Host(App):
        CSS = "#chart { height: 9; }"

        def compose(self) -> ComposeResult:
            yield ChartView(
                id="chart",
                palette=NO_COLOR,
                chart_mode="braille",
                classes="graph",
                theme_hint="unrecognised",
            )

    async def exercise() -> ChartView:
        app = Host()
        async with app.run_test(size=(40, 14)) as pilot:
            chart = app.query_one("#chart", ChartView)
            chart.set_chart(
                series=(Series("cpu", CPU_GREEN, FLAT, area=True),),
                t_end=60.0,
                scale_top=100.0,
                header=Text("CPU"),
                max_gap=5.0,
            )
            await pilot.pause(0.05)
            return chart

    chart = asyncio.run(exercise())
    assert chart.rendered is not None
    assert {str(span.style) for span in chart.rendered.spans} <= {
        NO_COLOR.foreground,
        NO_COLOR.muted,
    }

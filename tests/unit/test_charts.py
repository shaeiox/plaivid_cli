import asyncio
import locale
from datetime import UTC, datetime

from rich.text import Text
from textual.app import App, ComposeResult

from plaivid_cli.application.overview import HISTORY_WINDOW_SECONDS, OverviewHistory
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot
from plaivid_cli.domain.overview import LocalHostSample
from plaivid_cli.presentation.charts import (
    CPU_GREEN,
    LOAD_COLOURS,
    ChartView,
    Series,
    cpu_colour,
    default_chart_mode,
    render_chart,
    stable_top,
)
from plaivid_cli.presentation.theme import ALARM, CAUTION, NO_COLOR, TRUECOLOR

FULL = tuple((float(t), 50.0) for t in range(0, 61, 3))


def _lines(text: Text) -> list[str]:
    return text.plain.split("\n")


def _graph(text: Text, header: bool = False) -> list[str]:
    lines = _lines(text)
    return lines[1 if header else 0 : -1]  # drop the header and the time-axis rows


def _ink(row: str) -> str:
    """Drawn data only: the dotted grid marks are not data."""
    return "".join(char for char in row if char not in " ·")


def test_every_size_and_mode_renders_exact_rows_and_columns() -> None:
    for mode in ("braille", "blocks"):
        for width in (1, 5, 24, 60, 133):
            for height in (1, 2, 3, 9, 12):
                for header in (None, Text("CPU 5.0%")):
                    text = render_chart(
                        (Series("cpu", CPU_GREEN, FULL, area=True),),
                        width=width,
                        height=height,
                        t_end=60.0,
                        scale_top=100.0,
                        header=header,
                        mode=mode,
                    )
                    rows = _lines(text)
                    assert len(rows) == height, (mode, width, height, header is not None)
                    assert all(len(row) == width for row in rows), (mode, width, height)


def test_braille_and_block_modes_draw_with_their_own_glyphs() -> None:
    braille = render_chart(
        (Series("cpu", CPU_GREEN, FULL, area=True),),
        width=20,
        height=9,
        t_end=60.0,
        scale_top=100.0,
    )
    blocks = render_chart(
        (Series("cpu", CPU_GREEN, FULL, area=True),),
        width=20,
        height=9,
        t_end=60.0,
        scale_top=100.0,
        mode="blocks",
    )
    assert any(
        0x2800 <= ord(char) <= 0x28FF and char != "\u2800"
        for row in _graph(braille)
        for char in row
    )
    assert all(ord(char) < 0x2800 or ord(char) > 0x28FF for row in _graph(blocks) for char in row)
    assert "█" in "".join(_graph(blocks))


def test_full_scale_fills_the_top_graph_row_and_zero_is_drawn_on_the_bottom() -> None:
    top = render_chart(
        (Series("cpu", CPU_GREEN, tuple((float(t), 100.0) for t in range(0, 61, 3))),),
        width=20,
        height=6,
        t_end=60.0,
        scale_top=100.0,
        mode="blocks",
    )
    assert _graph(top)[0].strip() != ""
    zero = render_chart(
        (Series("cpu", CPU_GREEN, tuple((float(t), 0.0) for t in range(0, 61, 3))),),
        width=20,
        height=6,
        t_end=60.0,
        scale_top=100.0,
        mode="blocks",
    )
    assert _graph(zero)[-1].strip() != ""  # a real zero is a visible line, not an empty graph
    assert all(_ink(row) == "" for row in _graph(zero)[:-1])


def test_missing_samples_leave_a_gap_and_are_never_drawn_as_zero() -> None:
    samples = tuple(
        [(float(t), 100.0) for t in range(0, 21, 3)] + [(float(t), 100.0) for t in range(50, 61, 3)]
    )
    text = render_chart(
        (Series("cpu", CPU_GREEN, samples),),
        width=60,
        height=6,
        t_end=60.0,
        scale_top=100.0,
        max_gap=5.0,
        mode="blocks",
    )
    graph = _graph(text)
    middle = [row[20:40] for row in graph]  # the 20 s..50 s span with no samples
    assert all(
        _ink(row) == "" for row in middle[:-1]
    )  # only the 0 baseline may sit on the bottom row
    assert set(middle[-1]) <= {"▁", " "}
    assert any(row[-5:].strip() for row in graph)  # the samples after the gap still render


def test_insufficient_history_shows_a_message_not_a_line() -> None:
    text = render_chart(
        (Series("cpu", CPU_GREEN, ((1.0, 50.0),)),), width=30, height=5, t_end=60.0, scale_top=100.0
    )
    assert "Waiting for samples" in text.plain
    assert text.plain.split("\n")[-1].startswith("-60s")


def test_time_axis_labels_appear_where_there_is_room() -> None:
    wide = render_chart(
        (Series("cpu", CPU_GREEN, FULL),), width=40, height=5, t_end=60.0, scale_top=100.0
    )
    assert (
        wide.plain.split("\n")[-1].startswith("-60s")
        and "-30s" in wide.plain.split("\n")[-1]
        and wide.plain.split("\n")[-1].rstrip().endswith("now")
    )
    narrow = render_chart(
        (Series("cpu", CPU_GREEN, FULL),), width=12, height=5, t_end=60.0, scale_top=100.0
    )
    assert "-30s" not in narrow.plain and narrow.plain.split("\n")[-1].rstrip().endswith("now")


def test_three_load_lines_use_three_distinct_colours() -> None:
    series = [
        Series(name, colour, tuple((float(t), 1.0 + index) for t in range(0, 61, 3)))
        for index, (name, colour) in enumerate(zip(("1m", "5m", "15m"), LOAD_COLOURS, strict=True))
    ]
    text = render_chart(
        tuple(series),
        width=40,
        height=9,
        t_end=60.0,
        scale_top=stable_top(3.0),
        header=Text("Load"),
        max_gap=5.0,
    )
    colours = {str(span.style) for span in text.spans}
    for colour in LOAD_COLOURS:
        assert colour in colours
    assert len(set(LOAD_COLOURS)) == 3


def test_cpu_colour_is_green_under_normal_load_and_status_colours_only_when_high() -> None:
    assert cpu_colour(10.0, TRUECOLOR) == CPU_GREEN
    assert cpu_colour(80.0, TRUECOLOR) == CAUTION
    assert cpu_colour(95.0, TRUECOLOR) == ALARM
    assert cpu_colour(None, TRUECOLOR) == TRUECOLOR.muted
    assert cpu_colour(95.0, NO_COLOR) == NO_COLOR.foreground


def test_stable_scale_only_moves_when_it_must() -> None:
    assert stable_top(None) == 1.0
    assert stable_top(3.0) == 4.0
    assert stable_top(3.0, 8.0) == 8.0  # still fits and is not wildly oversized: keep it
    assert stable_top(3.0, 40.0) == 4.0  # more than 3x the need: shrink
    assert stable_top(9.0, 4.0) == 12.0  # does not fit: grow


def test_colour_off_draws_plain_bars_with_one_style() -> None:
    text = render_chart(
        (Series("cpu", CPU_GREEN, FULL, area=True),),
        width=20,
        height=6,
        t_end=60.0,
        scale_top=100.0,
        palette=NO_COLOR,
    )
    assert {str(span.style) for span in text.spans} <= {NO_COLOR.foreground, NO_COLOR.muted}


def test_chart_mode_follows_environment_then_locale(monkeypatch) -> None:
    monkeypatch.setenv("PLAIVID_CHART", "blocks")
    assert default_chart_mode() == "blocks"
    monkeypatch.setenv("PLAIVID_CHART", "braille")
    assert default_chart_mode() == "braille"
    monkeypatch.delenv("PLAIVID_CHART")
    monkeypatch.setattr(locale, "getpreferredencoding", lambda *_: "UTF-8")
    assert default_chart_mode() == "braille"
    monkeypatch.setattr(locale, "getpreferredencoding", lambda *_: "ANSI_X3.4-1968")
    assert default_chart_mode() == "blocks"


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


def test_history_keeps_sixty_seconds_and_records_all_load_averages() -> None:
    history = OverviewHistory()
    for index in range(0, 100):
        history.add(_snapshot(float(index * 3), 10.0, 2.0, index + 1))
    cpu = history.values["cpu"]
    assert cpu[-1][0] == 99 * 3
    assert all(stamp >= cpu[-1][0] - HISTORY_WINDOW_SECONDS for stamp, _ in cpu)
    assert len(cpu) <= 21
    assert history.values["load5"][-1][1] == 1.0 and history.values["load15"][-1][1] == 0.5


def test_chart_view_redraws_when_the_terminal_is_resized() -> None:
    class Host(App):
        CSS = "#chart { height: 9; }"

        def compose(self) -> ComposeResult:
            yield ChartView(id="chart")

    async def run() -> tuple[int, int]:
        app = Host()
        async with app.run_test(size=(40, 14)) as pilot:
            chart = app.query_one("#chart", ChartView)
            chart.set_chart(
                series=(Series("cpu", CPU_GREEN, FULL, area=True),),
                t_end=60.0,
                scale_top=100.0,
                header=Text("CPU"),
                max_gap=5.0,
            )
            await pilot.pause(0.1)
            before = len(chart.rendered.plain.split("\n")[1])
            await pilot.resize_terminal(70, 14)
            await pilot.pause(0.1)
            after = len(chart.rendered.plain.split("\n")[1])
            return before, after

    before, after = asyncio.run(run())
    assert after > before


def test_fast_refresh_samples_are_averaged_into_buckets() -> None:
    from plaivid_cli.presentation.charts import bucketed

    jitter = tuple(
        (float(t), 0.0 if t % 2 else 0.5) for t in range(0, 60)
    )  # 1 s refresh, quantised
    points = bucketed(jitter, 0.0, 60.0, 2.0)
    assert 25 <= len(points) <= 31
    assert all(abs(value - 0.25) < 1e-9 for _, value in points)


def test_empty_buckets_are_skipped_not_drawn_as_zero() -> None:
    from plaivid_cli.presentation.charts import bucketed

    samples = tuple(
        [(float(t), 40.0) for t in range(0, 11)] + [(float(t), 40.0) for t in range(40, 61)]
    )
    points = bucketed(samples, 0.0, 60.0, 2.0)
    assert not any(20 < stamp < 38 for stamp, _ in points)
    assert all(value == 40.0 for _, value in points)


def test_one_second_refresh_draws_a_continuous_line_in_every_column() -> None:
    samples = tuple((float(t), 50.0 if t % 2 == 0 else 0.0) for t in range(0, 61))
    text = render_chart(
        (Series("cpu", CPU_GREEN, samples),),
        width=40,
        height=9,
        t_end=60.0,
        scale_top=100.0,
        mode="blocks",
        min_bucket=2.0,
        max_gap=3.0,
    )
    graph = _graph(text)
    for column in range(40):
        assert any(_ink(row)[:1] and row[column] not in " ·" for row in graph), column


def test_low_cpu_trace_has_visible_peaks_and_troughs() -> None:
    from plaivid_cli.presentation.charts import CPU_MIN_SCALE

    samples = tuple((float(t), 20.0 if (t // 3) % 2 else 5.0) for t in range(0, 61, 3))
    scale = stable_top(20.0, None, floor=CPU_MIN_SCALE)
    assert scale >= 20.0
    text = render_chart(
        (Series("cpu", CPU_GREEN, samples),),
        width=60,
        height=9,
        t_end=60.0,
        scale_top=scale,
        mode="blocks",
        max_gap=4.0,
    )
    rows_with_ink = {index for index, row in enumerate(_graph(text)) if _ink(row)}
    assert len(rows_with_ink) >= 3  # 5% and 20% sit on clearly different rows


def test_zero_baseline_is_drawn_under_every_column() -> None:
    samples = tuple((float(t), 5.0) for t in range(0, 61, 3))
    for mode in ("blocks", "braille"):
        text = render_chart(
            (Series("cpu", CPU_GREEN, samples),),
            width=30,
            height=7,
            t_end=60.0,
            scale_top=12.0,
            mode=mode,
        )
        bottom = _graph(text)[-1]
        assert all(cell != " " for cell in bottom), mode


def test_scale_floor_keeps_low_values_readable() -> None:
    assert stable_top(5.0, None, floor=10.0) == 12.0
    assert stable_top(None, None, floor=10.0) == 12.0

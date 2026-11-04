from collections import deque

from plaivid_cli.presentation.charts import CHART_HEIGHT, PLASMA_STOPS, bar_chart, plasma, resample
from plaivid_cli.presentation.theme import NO_COLOR, TRUECOLOR


def _rows(text) -> list[str]:
    return text.plain.split("\n")


def test_chart_has_height_rows_and_one_cell_per_column() -> None:
    columns = [0.0, 0.25, 0.5, 1.0, 0.75]
    chart = bar_chart(columns, CHART_HEIGHT, TRUECOLOR)
    rows = _rows(chart)
    assert len(rows) == CHART_HEIGHT
    assert all(len(row) == len(columns) for row in rows)


def test_full_column_reaches_the_top_row_and_empty_column_stays_blank() -> None:
    chart = bar_chart([1.0, 0.0], 4, TRUECOLOR)
    rows = _rows(chart)
    assert all(row[0] == "█" for row in rows)
    assert all(row[1] == " " for row in rows)


def test_rows_use_the_plasma_ramp_bottom_dark_top_bright() -> None:
    chart = bar_chart([1.0], 4, TRUECOLOR)
    colours = {}
    for span in chart.spans:
        colours.setdefault(span.start, str(span.style))
    top = min(colours)  # first character is the top row
    bottom = max(colours)
    assert plasma(1.0) in colours[top]
    assert plasma(0.0) in colours[bottom]
    assert plasma(1.0) == PLASMA_STOPS[-1]


def test_partial_row_uses_eighth_block_glyphs() -> None:
    rows = _rows(bar_chart([0.5], 2, TRUECOLOR))
    # Half of a 2-row bar fills the bottom row fully and the top row not at all.
    assert rows == [" ", "█"]
    rows = _rows(bar_chart([0.1], 2, TRUECOLOR))
    assert rows[1] != " " and rows[1] != "█"


def test_colour_off_draws_plain_bars_with_one_style() -> None:
    chart = bar_chart([0.2, 0.9], 4, NO_COLOR)
    assert {str(span.style) for span in chart.spans} <= {NO_COLOR.foreground}


def test_resample_spans_exact_width_and_normalises() -> None:
    samples = deque((float(i), float(i)) for i in range(5))
    columns = resample(samples, 12)
    assert len(columns) == 12
    assert columns[0] == 0.0 and columns[-1] == 1.0
    flat = resample(deque((float(i), 3.0) for i in range(4)), 6)
    assert flat == [0.0] * 6

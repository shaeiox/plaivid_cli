"""Pure graph rendering: single-series CPU and three-line load charts.

Presentation only. Samples come from the overview history; nothing here calls a provider.

Rendering works on a dot grid and maps it to terminal cells:
- Braille (default): 2x4 dots per cell, U+2800..U+28FF. One dot per curve step,
  so the trace stays sharp instead of becoming a two-dot-thick ribbon.
- Blocks (fallback for non-UTF-8 terminals): one column per dot, 8 vertical steps per cell.

The grid/baseline is a **separate, faint layer**: its dots are never OR-ed into a
data cell (which would repaint background dots with the data colour). A missing
sample is a gap in the line, never a zero. The vertical scale follows the highest
peak that is still inside the wall-clock 60-second window, and full-size charts
reserve a left gutter with numeric Y-Max / Y-Mid / Y-Min(0) ticks.
"""

from __future__ import annotations

import locale
import math
import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from rich.text import Text

from plaivid_cli.application.overview import HISTORY_WINDOW_SECONDS, window_points
from plaivid_cli.presentation.theme import ALARM, CAUTION, TRUECOLOR, Palette

from .grid import _axis_row, _series_dots, bucketed

WINDOW_SECONDS = HISTORY_WINDOW_SECONDS
# Header row + graph rows + time-axis row. Both graphs use this height so panels line up.
CHART_HEIGHT = 9
# Normal CPU load is green; it turns yellow and red as utilisation climbs.
CPU_GREEN = "#5fd787"
CPU_CAUTION_PERCENT = 75.0
CPU_ALARM_PERCENT = 90.0
# 1-minute, 5-minute and 15-minute load: three distinguishable, non-status hues.
LOAD_COLOURS = ("#5fafff", "#d787d7", "#ffaf5f")
GRID_FRACTIONS = (0.25, 0.5, 0.75)
# Faint, low-contrast background layer. Data lines must never share this colour.
GRID_COLOUR = "#3f3f4e"
GRID_STYLE = f"dim {GRID_COLOUR}"
# Standard headroom above the highest active peak before snapping to a round step.
SCALE_HEADROOM = 1.15
# A retained ceiling is released as soon as it exceeds 2.5x the active need, so a
# stale peak cannot keep the Y axis squashed for long. The dashboard charts use
# the strictly windowed ``dynamic_top`` and never rely on this hysteresis.
SCALE_KEEP_RATIO = 2.5
_STEPS = (1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)
_EIGHTHS = " ▁▂▃▄▅▆▇"
# Braille dot bit for (dot column, dot row counted from the top), per the Unicode layout.
_BRAILLE_BIT = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (0, 3): 0x40,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (1, 3): 0x80,
}


@dataclass(frozen=True)
class Series:
    name: str
    colour: str
    points: tuple[tuple[float, float], ...]
    area: bool = False


def default_chart_mode() -> str:
    """Braille on UTF-8 terminals; block characters otherwise. PLAIVID_CHART=braille|blocks overrides."""
    forced = os.environ.get("PLAIVID_CHART", "").strip().lower()
    if forced in {"braille", "blocks"}:
        return forced
    encoding = (locale.getpreferredencoding(False) or "").lower()
    return "braille" if "utf" in encoding else "blocks"


def cpu_colour(percent: float | None, palette: Palette = TRUECOLOR) -> str:
    """Green under normal load; yellow and red only when utilisation is high."""
    if not palette.decorative:
        return palette.foreground
    if percent is None:
        return palette.muted
    if percent >= CPU_ALARM_PERCENT:
        return ALARM
    if percent >= CPU_CAUTION_PERCENT:
        return CAUTION
    return CPU_GREEN


# CPU scale never drops below this, so a 5% trace still shows its ups and downs.
CPU_MIN_SCALE = 10.0


def _needed_top(peak: float | None, floor: float, headroom: float) -> float:
    if peak is None or not math.isfinite(peak):
        return floor
    return max(floor, max(0.0, peak) * headroom)


def _step_top(peak: float | None, floor: float = 1.0, headroom: float = SCALE_HEADROOM) -> float:
    """Smallest round step that holds ``peak`` plus headroom; never below ``floor``."""
    needed = _needed_top(peak, floor, headroom)
    for step in _STEPS:
        if step >= needed:
            return float(step)
    return float(math.ceil(needed))


def stable_top(
    peak: float | None,
    previous: float | None = None,
    floor: float = 1.0,
    *,
    strict: bool = False,
    headroom: float = SCALE_HEADROOM,
) -> float:
    """Vertical scale ceiling with optional hysteresis.

    ``strict=True`` ignores ``previous`` entirely: the scale immediately shrinks
    to match the active peak plus headroom. Use it for the wall-clock window, where
    a peak that has scrolled out of view must stop pinning the axis.
    """
    needed = _needed_top(peak, floor, headroom)
    if not strict and previous is not None and needed <= previous <= SCALE_KEEP_RATIO * needed:
        return previous
    return _step_top(peak, floor, headroom)


def window_peak(
    points: Iterable[tuple[float, float]],
    t_end: float,
    window: float = WINDOW_SECONDS,
) -> float | None:
    """Highest sample still visible in ``[t_end - window, t_end]`` (wall-clock)."""
    return max((value for _, value in window_points(points, t_end, window)), default=None)


def dynamic_top(
    points: Iterable[tuple[float, float]],
    *,
    t_end: float,
    floor: float = 1.0,
    headroom: float = SCALE_HEADROOM,
    window: float = WINDOW_SECONDS,
) -> float:
    """Strict Y ceiling from *only* the samples in the current wall-clock window.

    When a high peak leaves the 60-second window, the ceiling shrinks on the very
    next render to the highest active peak plus standard headroom. It never uses
    hysteresis, so no stale peak can keep the chart squashed.
    """
    return _step_top(window_peak(points, t_end, window), floor, headroom)


def _tick_label(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) < 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if abs(value) < 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:g}"


def y_axis_labels(scale_top: float) -> tuple[str, str, str]:
    """Numeric Y-Max, Y-Mid and Y-Min/0 labels for the left chart gutter."""
    top = max(0.0, float(scale_top)) if math.isfinite(scale_top) else 0.0
    return _tick_label(top), _tick_label(top / 2), "0"


def _gutter_width(labels: tuple[str, str, str]) -> int:
    return max(4, max(len(label) for label in labels) + 2)


def _gutter_row(
    row: int,
    graph_rows: int,
    labels: tuple[str, str, str],
    gutter: int,
    label_style: str,
    tick_style: str,
) -> Text:
    """One left-gutter row: a left-flush numeric tick + a smooth axis rule."""
    label_width = gutter - 1
    if row == 0:
        label, tick = labels[0], "┤"
    elif row == graph_rows - 1:
        label, tick = labels[2], "┤"
    elif row == (graph_rows - 1) // 2:
        label, tick = labels[1], "┤"
    else:
        label, tick = "", "│"
    # Labels sit flush to the left edge; the bottom pad is a smooth rule so the
    # zero row has no dotted gaps between the label and the y-axis.
    pad = "─" if row == graph_rows - 1 else " "
    out = Text(no_wrap=True, overflow="crop")
    out.append(label.ljust(label_width, pad)[:label_width], style=label_style)
    out.append(tick, style=tick_style)
    return out


def _braille_mask(codes: set[int], ky: int) -> int:
    mask = 0
    for code in codes:
        dot_x, within = divmod(code, 100)
        mask |= _BRAILLE_BIT[(dot_x, ky - 1 - within)]
    return mask


def render_chart(
    series: Sequence[Series],
    *,
    width: int,
    height: int,
    t_end: float,
    scale_top: float,
    header: Text | None = None,
    max_gap: float = 5.0,
    mode: str = "braille",
    palette: Palette = TRUECOLOR,
    empty_text: str = "Waiting for samples",
    min_bucket: float = 0.0,
    y_labels: bool | None = None,
) -> Text:
    """Return exactly ``height`` rows, each ``width`` cells wide (rows are cropped, never wrapped).

    Samples are averaged into time buckets of at least ``min_bucket`` seconds, so a fast refresh
    draws a smooth trend instead of per-read jitter. ``t_end`` is the current clock, so points
    older than 60 seconds are dropped even if collection has stalled.

    ``y_labels`` defaults to auto: a full-size dashboard chart (``CHART_HEIGHT`` rows or
    more), or any chart with a caption/header, reserves a left gutter with dynamic
    Y-Max / Y-Mid / Y-Min ticks. Pass True/False to force labels on/off for compact
    bare charts.
    """
    width = max(1, width)
    height = max(1, height)
    header_rows = 1 if header is not None and height >= 2 else 0
    axis_rows = 1 if height - header_rows >= 2 else 0
    graph_rows = height - header_rows - axis_rows
    scale_top = scale_top if scale_top > 0 else 1.0
    braille = mode == "braille"
    kx, ky = (2, 4) if braille else (1, 8)

    labels = y_axis_labels(scale_top)
    show_y = y_labels is True or (
        y_labels is None and (height >= CHART_HEIGHT or header is not None)
    )
    if y_labels is False or graph_rows < 3 or width < 16:
        show_y = False
    gutter = min(_gutter_width(labels), width - 8) if show_y else 0
    plot_width = width - gutter
    dw, dh = plot_width * kx, graph_rows * ky

    bucket = max(WINDOW_SECONDS / plot_width, min_bucket)
    max_gap = max(max_gap, 2.5 * bucket)
    series = tuple(
        Series(
            item.name,
            item.colour,
            bucketed(item.points, t_end - WINDOW_SECONDS, t_end, bucket),
            item.area,
        )
        for item in series
    )
    t0 = t_end - WINDOW_SECONDS
    grid_style = GRID_STYLE if palette.decorative else palette.muted
    label_style = palette.muted

    def empty_rows() -> list[Text]:
        rows: list[Text] = []
        for row in range(graph_rows):
            line = (
                _gutter_row(row, graph_rows, labels, gutter, label_style, grid_style)
                if gutter
                else Text(no_wrap=True, overflow="crop")
            )
            line.append(" " * plot_width, style=label_style)
            rows.append(line)
        message = empty_text[:plot_width]
        rows[graph_rows // 2] = (
            _gutter_row(graph_rows // 2, graph_rows, labels, gutter, label_style, grid_style)
            if gutter
            else Text(no_wrap=True, overflow="crop")
        )
        rows[graph_rows // 2].append(message.center(plot_width)[:plot_width], style=label_style)
        return rows

    lines: list[Text] = []
    if header_rows:
        head = header.copy()
        head.truncate(width, overflow="crop")
        head.pad_right(width - len(head))
        lines.append(head)

    if graph_rows <= 0:
        pass  # header only, for a one-row chart
    elif all(len(item.points) < 2 for item in series):
        for row in empty_rows():
            lines.append(row)
    else:
        # Background layer: faint horizontal grid dots plus the zero baseline.
        # These dots are kept in their own cell set and are never merged into data cells.
        grid: set[tuple[int, int]] = set()
        for fraction in GRID_FRACTIONS:
            level = round(fraction * (dh - 1))
            grid.update((x, level) for x in range(0, dw, 4 if braille else 2))

        # Bucket every dot into its cell once: cell = (column, row from top) -> dot codes.
        # A dot code is dot_x * 100 + dot_y_within_cell (bottom-up), so it fits both modes.
        def bucket_dots(dots: set[tuple[int, int]]) -> dict[tuple[int, int], set[int]]:
            cells: dict[tuple[int, int], set[int]] = {}
            for x, y in dots:
                key = (x // kx, graph_rows - 1 - y // ky)
                cells.setdefault(key, set()).add((x % kx) * 100 + y % ky)
            return cells

        line_cells = [
            bucket_dots(_series_dots(item, t0, dw, dh, scale_top, max_gap)) for item in series
        ]
        area_cells: dict[tuple[int, int], set[int]] = {}
        for item, cells in zip(series, line_cells, strict=True):
            if item.area:
                filled: set[tuple[int, int]] = set()
                for col_row, codes in cells.items():
                    for code in codes:
                        dot_x, within = divmod(code, 100)
                        base_y = (graph_rows - 1 - col_row[1]) * ky
                        x = col_row[0] * kx + dot_x
                        filled.update((x, yy) for yy in range(0, base_y + within))
                for key, codes in bucket_dots(filled).items():
                    area_cells.setdefault(key, set()).update(codes)
        grid_cells = bucket_dots(grid)
        baseline_cells = bucket_dots({(x, 0) for x in range(dw)})
        # Smooth Unicode rule for the zero baseline in Braille mode; ┴ marks the ticks.
        tick_columns = {0, plot_width // 2, plot_width - 1}

        for row in range(graph_rows):
            text = (
                _gutter_row(row, graph_rows, labels, gutter, label_style, grid_style)
                if gutter
                else Text(no_wrap=True, overflow="crop")
            )
            for col in range(plot_width):
                key = (col, row)
                lines_here = [cells.get(key, set()) for cells in line_cells]
                area_here = area_cells.get(key, set())
                grid_here = grid_cells.get(key, set())
                baseline_here = baseline_cells.get(key, set())
                data_codes = set().union(*lines_here, area_here)
                grid_codes = grid_here | baseline_here

                if not data_codes and not grid_codes and not (braille and row == graph_rows - 1):
                    text.append(" ")
                    continue
                if not data_codes:
                    # Grid layer only: faint dim gray, never a data colour.
                    if braille:
                        if row == graph_rows - 1:
                            glyph = "┴" if col in tick_columns else "─"
                        else:
                            glyph = chr(0x2800 + _braille_mask(grid_codes, ky))
                    else:
                        glyph = "▁" if baseline_here else "·"
                    text.append(glyph, style=grid_style)
                    continue

                # Data layer only: the background dots are deliberately excluded.
                if braille:
                    glyph = chr(0x2800 + _braille_mask(data_codes, ky))
                else:
                    filled_rows = data_codes
                    if len(filled_rows) == ky:
                        glyph = "█"
                    elif filled_rows == set(range(len(filled_rows))):
                        glyph = _EIGHTHS[len(filled_rows)]
                    else:
                        glyph = "▄" if min(filled_rows) < ky // 2 else "▀"
                if not palette.decorative:
                    colour = palette.foreground
                else:
                    # Line colour wins over area colour; area uses its series colour, dimmed.
                    colour = next(
                        (
                            item.colour
                            for item, codes in zip(series, lines_here, strict=True)
                            if codes
                        ),
                        next((item.colour for item in series if item.area), palette.muted),
                    )
                text.append(glyph, style=colour)
            lines.append(text)

    if axis_rows:
        axis = _axis_row(width)
        axis.stylize(palette.muted)
        lines.append(axis)
    return Text("\n").join(lines)

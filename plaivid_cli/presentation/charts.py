"""Overview graphs: single-series CPU and three-line load charts.

Presentation only. Samples come from the overview history; nothing here calls a provider.

Rendering works on a dot grid and maps it to terminal cells:
- Braille (default): 2x4 dots per cell, U+2800..U+28FF.
- Blocks (fallback for non-UTF-8 terminals): one column per dot, 8 vertical steps per cell.

A missing sample is a gap in the line, never a zero. A stable vertical scale stops the
graph from rescaling on every refresh.
"""

from __future__ import annotations

import locale
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass

from rich.text import Text
from textual.widgets import Static

from plaivid_cli.application.overview import HISTORY_WINDOW_SECONDS
from plaivid_cli.presentation.theme import ALARM, CAUTION, TRUECOLOR, Palette

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
_STEPS = (1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)
_EIGHTHS = " ▁▂▃▄▅▆▇"
# Braille dot bit for (dot column, dot row counted from the top), per the Unicode layout.
_BRAILLE_BIT = {
    (0, 0): 0x01, (0, 1): 0x02, (0, 2): 0x04, (0, 3): 0x40,
    (1, 0): 0x08, (1, 1): 0x10, (1, 2): 0x20, (1, 3): 0x80,
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


def stable_top(peak: float | None, previous: float | None = None, floor: float = 1.0) -> float:
    """Vertical scale ceiling. Kept while it still fits the peak and is not more than 3x it."""
    if peak is None or not math.isfinite(peak):
        needed = floor
    else:
        needed = max(floor, peak * 1.15)
    if previous is not None and needed <= previous <= 3 * needed:
        return previous
    for step in _STEPS:
        if step >= needed:
            return float(step)
    return float(math.ceil(needed))


def _line_dots(points: Sequence[tuple[float, float]], dw: int, dh: int) -> set[tuple[int, int]]:
    """Connected dots for one run of samples (no gaps inside the run)."""
    out: set[tuple[int, int]] = set()
    if len(points) == 1:
        x, y = points[0]
        out.add((round(x), round(y)))
        return out
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        xa, xb = round(x0), round(x1)
        if xb <= xa:
            lo, hi = sorted((round(y0), round(y1)))
            out.update((xa, yy) for yy in range(lo, hi + 1))
            continue
        ys = []
        for x in range(xa, xb + 1):
            fraction = min(1.0, max(0.0, (x - x0) / (x1 - x0)))
            ys.append(round(y0 + (y1 - y0) * fraction))
        for index, x in enumerate(range(xa, xb + 1)):
            nxt = ys[index + 1] if index + 1 < len(ys) else ys[index]
            lo, hi = sorted((ys[index], nxt))
            out.update((x, yy) for yy in range(lo, hi + 1))
    return out


def _series_dots(series: Series, t0: float, dw: int, dh: int, scale: float, max_gap: float) -> set[tuple[int, int]]:
    """Map samples to dots. A time gap longer than ``max_gap`` breaks the line."""
    runs: list[list[tuple[float, float]]] = [[]]
    previous: float | None = None
    for stamp, value in series.points:
        if not math.isfinite(value) or stamp < t0:
            continue
        if previous is not None and stamp - previous > max_gap:
            runs.append([])
        previous = stamp
        x = (stamp - t0) / WINDOW_SECONDS * (dw - 1)
        y = min(max(value, 0.0), scale) / scale * (dh - 1)
        runs[-1].append((x, y))
    dots: set[tuple[int, int]] = set()
    for run in runs:
        if run:
            dots |= _line_dots(run, dw, dh)
    # Two dots thick, so a line reads as a line rather than a dotted trail.
    dots |= {(x, y + 1) for x, y in dots}
    return {(x, y) for x, y in dots if 0 <= x < dw and 0 <= y < dh}


def bucketed(
    points: Sequence[tuple[float, float]], t0: float, t_end: float, bucket: float
) -> tuple[tuple[float, float], ...]:
    """Average real samples into fixed time buckets. Empty buckets stay empty, never zero.

    Buckets sit on an absolute time grid (multiples of ``bucket``), not on the window edge. A new
    sample therefore never moves an earlier bucket: completed buckets keep their values and the
    graph only scrolls as time passes.
    """
    if bucket <= 0:
        return tuple(points)
    groups: dict[int, list[float]] = {}
    for stamp, value in points:
        if not (math.isfinite(stamp) and math.isfinite(value)) or stamp < t0 or stamp > t_end:
            continue
        key = math.floor(stamp / bucket)
        groups.setdefault(key, []).append(value)
    out: list[tuple[float, float]] = []
    for key in sorted(groups):
        values = groups[key]
        centre = (key + 0.5) * bucket
        out.append((centre, sum(values) / len(values)))
    return tuple(out)


def _axis_row(width: int) -> Text:
    cells = [" "] * width
    labels = [(0, "-60s")]
    if width >= 30:
        labels.append((width // 2 - 2, "-30s"))
    labels.append((width - 3, "now"))
    for start, label in labels:
        for offset, char in enumerate(label):
            if 0 <= start + offset < width:
                cells[start + offset] = char
    return Text("".join(cells), no_wrap=True, overflow="crop")


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
) -> Text:
    """Return exactly ``height`` rows, each ``width`` cells wide (rows are cropped, never wrapped).

    Samples are averaged into time buckets of at least ``min_bucket`` seconds, so a fast refresh
    draws a smooth trend instead of per-read jitter.
    """
    width = max(1, width)
    height = max(1, height)
    bucket = max(WINDOW_SECONDS / width, min_bucket)
    max_gap = max(max_gap, 2.5 * bucket)
    series = tuple(
        Series(item.name, item.colour, bucketed(item.points, t_end - WINDOW_SECONDS, t_end, bucket), item.area)
        for item in series
    )
    header_rows = 1 if header is not None and height >= 2 else 0
    axis_rows = 1 if height - header_rows >= 2 else 0
    graph_rows = height - header_rows - axis_rows
    scale_top = scale_top if scale_top > 0 else 1.0
    braille = mode == "braille"
    kx, ky = (2, 4) if braille else (1, 8)
    dw, dh = width * kx, graph_rows * ky
    t0 = t_end - WINDOW_SECONDS

    lines: list[Text] = []
    if header_rows:
        head = header.copy()
        head.truncate(width, overflow="crop")
        head.pad_right(width - len(head))
        lines.append(head)

    if graph_rows <= 0:
        pass  # header only, for a one-row chart
    elif all(len(item.points) < 2 for item in series):
        blank = [" " * width for _ in range(graph_rows)]
        message = empty_text[:width]
        blank[graph_rows // 2] = message.center(width)[:width]
        for row in blank:
            lines.append(Text(row, style=palette.muted, no_wrap=True, overflow="crop"))
    else:
        grid: set[tuple[int, int]] = set()
        for fraction in GRID_FRACTIONS:
            level = round(fraction * (dh - 1))
            grid.update((x, level) for x in range(0, dw, 4 if braille else 2))

        # Bucket every dot into its cell once: cell = (column, row from top) -> dot codes.
        # A dot code is dot_x * 100 + dot_y_within_cell (bottom-up), so it fits both modes.
        def bucket(dots: set[tuple[int, int]]) -> dict[tuple[int, int], set[int]]:
            cells: dict[tuple[int, int], set[int]] = {}
            for x, y in dots:
                key = (x // kx, graph_rows - 1 - y // ky)
                cells.setdefault(key, set()).add((x % kx) * 100 + y % ky)
            return cells

        line_cells = [bucket(_series_dots(item, t0, dw, dh, scale_top, max_gap)) for item in series]
        area_cells: dict[tuple[int, int], set[int]] = {}
        for item, cells in zip(series, line_cells):
            if item.area:
                filled: set[tuple[int, int]] = set()
                for col_row, codes in cells.items():
                    for code in codes:
                        dot_x, within = divmod(code, 100)
                        base_y = (graph_rows - 1 - col_row[1]) * ky
                        x = col_row[0] * kx + dot_x
                        filled.update((x, yy) for yy in range(0, base_y + within))
                for key, codes in bucket(filled).items():
                    area_cells.setdefault(key, set()).update(codes)
        grid_cells = bucket(grid)
        # A baseline at 0 on the bottom row, so a low value is visibly above zero.
        baseline_cells = bucket({(x, 0) for x in range(dw)})

        for row in range(graph_rows):
            text = Text(no_wrap=True, overflow="crop")
            for col in range(width):
                key = (col, row)
                lines_here = [cells.get(key, set()) for cells in line_cells]
                area_here = area_cells.get(key, set())
                grid_here = grid_cells.get(key, set())
                baseline_here = baseline_cells.get(key, set())
                if not any(lines_here) and not area_here and not grid_here and not baseline_here:
                    text.append(" ")
                    continue
                content = bool(area_here) or any(lines_here)
                if braille:
                    mask = 0
                    for codes in (*lines_here, area_here, grid_here, baseline_here):
                        for code in codes:
                            dot_x, within = divmod(code, 100)
                            mask |= _BRAILLE_BIT[(dot_x, ky - 1 - within)]
                    glyph = chr(0x2800 + mask)
                else:
                    filled_rows = set().union(*lines_here, area_here)
                    if not filled_rows:
                        glyph = "▁" if baseline_here else "·"
                    elif len(filled_rows) == ky:
                        glyph = "█"
                    elif filled_rows == set(range(len(filled_rows))):
                        glyph = _EIGHTHS[len(filled_rows)]
                    else:
                        glyph = "▄" if min(filled_rows) < ky // 2 else "▀"
                if not content:
                    colour = palette.muted
                elif not palette.decorative:
                    colour = palette.foreground
                else:
                    # Line colour wins over area colour; area uses its series colour, dimmed.
                    colour = next(
                        (item.colour for item, codes in zip(series, lines_here) if codes),
                        next((item.colour for item in series if item.area), palette.muted),
                    )
                text.append(glyph, style=colour)
            lines.append(text)

    if axis_rows:
        axis = _axis_row(width)
        axis.stylize(palette.muted)
        lines.append(axis)
    return Text("\n").join(lines)


class ChartView(Static):
    """A graph widget that redraws only when its data or its size changes."""

    def __init__(self, *, id: str, mode: str = "braille") -> None:
        super().__init__("", id=id, markup=False)
        self._mode = mode
        self._spec: tuple | None = None
        self._last: tuple | None = None
        self.rendered: Text | None = None

    def set_chart(
        self,
        *,
        series: Sequence[Series],
        t_end: float,
        scale_top: float,
        header: Text | None,
        max_gap: float,
        min_bucket: float = 0.0,
    ) -> None:
        self._spec = (tuple(series), t_end, scale_top, header, max_gap, min_bucket)
        self._draw()

    def reset(self, message: str) -> None:
        self._spec = None
        self._last = None
        self.update(message)

    def on_resize(self) -> None:
        self._draw()

    def _draw(self) -> None:
        if self._spec is None:
            return
        width, height = self.content_size.width, self.content_size.height
        if width < 4 or height < 2:
            return
        series, t_end, scale_top, header, max_gap, min_bucket = self._spec
        key = (width, height, self._spec)
        if key == self._last:
            return
        self._last = key
        self.rendered = render_chart(
                series,
                width=width,
                height=height,
                t_end=t_end,
                scale_top=scale_top,
                header=header,
                max_gap=max_gap,
                mode=self._mode,
                min_bucket=min_bucket,
            )
        self.update(self.rendered)

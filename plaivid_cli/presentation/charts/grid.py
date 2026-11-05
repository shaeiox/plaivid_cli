"""Reusable chart-space geometry and fixed-window bucketing algorithms."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from rich.text import Text

if TYPE_CHECKING:
    from .render import Series

from plaivid_cli.application.overview import HISTORY_WINDOW_SECONDS

WINDOW_SECONDS = HISTORY_WINDOW_SECONDS


def _line_dots(points: Sequence[tuple[float, float]], dw: int, dh: int) -> set[tuple[int, int]]:
    """Connected dots for one run of samples (no gaps inside the run)."""
    out: set[tuple[int, int]] = set()
    if len(points) == 1:
        x, y = points[0]
        out.add((round(x), round(y)))
        return out
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
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


def _series_dots(
    series: Series, t0: float, dw: int, dh: int, scale: float, max_gap: float
) -> set[tuple[int, int]]:
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

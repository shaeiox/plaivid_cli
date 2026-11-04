"""Multi-row bar charts for the Overview: columns are coloured by row height (plasma ramp).

Presentation only. Samples come from the overview history; nothing here calls a provider.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from rich.text import Text

from plaivid_cli.presentation.theme import TRUECOLOR, Palette

# Matplotlib's "plasma" ramp, bottom (dark blue) to top (yellow). The top stop is the
# warning yellow on purpose: this chart follows the requested plasma look.
PLASMA_STOPS = (
    "#0d0887", "#47039f", "#7e03a8", "#9c179e", "#bd3786",
    "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921",
)

# Rows per Overview chart; the card grows by this much.
CHART_HEIGHT = 8

# Partial-cell glyphs, one eighth to seven eighths of a cell, bottom-up.
_EIGHTHS = " ▁▂▃▄▅▆▇"


def _rgb(colour: str) -> tuple[float, float, float]:
    value = colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def plasma(t: float) -> str:
    """Colour at position ``t`` (0 = bottom, 1 = top) along the plasma ramp."""
    t = min(1.0, max(0.0, t))
    scaled = t * (len(PLASMA_STOPS) - 1)
    index = min(int(scaled), len(PLASMA_STOPS) - 2)
    frac = scaled - index
    a, b = _rgb(PLASMA_STOPS[index]), _rgb(PLASMA_STOPS[index + 1])
    return "#{:02x}{:02x}{:02x}".format(*(round(a[i] + (b[i] - a[i]) * frac) for i in range(3)))


def resample(values: deque[tuple[float, float]], width: int) -> list[float]:
    """Exactly ``width`` columns, normalised to 0..1 across the sampled range (flat data -> 0)."""
    numbers = [value for _, value in values]
    width = max(2, width)
    high, low = max(numbers), min(numbers)
    last = len(numbers) - 1
    columns: list[float] = []
    for column in range(width):
        position = column * last / (width - 1)
        left = int(position)
        right = min(left + 1, last)
        fraction = position - left
        value = numbers[left] * (1 - fraction) + numbers[right] * fraction
        columns.append((value - low) / (high - low) if high > low else 0.0)
    return columns


def bar_chart(columns: Sequence[float], height: int, palette: Palette = TRUECOLOR) -> Text:
    """Render normalised columns (0..1) as ``height`` rows of block cells.

    Each cell takes the plasma colour of its row, so the bottom is dark and the top bright.
    Without colour (16-colour or NO_COLOR) every bar uses the palette foreground.
    """
    height = max(1, height)
    levels = height * 8
    text = Text(no_wrap=True, overflow="crop")
    for index, row in enumerate(range(height - 1, -1, -1)):  # top row first
        row_base = row * 8  # eighths below this row
        if index:
            text.append("\n")
        t = row / (height - 1) if height > 1 else 1.0
        colour = plasma(t) if palette.decorative else palette.foreground
        for value in columns:
            filled = min(levels, max(0.0, value * levels))
            remainder = min(8.0, max(0.0, filled - row_base))
            if remainder >= 8:
                text.append("█", style=colour)
            elif remainder > 0:
                text.append(_EIGHTHS[int(remainder)], style=colour)
            else:
                text.append(" ")
    return text

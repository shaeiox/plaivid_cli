"""Textual widget wrapper around the pure chart renderer."""

from __future__ import annotations

from collections.abc import Sequence

from rich.text import Text
from textual.widgets import Static

from .render import Series, render_chart


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

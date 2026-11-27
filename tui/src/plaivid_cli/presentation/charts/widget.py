"""Textual widget wrapper around the pure chart renderer."""

from __future__ import annotations

import inspect
from collections.abc import Sequence

from rich.text import Text
from textual.widgets import Static

from plaivid_cli.presentation.theme import TRUECOLOR, Palette

from .render import Series, render_chart

# Widget kwargs that are safe to forward to Textual's Static. Anything else a
# composition root passes (``palette``, ``chart_mode``, future theme hints, ...)
# is accepted and handled here instead of raising a TypeError while composing.
_FORWARDED = frozenset(
    set(inspect.signature(Static.__init__).parameters) - {"self", "renderable", "id", "markup"}
)


class ChartView(Static):
    """A graph widget that redraws only when its data or its size changes.

    ``ChartView`` is deliberately tolerant of extra keyword arguments: dashboards
    compose it with presentation options such as ``palette`` alongside the chart
    ``mode``. Unknown widget hints are ignored rather than breaking ``compose()``.
    """

    def __init__(
        self,
        id: str | None = None,
        *,
        mode: str = "braille",
        palette: Palette | None = None,
        y_labels: bool | None = None,
        **kwargs: object,
    ) -> None:
        # ``id`` is accepted positionally or by keyword; every other composition
        # hint is either forwarded to Static (when it is a real widget option) or
        # quietly handled here, so a dashboard never fails to compose.
        forwarded = {key: value for key, value in kwargs.items() if key in _FORWARDED}
        super().__init__("", id=id, markup=False, **forwarded)
        self._mode = mode
        self._palette: Palette = palette if palette is not None else TRUECOLOR
        self._y_labels = y_labels
        self._spec: tuple | None = None
        self._last: tuple | None = None
        self.rendered: Text | None = None

    def use_palette(self, palette: Palette) -> None:
        """Adopt the page's detected palette and redraw with it."""
        self._palette = palette
        self._last = None
        self._draw()

    def set_chart(
        self,
        *,
        series: Sequence[Series],
        t_end: float,
        scale_top: float,
        header: Text | None,
        max_gap: float,
        min_bucket: float = 0.0,
        **kwargs: object,
    ) -> None:
        palette = kwargs.get("palette")
        if isinstance(palette, Palette):
            self._palette = palette
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
            palette=self._palette,
            min_bucket=min_bucket,
            y_labels=self._y_labels,
        )
        self.update(self.rendered)

"""CPU telemetry card and its chart surface."""

from __future__ import annotations

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.widgets import Static

from plaivid_cli.presentation.charts import ChartView
from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import DashboardCard


class CPUCard(DashboardCard):
    """Present the current CPU summary and history chart without collecting data.

    All metrics/process stats sit above the ``ChartView``; the chart is the last
    child so its 60-second time axis is the bottom-most element of the card.
    """

    def __init__(self, palette: Palette, chart_mode: str) -> None:
        super().__init__(id="cpu-box", group="compute", title="CPU", palette=palette)
        self._chart_mode = chart_mode

    def compose(self) -> ComposeResult:
        yield Static("Loading monitoring data…", id="cpu-card", markup=False)
        yield ChartView(id="cpu-chart", mode=self._chart_mode, palette=self._palette)

    def set_summary(self, value: RenderableType) -> None:
        self.query_one("#cpu-card", Static).update(value)

    @property
    def chart(self) -> ChartView:
        return self.query_one("#cpu-chart", ChartView)

"""Load average and running VM card."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.widgets import Static

from plaivid_cli.presentation.charts import ChartView
from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import DashboardCard


class LoadCard(DashboardCard):
    """Present load summaries, trend chart, and verified running-VM count.

    Every text box (load averages, process stats and the Running VMs count) is
    composed **above** the chart: the ``ChartView`` is the last child, so its
    time axis is the bottom-most element of the card container.
    """

    def __init__(self, palette: Palette, chart_mode: str) -> None:
        super().__init__(id="load-box", group="compute", title="Load & tasks", palette=palette)
        self._chart_mode = chart_mode

    def compose(self) -> ComposeResult:
        # Metrics first, chart last. Status is centralised in the card header.
        yield Static("Loading monitoring data…", id="load-card", markup=False)
        yield Static("Running VMs…", id="running-card", markup=False)
        yield ChartView(id="load-chart", mode=self._chart_mode, palette=self._palette)

    @property
    def chart(self) -> ChartView:
        return self.query_one("#load-chart", ChartView)

    def set_summary(self, value: RenderableType) -> None:
        self.query_one("#load-card", Static).update(value)

    def set_running(self, value: RenderableType) -> None:
        self.query_one("#running-card", Static).update(value)

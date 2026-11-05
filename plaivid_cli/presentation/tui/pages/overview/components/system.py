"""Host identity and operating-system details card."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.widgets import Static

from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import DashboardCard


class SystemCard(DashboardCard):
    """Present local host identity separately from generic OS metrics."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="system-card", group="host", title="System information", palette=palette
        )

    def compose(self) -> ComposeResult:
        yield Static("LOCAL HOST  N/A", id="host-identity", markup=False)
        yield Static("Waiting for collection…", id="metrics-system", markup=False)

    def set_identity(self, value: RenderableType) -> None:
        self.query_one("#host-identity", Static).update(value)

    def set_metrics(self, value: RenderableType) -> None:
        self.query_one("#metrics-system", Static).update(value)

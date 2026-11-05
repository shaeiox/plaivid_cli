"""Top-process and command summary card."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from plaivid_cli.presentation.theme import Palette, group_title
from plaivid_cli.presentation.tui.components import DashboardCard


class ProcessesCard(DashboardCard):
    """Present process samples and grouped commands from the supplied snapshot."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="processes-card", group="compute", title="Top processes by CPU", palette=palette
        )

    def compose(self) -> ComposeResult:
        with Horizontal(id="process-row"):
            yield Static("Waiting for collection…", id="metrics-processes", markup=False)
            yield Static("", id="metrics-commands", markup=False)

    def set_processes(self, value: RenderableType) -> None:
        self.query_one("#metrics-processes", Static).update(value)

    def set_commands(self, value: RenderableType) -> None:
        self.query_one("#metrics-commands", Static).update(value)

    def set_title(self, title: str) -> None:
        self.border_title = group_title("compute", title, self._palette)

"""Memory telemetry card."""

from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import TextDashboardCard


class MemoryCard(TextDashboardCard):
    """Display the host memory summary and trend-independent swap details."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="memory-box",
            group="compute",
            title="Memory",
            palette=palette,
            content_id="memory-card",
            initial="Loading monitoring data…",
        )

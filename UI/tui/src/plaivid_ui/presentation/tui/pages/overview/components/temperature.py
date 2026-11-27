"""Temperature sensor card."""

from plaivid_ui.presentation.theme import Palette
from plaivid_ui.presentation.tui.components import TextDashboardCard


class TemperatureCard(TextDashboardCard):
    """Display formatted sensor readings without querying local sensors directly."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="temperature-box",
            group="environment",
            title="Temperature",
            palette=palette,
            content_id="metrics-temperature",
        )

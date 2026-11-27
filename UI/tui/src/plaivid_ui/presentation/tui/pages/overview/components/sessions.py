"""Logged-in session card."""

from plaivid_ui.presentation.theme import Palette
from plaivid_ui.presentation.tui.components import TextDashboardCard


class SessionsCard(TextDashboardCard):
    """Display the current session summary as already-formatted text."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="sessions-box",
            group="environment",
            title="Sessions",
            palette=palette,
            content_id="metrics-sessions",
        )

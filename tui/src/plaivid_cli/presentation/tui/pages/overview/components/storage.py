"""Filesystem capacity card."""

from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import TextDashboardCard


class StorageCard(TextDashboardCard):
    """Display formatted filesystem capacity supplied by the Overview presenter."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(
            id="storage-box",
            group="io",
            title="Storage",
            palette=palette,
            content_id="metrics-storage",
        )

"""Reusable card and summary-tile widgets; they display values but own no domain state."""

from __future__ import annotations

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from plaivid_cli.presentation.theme import Palette, group_color, group_title


class DashboardCard(Vertical):
    """A themed Overview card with a stable group and title."""

    def __init__(self, *, id: str, group: str, title: str, palette: Palette) -> None:
        super().__init__(id=id, classes="card")
        self._group = group
        self._title = title
        self._status = ""
        self.use_palette(palette)

    def use_palette(self, palette: Palette) -> None:
        """Set the presentation palette supplied by the page composition root."""
        self._palette = palette
        self._apply_header()
        colour = group_color(self._group, palette)
        if colour is not None:
            self.styles.border = ("round", colour)

    def set_status(self, status: str) -> None:
        """Keep the card's one collection-status indicator in its header.

        Child metric widgets show measurements only; repeating ``ONLINE`` at the
        bottom of each of them made the same state look like several readings.
        """
        if status == self._status:
            return
        self._status = status
        self._apply_header()

    def set_title(self, title: str) -> None:
        """Replace the card title while preserving its centralised status label."""
        self._title = title
        self._apply_header()

    def _apply_header(self) -> None:
        palette = getattr(self, "_palette", None)
        if palette is None:
            return
        title = group_title(self._group, self._title, palette)
        if self._status:
            title.append(f"  ·  {self._status}", style=palette.muted)
        self.border_title = title


class TextDashboardCard(DashboardCard):
    """Card with one typed-by-ID text body for a small telemetry section."""

    def __init__(
        self,
        *,
        id: str,
        group: str,
        title: str,
        palette: Palette,
        content_id: str,
        initial: str = "Waiting for collection…",
    ) -> None:
        super().__init__(id=id, group=group, title=title, palette=palette)
        self._content_id = content_id
        self._initial = initial

    def compose(self) -> ComposeResult:
        yield Static(self._initial, id=self._content_id, markup=False)

    def set_content(self, value: RenderableType) -> None:
        """Display already-presented content; formatting and collection stay outside the widget."""
        self.query_one(f"#{self._content_id}", Static).update(value)


class MetricTile(Vertical):
    """Compact, reusable summary value used by inventory pages."""

    def __init__(self, *, title: str, value_id: str, initial: str, palette: Palette) -> None:
        super().__init__(classes="metric-card")
        self._title = group_title("vms", title, palette)
        self._value_id = value_id
        self._initial = initial

    def compose(self):
        yield Static(self._title, classes="metric-title")
        yield Static(self._initial, id=self._value_id, classes="metric-value")

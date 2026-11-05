"""Overview page composition; telemetry is supplied by its page controller."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Static, TabPane

from plaivid_cli.presentation.theme import Palette

from .components import (
    CPUCard,
    HostStatusCard,
    LoadCard,
    MemoryCard,
    NetworkCard,
    ProcessesCard,
    SessionsCard,
    StorageCard,
    SystemCard,
    TemperatureCard,
)


class OverviewPage(TabPane):
    """The Overview page and its independently composed telemetry cards."""

    def __init__(
        self,
        palette: Palette,
        chart_mode: str,
        refresh_interval: float,
        *,
        on_rediscover: Callable[[], None],
        on_select_interface: Callable[[str], None],
    ) -> None:
        super().__init__("Overview", id="overview")
        self._palette = palette
        self._chart_mode = chart_mode
        self._refresh_interval = refresh_interval
        self._on_rediscover = on_rediscover
        self._on_select_interface = on_select_interface

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="overview-scroll"):
            with Horizontal(id="overview-toolbar"):
                yield Static("Host telemetry", id="overview-title")
                yield Static(f"Refresh: {self._refresh_interval:g}s", id="refresh-label")
                yield Input(
                    value=f"{self._refresh_interval:g}", id="interval-input", placeholder="sec"
                )
                yield Button("Apply", id="interval-apply")
                yield Button("Refresh", id="overview-refresh")
            yield Static("", id="interval-error", markup=False)
            with Grid(id="overview-grid"):
                with Vertical(classes="card-column", id="col-left"):
                    yield NetworkCard(
                        self._palette,
                        on_rediscover=self._on_rediscover,
                        on_select_interface=self._on_select_interface,
                    )
                    yield StorageCard(self._palette)
                    yield SessionsCard(self._palette)
                with Vertical(classes="card-column", id="col-center"):
                    yield HostStatusCard(self._palette)
                    yield SystemCard(self._palette)
                    yield LoadCard(self._palette, self._chart_mode)
                with Vertical(classes="card-column", id="col-right"):
                    yield CPUCard(self._palette, self._chart_mode)
                    yield MemoryCard(self._palette)
                    yield TemperatureCard(self._palette)
            yield ProcessesCard(self._palette)

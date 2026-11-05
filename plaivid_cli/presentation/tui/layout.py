"""Application shell composition; each tab delegates to a dedicated page module."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Input, Label, Static, TabbedContent

from plaivid_cli.presentation.theme import brand

from .pages.overview import OverviewPage
from .pages.virtual_desktops import VirtualDesktopPage
from .pages.virtual_machines import VirtualMachinePage


class LayoutMixin:
    """Construct the shell and mount page entry points without page-specific markup."""

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            with Horizontal(id="topbar"):
                yield Static(brand(self._palette), id="brand", markup=False)
                yield Static("● Offline", id="session-label", markup=False)
                yield Button("Exit", id="logout", variant="default")
            with VerticalScroll(id="login-box"):
                yield Label("Operator sign-in", id="login-title")
                yield Static(
                    "Credentials are sent only to the configured local sbell command. "
                    "Password/token process-argument exposure is unresolved and denied by default.",
                    id="login-warning",
                )
                yield Input(
                    value=self.application.settings.default_username,
                    placeholder="Username",
                    id="username",
                )
                yield Input(password=True, placeholder="Password", id="password")
                yield Static("", id="login-error", markup=False)
                with Horizontal(id="login-buttons"):
                    yield Button("Sign in", id="login", variant="primary")
            with TabbedContent(initial="overview", id="tabs"):
                yield OverviewPage(
                    self._palette,
                    self._chart_mode,
                    self._overview_schedule.interval,
                    on_rediscover=self.rediscover,
                    on_select_interface=self.select_nic,
                )
                yield VirtualMachinePage(self._palette)
                yield VirtualDesktopPage(self._palette)
            yield Static(
                "1 Overview · 2 Virtual Machines · 3 Virtual Desktops · R refresh · Q quit",
                id="notice",
            )
            yield Footer()

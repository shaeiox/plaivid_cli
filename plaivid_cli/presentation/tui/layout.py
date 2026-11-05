"""Dashboard widget composition, isolated from application behavior."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from plaivid_cli.presentation.charts import ChartView
from plaivid_cli.presentation.theme import brand, group_title

from .support import BULK_ACTIONS, CheckableTable, _action_label


class LayoutMixin:
    """Construct the static page/widget tree for the TUI."""

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
                with TabPane("Overview", id="overview"):
                    with VerticalScroll(id="overview-scroll"):
                        with Horizontal(id="overview-toolbar"):
                            yield Static("Host telemetry", id="overview-title")
                            yield Static(
                                f"Refresh: {self._overview_schedule.interval:g}s",
                                id="refresh-label",
                            )
                            yield Input(
                                value=f"{self._overview_schedule.interval:g}",
                                id="interval-input",
                                placeholder="sec",
                            )
                            yield Button("Apply", id="interval-apply")
                            yield Button("Refresh", id="overview-refresh")
                        yield Static("", id="interval-error", markup=False)
                        with Grid(id="overview-grid"):
                            with Vertical(classes="card-column", id="col-left"):
                                with Vertical(classes="card", id="network-box") as box:
                                    self._group_box(box, "io", "Network interfaces")
                                    yield Static(
                                        "Waiting for collection…",
                                        id="metrics-network",
                                        markup=False,
                                    )
                                    with Horizontal(id="nic-tabs"):
                                        pass
                                    yield Static(
                                        "Discovering physical interfaces…",
                                        id="nic-detail",
                                        markup=False,
                                    )
                                    yield Button("Rediscover", id="rediscover")
                                with Vertical(classes="card", id="storage-box") as box:
                                    self._group_box(box, "io", "Storage")
                                    yield Static(
                                        "Waiting for collection…",
                                        id="metrics-storage",
                                        markup=False,
                                    )
                                with Vertical(classes="card", id="sessions-box") as box:
                                    self._group_box(box, "environment", "Sessions")
                                    yield Static(
                                        "Waiting for collection…",
                                        id="metrics-sessions",
                                        markup=False,
                                    )
                            with Vertical(classes="card-column", id="col-center"):
                                with Vertical(classes="card", id="host-status-box") as box:
                                    self._group_box(box, "host", "Host status")
                                    yield Static("", id="host-logo", markup=False)
                                    yield Static("", id="host-banner", markup=False)
                                    yield Static(
                                        "Waiting for collection…", id="host-status", markup=False
                                    )
                                with Vertical(classes="card", id="system-card") as box:
                                    self._group_box(box, "host", "System information")
                                    yield Static(
                                        "LOCAL HOST  N/A", id="host-identity", markup=False
                                    )
                                    yield Static(
                                        "Waiting for collection…", id="metrics-system", markup=False
                                    )
                                with Vertical(classes="card", id="load-box") as box:
                                    self._group_box(box, "compute", "Load & tasks")
                                    yield Static(
                                        "Loading monitoring data…", id="load-card", markup=False
                                    )
                                    yield ChartView(id="load-chart", mode=self._chart_mode)
                                    yield Static("Running VMs…", id="running-card", markup=False)
                            with Vertical(classes="card-column", id="col-right"):
                                with Vertical(classes="card", id="cpu-box") as box:
                                    self._group_box(box, "compute", "CPU")
                                    yield Static(
                                        "Loading monitoring data…", id="cpu-card", markup=False
                                    )
                                    yield ChartView(id="cpu-chart", mode=self._chart_mode)
                                with Vertical(classes="card", id="memory-box") as box:
                                    self._group_box(box, "compute", "Memory")
                                    yield Static(
                                        "Loading monitoring data…", id="memory-card", markup=False
                                    )
                                with Vertical(classes="card", id="temperature-box") as box:
                                    self._group_box(box, "environment", "Temperature")
                                    yield Static(
                                        "Waiting for collection…",
                                        id="metrics-temperature",
                                        markup=False,
                                    )
                        with Vertical(classes="card", id="processes-card") as box:
                            self._group_box(box, "compute", "Top processes by CPU")
                            with Horizontal(id="process-row"):
                                yield Static(
                                    "Waiting for collection…", id="metrics-processes", markup=False
                                )
                                yield Static("", id="metrics-commands", markup=False)
                with TabPane("Virtual Machines", id="fleet"):
                    with Horizontal(id="fleet-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Defined VMs", self._palette),
                                classes="metric-title",
                            )
                            yield Static("—", id="vm-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Processes seen", self._palette),
                                classes="metric-title",
                            )
                            yield Static("—", id="process-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Inventory", self._palette),
                                classes="metric-title",
                            )
                            yield Static(
                                "Not collected", id="inventory-quality", classes="metric-value"
                            )
                        yield Button("Refresh", id="refresh-button", variant="primary")
                    with Vertical(id="vm-list"):
                        with Horizontal(id="vm-toolbar"):
                            yield Select(
                                [(_action_label(action), action.value) for action in BULK_ACTIONS],
                                prompt="Bulk action",
                                allow_blank=True,
                                id="bulk-actions",
                            )
                            yield Checkbox("Apply to all VMs", id="select-all")
                            yield Button("Audit", id="audit-toggle")
                            yield Input(placeholder="Search VM name", id="vm-search")
                        yield CheckableTable(
                            id="fleet-table", cursor_type="row", zebra_stripes=True
                        )
                        yield Static("No operation submitted.", id="action-status", markup=False)
                    yield Static("Selected VM · 0 target(s)", id="vm-scope", markup=False)
                    yield Static(
                        "Select a VM to inspect its details.", id="detail-box", markup=False
                    )
                    yield Static(
                        "Read-only audit\nWaiting for session…", id="audit-panel", markup=False
                    )
                with TabPane("Virtual Desktops", id="desktops"):
                    with Horizontal(id="desktop-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Defined Desktops", self._palette),
                                classes="metric-title",
                            )
                            yield Static("—", id="desktop-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Selected", self._palette),
                                classes="metric-title",
                            )
                            yield Static("—", id="desktop-selected-label", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static(
                                group_title("vms", "Inventory", self._palette),
                                classes="metric-title",
                            )
                            yield Static(
                                "Not collected", id="desktop-quality", classes="metric-value"
                            )
                        yield Button("Refresh", id="desktop-refresh", variant="primary")
                    with Vertical(id="desktop-list"):
                        with Horizontal(id="desktop-toolbar"):
                            yield Select(
                                [(_action_label(action), action.value) for action in BULK_ACTIONS],
                                prompt="Bulk action",
                                allow_blank=True,
                                id="desktop-actions",
                            )
                            yield Checkbox("Apply to all Desktops", id="desktop-all")
                            yield Button("Audit", id="desktop-audit-toggle")
                            yield Input(placeholder="Search Desktop name", id="desktop-search")
                        yield CheckableTable(
                            id="desktop-table", cursor_type="row", zebra_stripes=True
                        )
                        yield Static(
                            "No operation submitted.", id="desktop-action-status", markup=False
                        )
                    yield Static("Selected Desktop · 0 target(s)", id="desktop-scope", markup=False)
                    with VerticalScroll(id="desktop-detail-scroll"):
                        yield Static(
                            "Select a Desktop to inspect its details.",
                            id="desktop-detail",
                            markup=False,
                        )
                    yield Static(
                        "Read-only audit\nWaiting for session…",
                        id="desktop-audit-panel",
                        markup=False,
                    )
            yield Static(
                "1 Overview · 2 Virtual Machines · 3 Virtual Desktops · R refresh · Q quit",
                id="notice",
            )
            yield Footer()

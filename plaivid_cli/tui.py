"""Textual presentation for the local PVM management application."""

from __future__ import annotations

import os

from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.overview import OverviewHistory, OverviewSchedule
from plaivid_cli.application.services import (
    PlaividApplication,
    TargetSelection,
    as_host_metrics,
    as_host_status,
    as_vm_detail,
)
from plaivid_cli.application.session import SessionManager
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    ApplicationSnapshot,
    CollectionStatus,
    HostMetrics,
    HostStatus,
    InventoryData,
    OperationPlan,
    OperationResult,
    PvmSession,
    SectionSnapshot,
    VMDetail,
    VMRecord,
)
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation import host_metrics as hm
from plaivid_cli.presentation.overview import cards, nic_details
from plaivid_cli.presentation.theme import (
    apply_theme,
    brand,
    palette_for,
    state_text,
    styled_metric,
)

DESKTOP_MIN_REFRESH_SECONDS = 15.0  # Conservative provisional cadence; manual Refresh is explicit.

BULK_ACTIONS: tuple[Action, ...] = (
    Action.START,
    Action.RESUME,
    Action.PAUSE,
    Action.STOP,
    Action.RESET,
    Action.KILL,
)


def _action_label(action: Action) -> str:
    return action.value.title()


_METRIC_PANELS = (
    "metrics-system", "metrics-network", "metrics-storage", "metrics-temperature",
    "metrics-sessions", "metrics-processes", "metrics-commands",
)

class PlaividTui(App[None]):
    """Operator dashboard; all I/O is delegated to application coordinators."""

    TITLE = "Plaivid PVM Console"
    SUB_TITLE = "Local management · Linux"
    # Semantic tokens mirror the Plaivid Textual theme, including native controls.
    CSS = """
        Screen { background: $p-bg; color: $p-text; }
        #shell { height: 1fr; padding: 0 1; background: $p-bg; }
        #topbar { height: 2; padding: 0 1; margin: 0 0 1 0;
                  background: $p-panel; border-bottom: solid $p-border; }
        #brand { width: 1fr; content-align: left middle; }
        #session-label { width: auto; color: $p-green; content-align: right middle; padding: 0 1; }
        #logout { width: 6; min-width: 6; height: 1; margin: 0; padding: 0;
                  background: $p-surface; color: $p-rose; border: none; }
        #logout:focus { background: $p-surface; color: $p-rose; text-style: bold underline; }

        #login-box { width: 64; max-width: 92%; height: auto; border-left: solid $p-blue;
                     background: $p-panel; padding: 1 2; margin: 2 0; }
        #login-title { color: $p-blue; text-style: bold; padding-bottom: 1; }
        #login-warning { color: $p-yellow; padding: 1 0; }
        #login-error { color: $p-rose; padding: 1 0; }
        #login-buttons { height: 1; align-horizontal: right; margin-top: 1; }
        Input { background: $p-surface; border: solid $p-border; color: $p-text; }
        Input:focus { border: solid $p-blue; }

        /* One-line actions in every page; reserve filled color for keyboard focus. */
        Button, Button.-primary, Button.-style-default, Button.-style-flat {
            height: 1; min-width: 0; width: auto; padding: 0 1;
            border: none; background: $p-panel; color: $p-text;
        }
        Button.-primary { color: $p-blue; text-style: bold; }
        Button:hover, Button.-primary:hover { border: none; background: $p-surface; color: $p-blue; }
        Button:focus, Button.-primary:focus {
            border: none; background: $p-surface; color: $p-blue; text-style: bold underline;
        }
        Button:disabled { border: none; background: $p-panel; color: $p-muted; }
        Select { height: 1; color: $p-text; }
        Select > SelectCurrent {
            height: 1; padding: 0 1; border: none; background: $p-surface; color: $p-text;
        }
        Select:focus > SelectCurrent {
            border: none; background: $p-surface; color: $p-blue; text-style: bold;
        }
        Checkbox { height: 1; padding: 0; border: none; background: $p-panel; color: $p-muted; }
        Checkbox:focus { border: none; background: $p-surface; color: $p-blue; }
        Checkbox.-on { color: $p-text; }

        TabbedContent { height: 1fr; background: $p-bg; }
        TabbedContent > ContentTabs { background: $p-panel; }
        TabbedContent Tab { color: $p-muted; background: $p-panel; }
        TabbedContent Tab.-active { color: $p-bg; background: $p-blue; text-style: bold; }
        TabbedContent Tab:focus { text-style: bold; }
        TabPane { padding: 0 1; background: $p-bg; }
        Footer { background: $p-panel; color: $p-text; }
        #notice { height: 1; color: $p-muted; padding: 0 1; }

        #overview { height: 1fr; }
        #overview-scroll { height: 1fr; scrollbar-color: $p-border; }
        #overview-toolbar { height: 3; background: $p-panel; border-bottom: solid $p-border;
                            padding: 0 1; margin-top: 1; }
        #overview-title { width: 1fr; color: $p-blue; text-style: bold; }
        #refresh-label { width: 14; color: $p-cyan; }
        #interval-input { width: 5; height: 1; margin: 0 1; padding: 0 1;
                          border: none; background: $p-surface; color: $p-cyan; }
        #interval-input:focus { border: none; background: $p-surface; color: $p-cyan; text-style: underline; }
        #interval-apply { width: 8; min-width: 8; height: 1; padding: 0; }
        #overview-refresh, #rediscover { width: 11; min-width: 11; height: 1; padding: 0; }
        #overview-toolbar Button { border: none; background: $p-surface;
                                   color: $p-cyan; text-style: bold; }
        #overview-toolbar Button:focus { background: $p-surface; color: $p-blue; text-style: bold underline; }
        #interval-error { height: 1; color: $p-rose; }
        #host-identity { height: auto; color: $p-muted; }
        #overview-grid { height: auto; grid-size: 1; grid-gutter: 1 2; grid-rows: auto; margin-top: 1; }
        .cols-2 #overview-grid { grid-size: 2; }
        .cols-2 #col-right { column-span: 2; }
        .cols-3 #overview-grid { grid-size: 3; }
        .card-column { height: auto; }
        .card-column > .card { margin-bottom: 1; }
        .card { height: auto; background: $p-panel; border: round $p-border; padding: 0 1;
                border-title-color: $p-blue; border-title-style: bold; color: $p-text; }
        .card Static { height: auto; background: $p-panel; color: $p-text; }
        #cpu-chart, #load-chart { width: 100%; color: $p-cyan; margin-top: 1; text-wrap: nowrap; text-overflow: clip; }
        #running-card { color: $p-cyan; margin-top: 1; }
        #host-status { color: $p-text; }
        #nic-tabs { height: auto; }
        #nic-tabs .nic-tab { width: auto; min-width: 0; height: 1; margin-right: 2; padding: 0 1;
                             border: none; background: $p-surface; color: $p-muted; }
        #nic-tabs .nic-tab:hover { background: $p-panel; color: $p-text; }
        #nic-tabs .nic-tab:focus { text-style: underline; }
        #nic-tabs .nic-tab.-primary, #nic-tabs .nic-tab.-primary:hover, #nic-tabs .nic-tab.-primary:focus {
            background: $p-blue; color: $p-bg; text-style: bold; }
        #nic-detail { height: auto; color: $p-muted; margin-top: 1; }
        #rediscover { margin: 1 0 0 0; }
        #processes-card { margin-top: 1; }
        #process-row { height: auto; }
        #metrics-processes { width: 1fr; }
        #metrics-commands { width: 36; border-left: solid $p-border; padding-left: 1; color: $p-cyan; }
        .cols-1 #process-row, .cols-2 #process-row { layout: vertical; }
        .cols-1 #metrics-processes, .cols-2 #metrics-processes { width: 100%; }
        .cols-1 #metrics-commands, .cols-2 #metrics-commands { width: 100%; border-left: none;
                                                              border-top: solid $p-border;
                                                              padding: 1 0 0 0; margin-top: 1; }
        #fleet-summary { height: 5; margin-top: 1; align-vertical: middle; }
        .metric-card { width: 1fr; height: 5; margin-right: 1; padding: 0 1;
                       border-left: solid $p-border; background: $p-surface; }
        .metric-card:focus-within { border-left: solid $p-blue; }
        .metric-title { color: $p-muted; text-style: bold; }
        .metric-value { color: $p-cyan; text-style: bold; }
        #refresh-button { width: 11; min-width: 11; margin: 0 0 0 1; }
        #vm-list { height: 1fr; min-height: 13; border: round $p-border;
                   background: $p-panel; }
        #vm-toolbar { height: 3; padding: 0 1; align-vertical: middle; background: $p-panel; }
        #bulk-actions { width: 20; }
        #select-all { width: auto; margin-left: 2; }
        #audit-toggle { width: 11; min-width: 11; margin-left: 2; }
        #fleet-table { height: 1fr; min-height: 8; background: $p-surface;
                       border: round $p-border; }
        DataTable > .datatable--header { background: $p-panel; color: $p-text; text-style: bold; }
        DataTable:focus > .datatable--cursor { background: $p-blue; color: $p-bg; }
        #detail-box { height: 10; margin-top: 1; border: round $p-border;
                      background: $p-panel; padding: 1; }
        #action-status { height: 1; color: $p-yellow; }
        #desktop-summary { height: 5; margin-top: 1; align-vertical: middle; }
        #desktop-refresh { width: 11; min-width: 11; margin: 0 0 0 1; }
        #desktop-list { height: 1fr; min-height: 13; border: round $p-border;
                        background: $p-panel; }
        #desktop-toolbar { height: 3; padding: 0 1; align-vertical: middle;
                           background: $p-panel; }
        #desktop-actions { width: 20; }
        #desktop-all { width: auto; margin-left: 2; }
        #desktop-audit-toggle { width: 11; min-width: 11; margin-left: 2; }
        #desktop-search, #vm-search { width: 1fr; height: 1; margin-left: 1; padding: 0 1;
                                      border: none; background: $p-surface; }
        #desktop-search:focus, #vm-search:focus { border: none; background: $p-surface;
                                                  color: $p-blue; text-style: underline; }
        #desktop-table { height: 1fr; min-height: 8; background: $p-surface;
                         border: round $p-border; }
        #desktop-scope, #vm-scope { height: 1; color: $p-muted; }
        #desktop-detail-scroll { height: 10; margin-top: 1;
                                 border: round $p-border; background: $p-panel; }
        #desktop-audit-panel { display: none; height: auto; min-height: 7;
                               border: round $p-border; background: $p-panel; padding: 1; }
        #desktop-detail { height: auto; background: $p-panel; padding: 1; }
        #desktop-action-status { height: auto; color: $p-yellow; }
        #audit-panel { display: none; height: auto; min-height: 7;
                       border: round $p-border; background: $p-panel; padding: 1; }
        """
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("enter", "details", "Details"),
        ("q", "quit", "Quit"),
        ("1", "overview_page", "Overview"),
        ("2", "vms_page", "Virtual Machines"),
        ("3", "desktops_page", "Virtual Desktops"),
    ]

    def __init__(
        self,
        application: PlaividApplication,
        operations: OperationCoordinator,
        sessions: SessionManager,
    ) -> None:
        super().__init__()
        self._palette = palette_for(self.console.color_system, no_color="NO_COLOR" in os.environ)
        # Textual parses App.CSS at run time; Textual declares CSS as a ClassVar,
        # but its loader reads the instance attribute (also on Textual 0.47).
        object.__setattr__(self, "CSS", self._palette.css_tokens() + type(self).CSS)
        self.application = application
        self.operations = operations
        self.sessions = sessions
        self.session: PvmSession | None = None
        self._inventory_section: SectionSnapshot[object] | None = None
        self._inventory: InventoryData | None = None
        self._records: dict[str, VMRecord] = {}
        self._selected_uuid: str | None = None
        self._detail_base = "Select a VM to inspect its details."
        self._refresh_timer = None
        self._operation_active = False
        self._refresh_busy = False
        self._pending_manual_refresh = False
        self._session_epoch = 0
        self._inventory_generation: int | None = None
        self._table_order: tuple[str, ...] = ()
        self._table_content: dict[str, tuple[str, ...]] = {}
        self._table_columns = ()
        self._render_cache: dict[str, str] = {}
        self._overview_schedule = OverviewSchedule(
            min(60, max(1, application.settings.refresh_interval))
        )
        self._history = OverviewHistory()
        self._nic_selected: str | None = None
        self._nic_tab_names: tuple[str, ...] = ()
        self._fleet_due = 0.0
        self._visible_snapshot: ApplicationSnapshot | None = None
        self._desktops: dict[str, VirtualDesktop] = {}
        self._desktop_selected: str | None = None
        self._desktop_section: SectionSnapshot[object] | None = None
        self._desktop_generation: int | None = None
        self._desktop_min_generation = application.collection.snapshot.generation
        self._desktop_rows: tuple[str, ...] = ()
        self._desktop_cells: dict[str, tuple[str, ...]] = {}

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
                yield Input(value=self.application.settings.default_username, placeholder="Username", id="username")
                yield Input(password=True, placeholder="Password", id="password")
                yield Static("", id="login-error", markup=False)
                with Horizontal(id="login-buttons"):
                    yield Button("Sign in", id="login", variant="primary")
            with TabbedContent(initial="overview", id="tabs"):
                with TabPane("Overview", id="overview"):
                    with VerticalScroll(id="overview-scroll"):
                        with Horizontal(id="overview-toolbar"):
                            yield Static("Host telemetry", id="overview-title")
                            yield Static(f"Refresh: {self._overview_schedule.interval:g}s", id="refresh-label")
                            yield Input(value=f"{self._overview_schedule.interval:g}", id="interval-input", placeholder="sec")
                            yield Button("Apply", id="interval-apply")
                            yield Button("Refresh", id="overview-refresh")
                        yield Static("", id="interval-error", markup=False)
                        with Grid(id="overview-grid"):
                            with Vertical(classes="card-column", id="col-left"):
                                with Vertical(classes="card", id="network-box") as box:
                                    box.border_title = "Network interfaces"
                                    yield Static("Waiting for collection…", id="metrics-network", markup=False)
                                    with Horizontal(id="nic-tabs"):
                                        pass
                                    yield Static("Discovering physical interfaces…", id="nic-detail", markup=False)
                                    yield Button("Rediscover", id="rediscover")
                                with Vertical(classes="card", id="storage-box") as box:
                                    box.border_title = "Storage"
                                    yield Static("Waiting for collection…", id="metrics-storage", markup=False)
                                with Vertical(classes="card", id="sessions-box") as box:
                                    box.border_title = "Sessions"
                                    yield Static("Waiting for collection…", id="metrics-sessions", markup=False)
                            with Vertical(classes="card-column", id="col-center"):
                                with Vertical(classes="card", id="system-card") as box:
                                    box.border_title = "System information"
                                    yield Static("LOCAL HOST  N/A", id="host-identity", markup=False)
                                    yield Static("Waiting for collection…", id="metrics-system", markup=False)
                                with Vertical(classes="card", id="load-box") as box:
                                    box.border_title = "Load & tasks"
                                    yield Static("Loading monitoring data…", id="load-card", markup=False)
                                    yield Static("Waiting for samples", id="load-chart", markup=False)
                                    yield Static("Running VMs…", id="running-card", markup=False)
                            with Vertical(classes="card-column", id="col-right"):
                                with Vertical(classes="card", id="cpu-box") as box:
                                    box.border_title = "CPU"
                                    yield Static("Loading monitoring data…", id="cpu-card", markup=False)
                                    yield Static("Waiting for samples", id="cpu-chart", markup=False)
                                with Vertical(classes="card", id="memory-box") as box:
                                    box.border_title = "Memory"
                                    yield Static("Loading monitoring data…", id="memory-card", markup=False)
                                with Vertical(classes="card", id="temperature-box") as box:
                                    box.border_title = "Temperature"
                                    yield Static("Waiting for collection…", id="metrics-temperature", markup=False)
                                with Vertical(classes="card", id="host-status-box") as box:
                                    box.border_title = "Host status"
                                    yield Static("Waiting for collection…", id="host-status", markup=False)
                        with Vertical(classes="card", id="processes-card") as box:
                            box.border_title = "Top processes by CPU"
                            with Horizontal(id="process-row"):
                                yield Static("Waiting for collection…", id="metrics-processes", markup=False)
                                yield Static("", id="metrics-commands", markup=False)
                with TabPane("Virtual Machines", id="fleet"):
                    with Horizontal(id="fleet-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static("Defined VMs", classes="metric-title")
                            yield Static("—", id="vm-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("Processes seen", classes="metric-title")
                            yield Static("—", id="process-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("Inventory", classes="metric-title")
                            yield Static("Not collected", id="inventory-quality", classes="metric-value")
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
                        yield DataTable(id="fleet-table", cursor_type="row", zebra_stripes=True)
                        yield Static("No operation submitted.", id="action-status", markup=False)
                    yield Static("Selected VM · 0 target(s)", id="vm-scope", markup=False)
                    yield Static("Select a VM to inspect its details.", id="detail-box", markup=False)
                    yield Static("Read-only audit\nWaiting for session…", id="audit-panel", markup=False)
                with TabPane("Virtual Desktops", id="desktops"):
                    with Horizontal(id="desktop-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static("Defined Desktops", classes="metric-title")
                            yield Static("—", id="desktop-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("Selected", classes="metric-title")
                            yield Static("—", id="desktop-selected-label", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("Inventory", classes="metric-title")
                            yield Static("Not collected", id="desktop-quality", classes="metric-value")
                        yield Button("Refresh", id="desktop-refresh", variant="primary")
                    with Vertical(id="desktop-list"):
                        with Horizontal(id="desktop-toolbar"):
                            yield Select(
                                [(_action_label(action), action.value) for action in BULK_ACTIONS],
                                prompt="Bulk action", allow_blank=True, id="desktop-actions",
                            )
                            yield Checkbox("Apply to all Desktops", id="desktop-all")
                            yield Button("Audit", id="desktop-audit-toggle")
                            yield Input(placeholder="Search Desktop name", id="desktop-search")
                        yield DataTable(id="desktop-table", cursor_type="row", zebra_stripes=True)
                        yield Static("No operation submitted.", id="desktop-action-status", markup=False)
                    yield Static("Selected Desktop · 0 target(s)", id="desktop-scope", markup=False)
                    with VerticalScroll(id="desktop-detail-scroll"):
                        yield Static("Select a Desktop to inspect its details.", id="desktop-detail", markup=False)
                    yield Static("Read-only audit\nWaiting for session…", id="desktop-audit-panel", markup=False)
            yield Static("1 Overview · 2 Virtual Machines · 3 Virtual Desktops · R refresh · Q quit", id="notice")
            yield Footer()

    def on_mount(self) -> None:
        apply_theme(self, self._palette)
        self.query_one("#logout", Button).tooltip = "Logout"
        self.query_one("#vm-list", Vertical).border_title = "VM list"
        self.query_one("#desktop-list", Vertical).border_title = "Desktop list"
        table = self.query_one("#fleet-table", DataTable)
        self._table_columns = table.add_columns("#", "VM name", "Object state", "Process", "vCPU", "Memory")
        self._desktop_columns = self.query_one("#desktop-table", DataTable).add_columns(
            "Desktop", "UUID", "Cluster status", "OS", "vCPU"
        )
        self.query_one("#tabs", TabbedContent).display = False
        self.query_one("#login-box", VerticalScroll).display = True
        self._refresh_timer = self.set_interval(0.5, self._tick)
        self._set_width_class()
        self._resume_session()

    def on_resize(self, event: events.Resize) -> None:
        self._set_width_class(event.size.width)

    def _set_width_class(self, width: int | None = None) -> None:
        available = width if width is not None else self.size.width
        self.query_one("#shell", Vertical).set_class(available >= 110, "wide")
        scroll = self.query_one("#overview-scroll", VerticalScroll)
        scroll.set_class(available >= 130, "cols-3")
        scroll.set_class(90 <= available < 130, "cols-2")
        scroll.set_class(available < 90, "cols-1")

    def action_overview_page(self) -> None:
        if self.session is not None:
            self.query_one("#tabs", TabbedContent).active = "overview"

    def action_vms_page(self) -> None:
        if self.session is not None:
            self.query_one("#tabs", TabbedContent).active = "fleet"

    def action_desktops_page(self) -> None:
        if self.session is not None:
            self.query_one("#tabs", TabbedContent).active = "desktops"

    @work(thread=True, group="session", exclusive=True)
    def _resume_session(self) -> None:
        try:
            session, _ = self.sessions.resume_or_login()
        except AppError as exc:
            self.call_from_thread(self._login_required, str(exc))
            return
        self.call_from_thread(self._session_ready, session)

    @work(thread=True, group="session", exclusive=True)
    def _perform_login(self, username: str, password: str) -> None:
        try:
            session, _ = self.sessions.resume_or_login(username=username, password=password)
        except AppError as exc:
            self.call_from_thread(self._login_required, str(exc))
            return
        self.call_from_thread(self._session_ready, session)

    @on(Button.Pressed, "#login")
    def submit_login(self) -> None:
        username = self.query_one("#username", Input).value
        password_widget = self.query_one("#password", Input)
        password = password_widget.value
        password_widget.value = ""
        self.query_one("#login", Button).disabled = True
        self._perform_login(username, password)

    @on(Button.Pressed, "#logout")
    def submit_logout(self) -> None:
        if self.session is not None and not self._operation_active:
            self._perform_logout(self.session)

    @work(thread=True, group="session", exclusive=True)
    def _perform_logout(self, session: PvmSession) -> None:
        message = "Local session cleared."
        try:
            self.sessions.logout(session)
        except AppError as exc:
            message = f"Local token cache cleared; PVM logout was not confirmed: {exc.code}"
        self.call_from_thread(self._session_ended, message)

    def _clear_session_view(self) -> None:
        self.application.collection.clear_desktop_session()
        self._desktop_section = None
        self._desktop_generation = None
        self._desktop_min_generation = self.application.collection.snapshot.generation
        self._desktops.clear()
        self._desktop_selected = None
        self._desktop_rows = ()
        self._desktop_cells.clear()
        self.query_one("#desktop-table", DataTable).clear(columns=False)
        self.query_one("#desktop-search", Input).value = ""
        self.query_one("#desktop-all", Checkbox).value = False
        self.query_one("#desktop-quality", Static).update("Not collected")
        self.query_one("#desktop-count", Static).update("—")
        self.query_one("#desktop-selected-label", Static).update("—")
        self.query_one("#desktop-detail", Static).update("Select a Desktop to inspect its details.")
        self.query_one("#desktop-action-status", Static).update("No operation submitted.")
        self.query_one("#desktop-audit-panel", Static).update("Read-only audit\nWaiting for session…")
        self.query_one("#desktop-audit-panel", Static).display = False
        self._inventory_section = None
        self._inventory = None
        self._inventory_generation = None
        self._records.clear()
        self.query_one("#vm-search", Input).value = ""
        self.query_one("#select-all", Checkbox).value = False
        self._selected_uuid = None
        self._table_order = ()
        self._table_content.clear()
        self.query_one("#fleet-table", DataTable).clear(columns=False)
        self.query_one("#vm-count", Static).update("—")
        self.query_one("#process-count", Static).update("—")
        self.query_one("#inventory-quality", Static).update("Not collected")
        self.query_one("#detail-box", Static).update("Select a VM to inspect its details.")
        self.query_one("#action-status", Static).update("No operation submitted.")
        self.query_one("#audit-panel", Static).update("Read-only audit\nWaiting for session…")
        self.query_one("#audit-panel", Static).display = False
        self.query_one("#host-status", Static).update("Host status\nWaiting for collection…")
        for panel in _METRIC_PANELS:
            self.query_one(f"#{panel}", Static).update("Waiting for collection…")
        self._visible_snapshot = None
        self._history = OverviewHistory()
        self._render_cache.clear()
        self.query_one("#nic-tabs", Horizontal).remove_children()
        self._nic_tab_names = ()
        self._nic_selected = None
        for widget_id in (
            "running-card", "cpu-card", "memory-card", "load-card",
            "cpu-chart", "load-chart", "nic-detail", "host-identity",
        ):
            self.query_one(f"#{widget_id}", Static).update("Waiting for authenticated monitoring data…")

    def _session_ended(self, message: str) -> None:
        self.session = None
        self._session_epoch += 1
        self._overview_schedule.reset()
        self._pending_manual_refresh = False
        self._clear_session_view()
        self.query_one("#session-label", Static).update("● Offline")
        self.query_one("#tabs", TabbedContent).display = False
        self.query_one("#login-box", VerticalScroll).display = True
        self.query_one("#login-error", Static).update(message)

    def _login_required(self, message: str) -> None:
        self.query_one("#login", Button).disabled = False
        self.query_one("#login-error", Static).update(message)

    def _session_ready(self, session: PvmSession) -> None:
        self.session = session
        self._session_epoch += 1
        self._pending_manual_refresh = False
        self._clear_session_view()
        self.query_one("#tabs", TabbedContent).active = "overview"
        self._overview_schedule.reset()
        self._overview_schedule.enter()
        self.query_one("#session-label", Static).update(
            redact_text(f"● {session.username}  /  session active")
        )
        self.query_one("#login-box", VerticalScroll).display = False
        self.query_one("#tabs", TabbedContent).display = True
        self._tick()

    @on(TabbedContent.TabActivated, "#tabs")
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if self.session is None:
            return
        if event.pane.id == "overview":
            self._overview_schedule.enter()
            self._tick()
        else:
            self._overview_schedule.leave()
            self._fleet_due = 0
            self._tick()

    def action_refresh(self) -> None:
        self._request_refresh()

    @on(Button.Pressed, "#desktop-refresh")
    @on(Button.Pressed, "#refresh-button")
    @on(Button.Pressed, "#overview-refresh")
    def refresh_button(self) -> None:
        self._request_refresh()

    @on(Button.Pressed, "#audit-toggle")
    def show_audit(self) -> None:
        panel = self.query_one("#audit-panel", Static)
        panel.display = not panel.display
        if panel.display:
            self._request_audit("audit-panel")

    @on(Button.Pressed, "#desktop-audit-toggle")
    def show_desktop_audit(self) -> None:
        panel = self.query_one("#desktop-audit-panel", Static)
        panel.display = not panel.display
        if panel.display:
            self._request_audit("desktop-audit-panel")

    @on(Button.Pressed, "#rediscover")
    def rediscover(self) -> None:
        self._overview_schedule.rediscover()
        self._tick()

    @on(Button.Pressed, "#interval-apply")
    def apply_interval(self) -> None:
        raw = self.query_one("#interval-input", Input).value.strip()
        try:
            if not raw.isdecimal():
                raise ValueError("Refresh must be a whole number of seconds from 1 to 60")
            self._overview_schedule.set_interval(int(raw))
        except ValueError as exc:
            self.query_one("#interval-error", Static).update(str(exc))
            return
        self.query_one("#interval-error", Static).update("")
        self.query_one("#refresh-label", Static).update(
            f"Refresh: {self._overview_schedule.interval:g}s"
        )

    def _tick(self) -> None:
        self._set_width_class()
        if self.session is None:
            return
        if self._refresh_busy:
            return
        if self.query_one("#tabs", TabbedContent).active == "overview":
            sections = self._overview_schedule.due()
            if sections:
                self._start_refresh(sections)
        else:
            import time

            now = time.monotonic()
            if now >= self._fleet_due:
                section = "desktops" if self.query_one("#tabs", TabbedContent).active == "desktops" else "inventory"
                interval = max(DESKTOP_MIN_REFRESH_SECONDS, self.application.settings.refresh_interval) if section == "desktops" else self.application.settings.refresh_interval
                self._fleet_due = now + interval
                self._start_refresh((section,))

    def _request_refresh(self) -> None:
        if self.session is None:
            return
        if self._refresh_busy:
            self._pending_manual_refresh = True
            return
        if self.query_one("#tabs", TabbedContent).active == "overview":
            sections = ("physical_nics", "local_host", "nic_samples", "inventory", "dashboard", "host_status", "host_metrics")
            self._overview_schedule.busy = True
        else:
            sections = ("desktops",) if self.query_one("#tabs", TabbedContent).active == "desktops" else ("inventory",)
        self._start_refresh(sections)

    def _start_refresh(self, sections: tuple[str, ...]) -> None:
        session = self.session
        if session is None or self._refresh_busy:
            self._overview_schedule.finished()
            return
        self._refresh_busy = True
        self._collect_visible(sections, session.token, self._session_epoch)

    @work(thread=True, group="refresh", exclusive=False)
    def _collect_visible(self, sections: tuple[str, ...], token: str, epoch: int) -> None:
        try:
            snapshot = self.application.refresh(token, sections=sections)
        except Exception as exc:
            self.call_from_thread(self._show_refresh_error, epoch, type(exc).__name__)
        else:
            self.call_from_thread(self._publish_if_current, snapshot, epoch)
        finally:
            self.call_from_thread(self._refresh_finished)

    def _refresh_finished(self) -> None:
        self._refresh_busy = False
        self._overview_schedule.finished()
        if self._pending_manual_refresh and self.session is not None:
            self._pending_manual_refresh = False
            self._request_refresh()

    def _show_refresh_error(self, epoch: int, kind: str) -> None:
        if self.session is not None and epoch == self._session_epoch:
            self._show_error(f"Refresh failed: {kind}")

    def _publish_if_current(self, snapshot: ApplicationSnapshot, epoch: int) -> None:
        if self.session is not None and epoch == self._session_epoch:
            self._publish_snapshot(snapshot)

    def _put(self, widget_id: str, text: str) -> None:
        if self._render_cache.get(widget_id) != text:
            self.query_one(f"#{widget_id}", Static).update(styled_metric(text, palette=self._palette))
            self._render_cache[widget_id] = text

    def _render_overview(self, snapshot: ApplicationSnapshot) -> None:
        self._visible_snapshot = snapshot
        self._history.add(snapshot)
        chart_widths = {cid: self.query_one(f"#{cid}", Static).content_size.width or 32 for cid in ("cpu-chart", "load-chart")}
        values = cards(snapshot, self._history, self._overview_schedule.interval, chart_widths)
        for widget_id, text in values.items():
            self._put(widget_id, text)
        devices, detail = nic_details(snapshot, self._nic_selected)
        names = tuple(item.name for item in devices)
        if names != self._nic_tab_names:
            tabs = self.query_one("#nic-tabs", Horizontal)
            tabs.remove_children()
            for index, item in enumerate(devices):
                tabs.mount(Button(redact_text(item.name), id=f"nic-tab-{index}", classes="nic-tab"))
            self._nic_tab_names = names
        if self._nic_selected not in names:
            self._nic_selected = names[0] if names else None
        self._put("nic-detail", detail)
        for index, name in enumerate(names):
            button = self.query_one(f"#nic-tab-{index}", Button)
            button.variant = "primary" if name == self._nic_selected else "default"

    @on(Button.Pressed, ".nic-tab")
    def select_nic(self, event: Button.Pressed) -> None:
        index = int((event.button.id or "-0").rsplit("-", 1)[1])
        if index < len(self._nic_tab_names):
            self._nic_selected = self._nic_tab_names[index]
            _, detail = nic_details(self._visible_snapshot, self._nic_selected) if self._visible_snapshot else ((), "No sample")
            self._put("nic-detail", detail)
            for button_index, name in enumerate(self._nic_tab_names):
                button = self.query_one(f"#nic-tab-{button_index}", Button)
                button.variant = "primary" if name == self._nic_selected else "default"

    def _publish_snapshot(self, snapshot: ApplicationSnapshot) -> None:
        self._render_desktops(snapshot.section("desktops"))
        self._render_overview(snapshot)
        inventory_section = snapshot.section("inventory")
        if inventory_section is None or inventory_section.generation == self._inventory_generation:
            self._render_host(snapshot)
            return
        self._inventory_generation = inventory_section.generation
        self._inventory_section = inventory_section
        inventory = None
        if inventory_section is not None:
            value = inventory_section.value or inventory_section.last_good_value
            if isinstance(value, InventoryData):
                inventory = value
        self._inventory = inventory
        self._records = {record.uuid: record for record in inventory.records} if inventory else {}
        self._filter_vms()
        if inventory is not None:
            self.query_one("#vm-count", Static).update(str(len(inventory.records)))
            self.query_one("#process-count", Static).update(
                str(sum(record.process_seen for record in inventory.records))
            )
        else:
            self.query_one("#vm-count", Static).update("—")
            self.query_one("#process-count", Static).update("—")
        if inventory_section is None:
            quality = "Unavailable"
        else:
            quality = inventory_section.status.value.replace("_", " ").title()
            if inventory_section.quality_issues:
                quality += f" · {len(inventory_section.quality_issues)} issue(s)"
        self.query_one("#inventory-quality", Static).update(quality)
        status = _section_status(inventory_section)
        self.query_one("#inventory-quality", Static).styles.color = (
            self._palette.success if inventory_section and inventory_section.status is CollectionStatus.CURRENT else self._palette.warning
        )
        self.query_one("#notice", Static).update(
            f"Inventory {status} · generation {inventory_section.generation if inventory_section else '—'} · "
            "object states and process observations are shown separately"
        )
        self._render_host(snapshot)

    def _render_desktops(self, section: SectionSnapshot[object] | None) -> None:
        if section is None or section.generation <= self._desktop_min_generation or section.generation == self._desktop_generation:
            return
        self._desktop_generation = section.generation
        self._desktop_section = section
        value = section.value if section.value is not None else section.last_good_value
        self._desktops = {item.uuid: item for item in value if isinstance(item, VirtualDesktop)} if isinstance(value, tuple) else {}
        quality = section.status.value.replace("_", " ").title()
        if section.error:
            quality += f" · {redact_text(section.error)}"
        if section.quality_issues:
            quality += f" · {len(section.quality_issues)} issue(s)"
        self.query_one("#desktop-quality", Static).update(quality)
        self.query_one("#desktop-quality", Static).styles.color = (
            self._palette.success if section.status is CollectionStatus.CURRENT else self._palette.warning
        )
        self.query_one("#desktop-count", Static).update(str(len(self._desktops)) if section.has_value else "—")
        self._filter_desktops()

    @on(Input.Changed, "#desktop-search")
    def desktop_search_changed(self) -> None:
        self._filter_desktops()

    @on(Checkbox.Changed, "#desktop-all")
    def desktop_scope_changed(self) -> None:
        self._render_desktop_detail()

    def _filter_desktops(self) -> None:
        if not self.is_mounted(self.query_one("#desktop-table", DataTable)):
            return
        query = self.query_one("#desktop-search", Input).value.strip().casefold()
        records = sorted(
            (item for item in self._desktops.values() if query in item.name.casefold()),
            key=lambda item: (item.name.casefold(), item.uuid),
        )
        rows = {
            item.uuid: (redact_text(item.name), item.uuid[:8] + "…",
                        redact_text(item.cluster_status or "N/A"),
                        redact_text(item.os_type or "N/A"), str(item.vcpu) if item.vcpu is not None else "N/A")
            for item in records
        }
        order = tuple(rows)
        table = self.query_one("#desktop-table", DataTable)
        if order != self._desktop_rows:
            table.clear(columns=False)
            for uuid, cells in rows.items():
                table.add_row(*(self._cell_text(index, cell) for index, cell in enumerate(cells)), key=uuid)
        else:
            for uuid, cells in rows.items():
                old = self._desktop_cells.get(uuid, ())
                for column, cell in enumerate(cells):
                    if column >= len(old) or cell != old[column]:
                        table.update_cell(uuid, self._desktop_columns[column], self._cell_text(column, cell), update_width=True)
        self._desktop_rows, self._desktop_cells = order, rows
        if self._desktop_selected not in rows:
            self._desktop_selected = order[0] if order else None
        if self._desktop_selected:
            table.move_cursor(row=order.index(self._desktop_selected), animate=False)
        self._render_desktop_detail()

    @on(DataTable.RowHighlighted, "#desktop-table")
    def desktop_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if not self._running or not self.is_mounted(event.data_table):
            return
        uuid = str(getattr(event.row_key, "value", event.row_key))
        if uuid in self._desktop_rows:
            self._desktop_selected = uuid
            self._render_desktop_detail()

    def _render_desktop_detail(self) -> None:
        if not self.is_mounted(self.query_one("#desktop-detail", Static)):
            return
        all_targets = self.query_one("#desktop-all", Checkbox).value
        uuids = tuple(sorted(self._desktops)) if all_targets else ((self._desktop_selected,) if self._desktop_selected else ())
        scope = f"{'All unfiltered Desktops' if all_targets else 'Selected Desktop'} · {len(uuids)} target(s)"
        self.query_one("#desktop-selected-label", Static).update((self._desktop_selected or "—")[:8])
        self.query_one("#desktop-scope", Static).update(scope)
        record = self._desktops.get(self._desktop_selected or "")
        if record is None or self._desktop_selected not in self._desktop_rows:
            detail = "No matching Virtual Desktops." if self._desktop_section else "Waiting for Desktop discovery…"
        else:
            detail = (f"{record.name} · {record.uuid}\n"
                      f"Object enabled: {record.enabled or 'N/A'} · Local runtime: {record.local_status or 'N/A'}\n"
                      f"Cluster runtime: {record.cluster_status or 'N/A'} · OS: {record.os_type or 'N/A'} {record.os_version or ''}\n"
                      f"vCPU: {record.vcpu if record.vcpu is not None else 'N/A'} · RAM: N/A (raw size: {record.memory_size_raw or 'N/A'}, unit unverified)\n"
                      f"Owner: N/A · Zone: N/A · Parent ID: {record.parent_id or 'N/A'}")
        if all_targets:
            detail += "\nAll unfiltered target UUIDs: " + (", ".join(uuids) if uuids else "none")
        self.query_one("#desktop-detail", Static).update(redact_text(detail))

    @on(Select.Changed, "#desktop-actions")
    def desktop_action_requested(self, event: Select.Changed) -> None:
        if not isinstance(event.value, str):
            return
        action = Action(event.value)
        event.select.clear()
        if self._operation_active or self.session is None:
            self._desktop_message("Sign in and wait for the current operation to finish.")
            return
        section = self._desktop_section
        all_targets = self.query_one("#desktop-all", Checkbox).value
        if all_targets:
            targets = tuple(self._desktops[uuid] for uuid in sorted(self._desktops))
        elif self._desktop_selected in self._desktop_rows:
            selected = self._desktops.get(self._desktop_selected or "")
            targets = (selected,) if selected else ()
        else:
            targets = ()
        if section is None:
            self._desktop_message("Refresh the Desktop inventory before choosing an action.")
            return
        try:
            plan = self.operations.create_desktop_plan(action, targets, section, is_bulk=all_targets)
        except AppError as exc:
            self._desktop_message(str(exc))
            return
        # Selecting the action is the operator's intent; no extra confirmation.
        self._operation_active = True
        self.query_one("#logout", Button).disabled = True
        self.query_one("#desktop-actions", Select).disabled = True
        self._desktop_message(f"{action.value.upper()} submitted for {len(targets)} Desktop(s)…")
        self._execute_desktop(action, targets, section, plan, self._session_epoch)

    def _desktop_message(self, message: str) -> None:
        self.query_one("#desktop-action-status", Static).update(redact_text(message))

    @work(thread=True, group="desktop-operation", exclusive=False)
    def _execute_desktop(
        self, action: Action, targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object], plan: OperationPlan, epoch: int,
    ) -> None:
        try:
            session = self.session
            if session is None or epoch != self._session_epoch:
                return
            try:
                result = self.operations.execute_desktop(
                    session.token, action, targets, section,
                    is_bulk=plan.is_bulk, plan=plan,
                )
            except AppError as exc:
                self.call_from_thread(self._desktop_error_if_current, epoch, str(exc))
            else:
                self.call_from_thread(self._desktop_result_if_current, epoch, result)
        finally:
            try:
                self.call_from_thread(self._desktop_operation_finished)
            except RuntimeError:
                pass

    def _desktop_error_if_current(self, epoch: int, message: str) -> None:
        if self.session is not None and epoch == self._session_epoch:
            self._desktop_message(message)

    def _desktop_result_if_current(self, epoch: int, result: OperationResult) -> None:
        if self.session is not None and epoch == self._session_epoch:
            summary = "; ".join(f"{item.uuid}: {item.state.value}" for item in result.targets)
            self._desktop_message(f"{result.action.value.upper()} · {result.state.value} · {result.message} · {summary}")
            self._publish_snapshot(self.application.collection.snapshot)

    def _desktop_operation_finished(self) -> None:
        self._operation_active = False
        self.query_one("#logout", Button).disabled = False
        self.query_one("#desktop-actions", Select).disabled = False

    def _render_host(self, snapshot: ApplicationSnapshot) -> None:
        status_section = snapshot.section("host_status")
        metric_section = snapshot.section("host_metrics")
        status = as_host_status(status_section) if status_section else None
        metrics = as_host_metrics(metric_section) if metric_section else None
        self.query_one("#host-status", Static).update(_host_status_text(status, status_section))
        self._render_metric_panels(metrics, metric_section)

    def _render_metric_panels(self, metrics: HostMetrics | None, section: SectionSnapshot[object] | None) -> None:
        status = _section_status(section)
        texts = {
            "metrics-network": hm.finish(hm.network_body(metrics), status),
            "metrics-storage": hm.finish(hm.storage_body(metrics), status),
            "metrics-temperature": hm.finish(hm.temperature_body(metrics), status),
            "metrics-sessions": hm.finish(hm.sessions_body(metrics), status),
            "metrics-processes": hm.finish(hm.processes_body(metrics), status),
            "metrics-commands": redact_text("\n".join(hm.commands_body(metrics))),
        }
        for panel, text in texts.items():
            self.query_one(f"#{panel}", Static).update(text)
        total = metrics.process_total if metrics is not None else None
        self.query_one("#processes-card").border_title = (
            "Top processes by CPU" if total is None else f"Top processes by CPU · {total:,} total"
        )

    @on(Checkbox.Changed, "#select-all")
    def vm_scope_changed(self) -> None:
        self._filter_vms()

    @on(Input.Changed, "#vm-search")
    def vm_search_changed(self) -> None:
        # Search is strictly local: changing the input never starts collection.
        self._filter_vms()

    def _cell_text(self, column: int, cell: str) -> Text:
        # Column 2 is the object state (VM page) or cluster status (Virtual Desktops page).
        return state_text(cell, self._palette) if column == 2 else Text(cell)

    def _filter_vms(self) -> None:
        query = self.query_one("#vm-search", Input).value.strip().casefold()
        records = sorted(
            (record for record in self._records.values() if query in record.name.casefold()),
            key=lambda item: (0 if item.process_seen else 1, item.name.casefold(), item.uuid),
        )
        rows = {
            record.uuid: (
                str(index), redact_text(record.name),
                redact_text(record.state), "Observed" if record.process_seen else "Not observed",
                _display(record.vcpu), _display(record.mem_mb, suffix=" MB"),
            )
            for index, record in enumerate(records, start=1)
        }
        order = tuple(rows)
        table = self.query_one("#fleet-table", DataTable)
        if order != self._table_order:
            table.clear(columns=False)
            for uuid, cells in rows.items():
                table.add_row(*(self._cell_text(index, cell) for index, cell in enumerate(cells)), key=uuid)
        else:
            for uuid, cells in rows.items():
                old = self._table_content.get(uuid, ())
                for column, cell in enumerate(cells):
                    if column >= len(old) or cell != old[column]:
                        table.update_cell(uuid, self._table_columns[column], self._cell_text(column, cell), update_width=True)
        self._table_order, self._table_content = order, rows
        all_targets = self.query_one("#select-all", Checkbox).value
        count = len(self._records) if all_targets else int(bool(order))
        self.query_one("#vm-scope", Static).update(
            f"{'All unfiltered VMs' if all_targets else 'Selected VM'} · {count} target(s)"
            f" · {len(order)} shown"
        )
        if self._selected_uuid not in rows:
            self._selected_uuid = order[0] if order else None
        if self._selected_uuid:
            table.move_cursor(row=order.index(self._selected_uuid), animate=False)
            self._render_record(self._records[self._selected_uuid])
        else:
            self._detail_base = (
                "No matching VMs. Clear search to view the inventory."
                if query and self._inventory is not None else
                "No VM records are currently available."
            )
            self.query_one("#detail-box", Static).update(self._detail_base)

    @on(DataTable.RowHighlighted, "#fleet-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # A queued highlight may arrive while the screen is being torn down.
        if not self._running or not self.is_mounted(event.data_table):
            return
        key = getattr(event.row_key, "value", str(event.row_key))
        if str(key) not in self._table_order:
            return  # Ignore queued highlights for rows hidden by search.
        self._selected_uuid = str(key)
        record = self._records.get(self._selected_uuid)
        if record is not None:
            self._render_record(record)

    def _render_record(self, record: VMRecord) -> None:
        state_conflict = " · STATE EVIDENCE CONFLICT" if record.state_disagreed else ""
        detail = (
            f"{record.name}\nUUID  {record.uuid}\nObject state  {record.state}{state_conflict}\n"
            f"Process observed  {'Yes' if record.process_seen else 'No'}\n"
            f"PID  {_display(record.process.pid if record.process else None)}\n"
            f"vCPU  {_display(record.vcpu)}  ·  Memory  {_display(record.mem_mb, suffix=' MB')}\n"
            f"Description  {record.object.description or '—'}"
        )
        self._detail_base = detail
        self.query_one("#detail-box", Static).update(redact_text(detail))

    @work(thread=True, group="detail", exclusive=True)
    def _load_detail(self, uuid: str) -> None:
        session = self.session
        if session is None:
            return
        try:
            section = self.application.detail(session.token, uuid)
            value = as_vm_detail(section)
        except Exception:
            return
        self.call_from_thread(self._publish_detail, uuid, value)

    def _publish_detail(self, uuid: str, detail: VMDetail) -> None:
        if uuid != self._selected_uuid:
            return
        extra = (
            f"\nHost  {detail.host or '—'}  ·  machine  {detail.machine or '—'}"
            f"\nCPU model  {detail.cpu_model or '—'}  ·  topology  {detail.vcpu_topology or '—'}"
            f"\nDisks  {len(detail.disks)}  ·  NICs  {len(detail.nics)}  ·  console  "
            f"{detail.console.kind if detail.console else '—'}"
        )
        self.query_one("#detail-box", Static).update(redact_text(self._detail_base + extra))

    def action_details(self) -> None:
        if self._selected_uuid in self._table_order:
            self._load_detail(self._selected_uuid)

    @on(Select.Changed, "#bulk-actions")
    def bulk_action_selected(self, event: Select.Changed) -> None:
        if not isinstance(event.value, str):
            return  # blank / no-selection sentinel
        action = Action(event.value)
        # Reset the dropdown so the same action can be chosen again later.
        event.select.clear()
        self._begin_action(action)

    def _begin_action(self, action: Action) -> None:
        if self._operation_active:
            self._show_error("An operation is already in progress.")
            return
        section = self._inventory_section
        inventory = self._inventory
        if section is None or inventory is None:
            self._show_error("No inventory available. Refresh before operating a VM.")
            return
        if self.query_one("#select-all", Checkbox).value:
            selectors = ("all",)
        elif self._selected_uuid in self._table_order:
            selectors = (self._selected_uuid,)
        else:
            self._show_error("Select a VM row first.")
            return
        try:
            selection = self.application.resolve_targets(inventory, selectors)
        except AppError as exc:
            self._show_error(str(exc))
            return
        try:
            plan = self.operations.create_plan(
                action, selection.records, section, is_bulk=selection.is_bulk
            )
        except AppError as exc:
            self._show_error(str(exc))
            return
        self._launch_operation(action, selection, section, plan)

    def _launch_operation(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        plan: OperationPlan,
    ) -> None:
        if self._operation_active:
            self._show_error("An operation is already in progress.")
            return
        self._operation_active = True
        self.query_one("#bulk-actions", Select).disabled = True
        self.query_one("#logout", Button).disabled = True
        self._execute_action(action, selection, section, plan)

    @work(thread=True, group="operation", exclusive=False)
    def _execute_action(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        plan: OperationPlan,
    ) -> None:
        try:
            session = self.session
            if session is None:
                self.call_from_thread(self._show_error, "Sign in before submitting an operation.")
                return
            try:
                result = self.operations.execute(
                    session.token,
                    action,
                    selection.records,
                    section,
                    is_bulk=selection.is_bulk,
                    plan=plan,
                )
            except AppError as exc:
                self.call_from_thread(self._show_error, str(exc))
                self.call_from_thread(self._request_refresh)
                return
            self.call_from_thread(self._show_operation, result)
            self.call_from_thread(self._request_refresh)
        finally:
            try:
                self.call_from_thread(self._operation_finished)
            except RuntimeError:
                # Textual may already be shutting down; Runtime.close still
                # waits for the application-owned operation lane to finish.
                pass

    def _operation_finished(self) -> None:
        self._operation_active = False
        self.query_one("#bulk-actions", Select).disabled = False
        self.query_one("#logout", Button).disabled = False

    def _show_operation(self, result: OperationResult) -> None:
        self.query_one("#action-status", Static).update(
            redact_text(f"{result.action.value.upper()} · {result.state.value} · {result.message}")
        )

    def _show_error(self, message: str) -> None:
        self.query_one("#action-status", Static).update(redact_text(message))

    @work(thread=True, group="audit", exclusive=True)
    def _request_audit(self, panel_id: str = "audit-panel") -> None:
        if self.session is None:
            return
        try:
            entries = self.application.recent_audit(20)
        except Exception as exc:
            text = f"Audit unavailable: {type(exc).__name__}. The database is read-only."
        else:
            if not entries:
                text = "No audit rows available. The local database is queried read-only."
            else:
                lines = ["READ-ONLY AUDIT  ·  newest first"]
                lines.extend(
                    f"{entry.time}  {entry.user}  {entry.command}  {entry.result}"
                    for entry in entries
                )
                text = "\n".join(lines)
        self.call_from_thread(self._publish_audit, panel_id, text)

    def _publish_audit(self, panel_id: str, text: str) -> None:
        self.query_one(f"#{panel_id}", Static).update(redact_text(text))


def _display(value: int | float | str | None, *, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def _section_status(section: SectionSnapshot[object] | None) -> str:
    if section is None:
        return "unavailable"
    return section.status.value.replace("_", " ")


def _host_status_text(status: HostStatus | None, section: SectionSnapshot[object] | None) -> str:
    lines = ["HOST STATUS", f"Collection  {_section_status(section)}"]
    if status is None:
        lines.append("No current host-status values.")
        return redact_text("\n".join(lines))
    lines.extend(
        [
            f"Node  {status.name or '—'}  ·  IP  {status.ip or '—'}",
            f"Sball  {status.sball_state or '—'}  ·  node  {status.node_state or '—'}",
            f"Version  {status.version or '—'}",
            f"CPU  {_display(status.cpu_pct, suffix='%')}  ·  cores  {_display(status.cpu_count)}",
            f"RAM  {_bytes(status.ram_used_bytes)} / {_bytes(status.ram_total_bytes)}",
            f"Load  {_display(status.load1)}  {_display(status.load5)}  {_display(status.load15)}",
            f"Storage  {_bytes(status.storage_available_bytes)} free / {_bytes(status.storage_total_bytes)}",
        ]
    )
    return redact_text("\n".join(lines))


def _bytes(value: int | None) -> str:
    if value is None:
        return "—"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"

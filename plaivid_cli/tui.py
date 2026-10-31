"""Textual presentation for the local PVM management application."""

from __future__ import annotations

import os

from rich.text import Text
from textual import on, work
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
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    ApplicationSnapshot,
    CollectionStatus,
    HostMetrics,
    HostStatus,
    InventoryData,
    OperationApproval,
    OperationPlan,
    OperationResult,
    PvmSession,
    SectionSnapshot,
    VMDetail,
    VMRecord,
)
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.overview import cards, nic_details
from plaivid_cli.presentation.theme import (
    apply_theme,
    brand,
    palette_for,
    styled_metric,
)

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


class PlaividTui(App[None]):
    """Operator dashboard; all I/O is delegated to application coordinators."""

    TITLE = "Plaivid PVM Console"
    SUB_TITLE = "Local management · Linux"
    # Semantic tokens mirror the Plaivid Textual theme, including native controls.
    CSS = """
        Screen { background: $p-bg; color: $p-text; }
        #shell { height: 1fr; padding: 0 1; background: $p-bg; }
        #topbar { height: 3; padding: 0 1; margin: 0 0 1 0;
                  background: $p-panel; border: round $p-border; }
        #brand { width: 1fr; content-align: left middle; }
        #session-label { width: auto; color: $p-green; content-align: right middle; padding: 0 1; }
        #logout { width: 5; min-width: 5; height: 1; margin: 0; padding: 0;
                  background: $p-surface; color: $p-rose; border: none; }
        #logout:focus { background: $p-surface; color: $p-rose; text-style: bold underline; }

        #login-box { width: 64; max-width: 92%; height: auto; border: round $p-border;
                     background: $p-panel; padding: 1 2; margin: 2 0; }
        #login-title { color: $p-blue; text-style: bold; padding-bottom: 1; }
        #login-warning { color: $p-yellow; padding: 1 0; }
        #login-error { color: $p-rose; padding: 1 0; }
        #login-buttons { height: 1; align-horizontal: right; margin-top: 1; }
        Input { background: $p-surface; border: round $p-border; color: $p-text; }
        Input:focus { border: round $p-cyan; }

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
        #overview-toolbar { height: 3; background: $p-panel; border: round $p-border;
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
        #host-identity { height: auto; color: $p-muted; background: $p-panel;
                         border-left: solid $p-cyan; padding: 1; margin-top: 1; }
        .dashboard-heading { height: 2; color: $p-blue; text-style: bold;
                             padding: 0 1; margin-top: 1; }
        #summary-grid { grid-size: 2; grid-gutter: 1; height: auto; }
        #chart-grid { grid-size: 1; grid-gutter: 1; height: auto; }
        .wide #summary-grid { grid-size: 4; }
        .wide #chart-grid { grid-size: 3; }
        .dashboard-card { height: 6; padding: 0 1; border: round $p-border;
                          background: $p-surface; color: $p-text; }
        #heartbeat-card { height: 5; border: round $p-border;
                          background: $p-panel; margin-top: 1; }
        #heartbeat-details { height: auto; padding: 0 1; color: $p-muted;
                             background: $p-panel; border-left: solid $p-border; }
        .chart-card { height: 4; padding: 0 1; border: round $p-border;
                      background: $p-panel; }
        #cpu-chart { border-top: solid $p-cyan; }
        #memory-chart { border-top: solid $p-purple; }
        #load-chart { border-top: solid $p-blue; }
        #nic-tabs { height: auto; }
        .nic-tab { width: auto; min-width: 10; margin-right: 1; }
        #nic-detail, #vm-monitor, #vdi-monitor { height: auto; min-height: 5;
                                                 padding: 1; border: round $p-border;
                                                 background: $p-panel; }
        #rediscover { margin: 1 0; }
        #host-grid { height: auto; }
        #host-status, #host-metrics { width: 1fr; height: auto; min-height: 6;
                                      border: round $p-border; background: $p-panel;
                                      padding: 1; }
        #host-status { margin-right: 1; }

        #fleet-summary { height: 5; margin-top: 1; align-vertical: middle; }
        .metric-card { width: 1fr; height: 5; margin-right: 1; padding: 0 1;
                       border: round $p-border; background: $p-surface; }
        .metric-card:focus-within { border: round $p-green; }
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
        DataTable > .datatable--header { background: $p-panel; color: $p-purple; }
        DataTable:focus > .datatable--cursor { background: $p-purple; color: $p-bg; }
        #detail-box { height: 10; margin-top: 1; border: round $p-border;
                      background: $p-panel; padding: 1; }
        #action-status { height: 1; color: $p-yellow; }
        #audit-panel { display: none; height: auto; min-height: 7;
                       border: round $p-border; background: $p-panel; padding: 1; }
        """
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("enter", "details", "Details"),
        ("q", "quit", "Quit"),
        ("1", "overview_page", "Overview"),
        ("2", "vms_page", "Virtual Machines"),
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
        self._heartbeat_color: str | None = None
        self._overview_schedule = OverviewSchedule(
            min(60, max(1, application.settings.refresh_interval))
        )
        self._history = OverviewHistory()
        self._nic_selected: str | None = None
        self._nic_tab_names: tuple[str, ...] = ()
        self._fleet_due = 0.0
        self._visible_snapshot: ApplicationSnapshot | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            with Horizontal(id="topbar"):
                yield Static(brand(self._palette), id="brand", markup=False)
                yield Static("● Offline", id="session-label", markup=False)
                yield Button("⏻", id="logout", variant="default")
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
                            yield Static("⊷  LIVE  /  HOST TELEMETRY", id="overview-title")
                            yield Static(f"Refresh: {self._overview_schedule.interval:g}s", id="refresh-label")
                            yield Input(value=f"{self._overview_schedule.interval:g}", id="interval-input", placeholder="sec")
                            yield Button("Apply", id="interval-apply")
                            yield Button("Refresh", id="overview-refresh")
                        yield Static("", id="interval-error", markup=False)
                        yield Static("LOCAL HOST  N/A · PVM HOST  N/A", id="host-identity", markup=False)
                        yield Static("01  /  HOST OVERVIEW", classes="dashboard-heading")
                        with Grid(id="summary-grid"):
                            for card in ("running-card", "cpu-card", "memory-card", "load-card"):
                                yield Static("Loading monitoring data…", id=card, classes="dashboard-card", markup=False)
                        yield Static("♥  HOST HEARTBEAT\nLOADING", id="heartbeat-card", classes="dashboard-card", markup=False)
                        yield Static("Awaiting collector responses", id="heartbeat-details", markup=False)
                        yield Static("02  /  RESOURCE HISTORY", classes="dashboard-heading")
                        with Grid(id="chart-grid"):
                            for chart in ("cpu-chart", "memory-chart", "load-chart"):
                                yield Static("Waiting for samples", id=chart, classes="chart-card", markup=False)
                        yield Static("03  /  PHYSICAL NETWORK INTERFACES", classes="dashboard-heading")
                        with Horizontal(id="nic-tabs"):
                            pass
                        yield Static("Discovering physical interfaces…", id="nic-detail", markup=False)
                        yield Button("Rediscover", id="rediscover")
                        yield Static("04  /  VIRTUAL MACHINES", classes="dashboard-heading")
                        yield Static("Waiting for VM monitoring…", id="vm-monitor", markup=False)
                        yield Static("05  /  VIRTUAL DISK IMAGES", classes="dashboard-heading")
                        yield Static("VDI inventory not verified", id="vdi-monitor", markup=False)
                        with Horizontal(id="host-grid"):
                            yield Static("HOST STATUS\nWaiting for collection…", id="host-status", markup=False)
                            yield Static("HOST METRICS\nWaiting for collection…", id="host-metrics", markup=False)
                with TabPane("Virtual Machines", id="fleet"):
                    with Horizontal(id="fleet-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static("DEFINED VMS", classes="metric-title")
                            yield Static("—", id="vm-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("PROCESS SEEN", classes="metric-title")
                            yield Static("—", id="process-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("INVENTORY", classes="metric-title")
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
                        yield DataTable(id="fleet-table", cursor_type="row", zebra_stripes=True)
                        yield Static("No operation submitted.", id="action-status", markup=False)
                    yield Static("Select a VM to inspect its details.", id="detail-box", markup=False)
                    yield Static("READ-ONLY AUDIT\nWaiting for session…", id="audit-panel", markup=False)
            yield Static("1 Overview · 2 Virtual Machines · R refresh · Enter details · Q quit", id="notice")
            yield Footer()

    def on_mount(self) -> None:
        apply_theme(self, self._palette)
        self.query_one("#logout", Button).tooltip = "Logout"
        self.query_one("#vm-list", Vertical).border_title = "VM LIST"
        table = self.query_one("#fleet-table", DataTable)
        self._table_columns = table.add_columns("#", "VM name", "Object state", "Process", "vCPU", "Memory")
        self.query_one("#tabs", TabbedContent).display = False
        self.query_one("#login-box", VerticalScroll).display = True
        self._refresh_timer = self.set_interval(0.5, self._tick)
        self._set_width_class()
        self._resume_session()

    def on_resize(self) -> None:
        self._set_width_class()

    def _set_width_class(self) -> None:
        self.query_one("#shell", Vertical).set_class(self.size.width >= 110, "wide")

    def action_overview_page(self) -> None:
        if self.session is not None:
            self.query_one("#tabs", TabbedContent).active = "overview"

    def action_vms_page(self) -> None:
        if self.session is not None:
            self.query_one("#tabs", TabbedContent).active = "fleet"

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
        self._inventory_section = None
        self._inventory = None
        self._inventory_generation = None
        self._records.clear()
        self._selected_uuid = None
        self._table_order = ()
        self._table_content.clear()
        self.query_one("#fleet-table", DataTable).clear(columns=False)
        self.query_one("#vm-count", Static).update("—")
        self.query_one("#process-count", Static).update("—")
        self.query_one("#inventory-quality", Static).update("Not collected")
        self.query_one("#detail-box", Static).update("Select a VM to inspect its details.")
        self.query_one("#action-status", Static).update("No operation submitted.")
        self.query_one("#audit-panel", Static).update("READ-ONLY AUDIT\nWaiting for session…")
        self.query_one("#audit-panel", Static).display = False
        self.query_one("#host-status", Static).update("HOST STATUS\nWaiting for collection…")
        self.query_one("#host-metrics", Static).update("HOST METRICS\nWaiting for collection…")
        self._visible_snapshot = None
        self._history = OverviewHistory()
        self._render_cache.clear()
        self._heartbeat_color = None
        self.query_one("#nic-tabs", Horizontal).remove_children()
        self._nic_tab_names = ()
        self._nic_selected = None
        for widget_id in (
            "running-card", "cpu-card", "memory-card", "load-card", "heartbeat-card",
            "cpu-chart", "memory-chart", "load-chart", "heartbeat-details", "nic-detail",
            "vm-monitor", "vdi-monitor", "host-identity",
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

    @on(Button.Pressed, "#refresh-button")
    @on(Button.Pressed, "#overview-refresh")
    def refresh_button(self) -> None:
        self._request_refresh()

    @on(Button.Pressed, "#audit-toggle")
    def show_audit(self) -> None:
        panel = self.query_one("#audit-panel", Static)
        panel.display = not panel.display
        if panel.display:
            self._request_audit()

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
            if self.query_one("#tabs", TabbedContent).active == "overview":
                self._render_heartbeat_age()
            return
        if self.query_one("#tabs", TabbedContent).active == "overview":
            sections = self._overview_schedule.due()
            if sections:
                self._start_refresh(sections)
            else:
                self._render_heartbeat_age()
        else:
            import time

            now = time.monotonic()
            if now >= self._fleet_due:
                self._fleet_due = now + self.application.settings.refresh_interval
                self._start_refresh(("inventory",))

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
            sections = ("inventory",)
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

    def _render_heartbeat_age(self) -> None:
        # Low-cost UI clock: no PVM calls; render only if the text changed.
        snapshot = self._visible_snapshot
        if snapshot is None:
            return
        values = cards(snapshot, self._history, self._overview_schedule.interval)
        self._put("heartbeat-card", values["heartbeat-card"])
        self._color_heartbeat(values["heartbeat-card"])
        details = values["heartbeat-details"]
        self._put("heartbeat-details", details)

    def _color_heartbeat(self, text: str) -> None:
        color = (self._palette.error if "OFFLINE" in text else self._palette.warning if "WARNING" in text else self._palette.border)
        if color != self._heartbeat_color:
            self.query_one("#heartbeat-card", Static).styles.border = ("round", color)
            self._heartbeat_color = color

    def _put(self, widget_id: str, text: str) -> None:
        if self._render_cache.get(widget_id) != text:
            self.query_one(f"#{widget_id}", Static).update(styled_metric(text, palette=self._palette))
            self._render_cache[widget_id] = text

    def _render_overview(self, snapshot: ApplicationSnapshot) -> None:
        self._visible_snapshot = snapshot
        self._history.add(snapshot)
        values = cards(snapshot, self._history, self._overview_schedule.interval)
        for widget_id, text in values.items():
            self._put(widget_id, text)
        self._color_heartbeat(values["heartbeat-card"])
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
        selected_uuid = self._selected_uuid
        table = self.query_one("#fleet-table", DataTable)
        records: list[VMRecord] = []
        if inventory is not None:
            records = sorted(
                inventory.records,
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
            if order != self._table_order:
                table.clear(columns=False)
                for uuid, cells in rows.items():
                    table.add_row(*(Text(value) for value in cells), key=uuid)
            else:
                for uuid, cells in rows.items():
                    old = self._table_content.get(uuid, ())
                    for column, cell in enumerate(cells):
                        if column >= len(old) or cell != old[column]:
                            table.update_cell(uuid, self._table_columns[column], Text(cell), update_width=True)
            self._table_order, self._table_content = order, rows
            self.query_one("#vm-count", Static).update(str(len(inventory.records)))
            self.query_one("#process-count", Static).update(
                str(sum(record.process_seen for record in inventory.records))
            )
        else:
            if self._table_order:
                table.clear(columns=False)
                self._table_order, self._table_content = (), {}
            self.query_one("#vm-count", Static).update("—")
            self.query_one("#process-count", Static).update("—")
        if records:
            selected_uuid = (
                selected_uuid if selected_uuid in self._records else records[0].uuid
            )
            self._selected_uuid = selected_uuid
            selected_row = next(
                index for index, record in enumerate(records) if record.uuid == selected_uuid
            )
            table.move_cursor(row=selected_row, animate=False)
            self._render_record(self._records[selected_uuid])
        else:
            self._selected_uuid = None
            self._detail_base = "No VM records are currently available."
            self.query_one("#detail-box", Static).update(self._detail_base)
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

    def _render_host(self, snapshot: ApplicationSnapshot) -> None:
        status_section = snapshot.section("host_status")
        metric_section = snapshot.section("host_metrics")
        status = as_host_status(status_section) if status_section else None
        metrics = as_host_metrics(metric_section) if metric_section else None
        self.query_one("#host-status", Static).update(_host_status_text(status, status_section))
        self.query_one("#host-metrics", Static).update(_host_metrics_text(metrics, metric_section))

    @on(DataTable.RowHighlighted, "#fleet-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # A queued highlight may arrive while the screen is being torn down.
        if not self._running or not self.is_mounted(event.data_table):
            return
        key = getattr(event.row_key, "value", str(event.row_key))
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
        if self._selected_uuid:
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
        elif self._selected_uuid:
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
        # The operator's explicit action click is the intent; no extra dialog.
        try:
            approval = self.operations.approve(
                action, selection.records, section, interactive_confirmed=True
            )
        except AppError as exc:
            self._show_error(str(exc))
            return
        self._launch_operation(action, selection, section, approval, plan)

    def _launch_operation(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        approval: OperationApproval | None,
        plan: OperationPlan,
    ) -> None:
        if self._operation_active:
            self._show_error("An operation is already in progress.")
            return
        self._operation_active = True
        self.query_one("#bulk-actions", Select).disabled = True
        self.query_one("#logout", Button).disabled = True
        self._execute_action(action, selection, section, approval, plan)

    @work(thread=True, group="operation", exclusive=False)
    def _execute_action(
        self,
        action: Action,
        selection: TargetSelection,
        section: SectionSnapshot[object],
        approval: OperationApproval | None,
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
                    approval=approval,
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
    def _request_audit(self) -> None:
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
        self.call_from_thread(self._publish_audit, text)

    def _publish_audit(self, text: str) -> None:
        self.query_one("#audit-panel", Static).update(redact_text(text))


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


def _host_metrics_text(metrics: HostMetrics | None, section: SectionSnapshot[object] | None) -> str:
    lines = ["HOST METRICS", f"Collection  {_section_status(section)}"]
    if metrics is None:
        lines.append("No current monitoring values.")
        return redact_text("\n".join(lines))
    lines.extend(
        [
            f"System  {metrics.hostname or '—'}  ·  {metrics.os_version or '—'}",
            f"CPU  {_display(metrics.cpu_pct, suffix='%')}  ·  logical cores  {_display(metrics.logical_cores)}",
            f"Memory  {_bytes(metrics.memory_used_bytes)} / {_bytes(metrics.memory_total_bytes)}",
            f"Swap  {_bytes(metrics.swap_used_bytes)} / {_bytes(metrics.swap_total_bytes)}",
            f"Uptime  {metrics.uptime or '—'}",
            f"Interfaces  {len(metrics.interfaces)}  ·  storage mounts  {len(metrics.storage)}",
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

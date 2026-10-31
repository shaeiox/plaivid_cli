"""Textual presentation for the local PVM management application."""

from __future__ import annotations

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from plaivid_cli.application.operations import OperationCoordinator
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
    CSS = """
    Screen { background: #0b1220; color: #e5edf7; }
    #shell { height: 1fr; padding: 0 1; }
    #topbar { height: 3; padding: 0 1; background: #111d31; border: round #1d3554; }
    #brand { width: 1fr; color: #8be9fd; text-style: bold; content-align: left middle; }
    #session-label { width: auto; color: #91a6c4; content-align: right middle; }
    #login-box { width: 64; max-width: 92%; height: auto; border: round #36c2d1;
                 background: #111d31; padding: 1 2; margin: 2 0; }
    #login-title { color: #8be9fd; text-style: bold; padding-bottom: 1; }
    #login-warning { color: #ffc766; padding: 1 0; }
    #login-error { color: #ff7788; padding: 1 0; }
    #login-buttons { height: auto; align-horizontal: right; margin-top: 1; }
    #workspace { height: 1fr; }
    TabbedContent { height: 1fr; border: round #1d3554; background: #0f1929; }
    TabPane { padding: 1; }
    #fleet-summary { height: 5; }
    .metric-card { width: 1fr; height: 4; margin-right: 1; padding: 0 1;
                   border: round #254568; background: #111d31; }
    .metric-title { color: #91a6c4; }
    .metric-value { color: #8be9fd; text-style: bold; }
    #vm-list { height: 1fr; min-height: 13; border: round #254568; background: #111d31; }
    #vm-toolbar { height: 3; }
    #bulk-actions { width: 28; }
    #fleet-table { height: 1fr; min-height: 8; border: round #1d3554; }
    #detail-box { height: 10; margin-top: 1; border: round #254568; background: #111d31; padding: 1; }
    #action-status { height: 2; color: #ffc766; }
    #host-grid { height: auto; }
    #host-status, #host-metrics, #audit-panel { height: 1fr; border: round #254568;
                                                background: #111d31; padding: 1; }
    #host-status { width: 1fr; margin-right: 1; }
    #host-metrics { width: 1fr; }
    #audit-panel { height: 1fr; }
    .section-title { color: #8be9fd; text-style: bold; padding-bottom: 1; }
    #notice { height: 2; color: #91a6c4; padding: 0 1; }
    #refresh-button { width: 12; }
    #select-all { width: auto; margin-left: 2; color: #ffc766; }
    """
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("enter", "details", "Details"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        application: PlaividApplication,
        operations: OperationCoordinator,
        sessions: SessionManager,
    ) -> None:
        super().__init__()
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

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            Header(show_clock=True)
            with Horizontal(id="topbar"):
                yield Static("PLAIVID  /  PVM MANAGEMENT", id="brand")
                yield Static("● Offline", id="session-label", markup=False)
                yield Button("Logout", id="logout", variant="default")
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
            with TabbedContent(initial="fleet", id="tabs"):
                with TabPane("Fleet", id="fleet"):
                    with Horizontal(id="fleet-summary"):
                        with Vertical(classes="metric-card"):
                            yield Static("DEFINED OBJECTS", classes="metric-title")
                            yield Static("—", id="vm-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("PROCESS OBSERVED", classes="metric-title")
                            yield Static("—", id="process-count", classes="metric-value")
                        with Vertical(classes="metric-card"):
                            yield Static("INVENTORY EVIDENCE", classes="metric-title")
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
                        yield DataTable(id="fleet-table", cursor_type="row", zebra_stripes=True)
                        yield Static("No operation submitted.", id="action-status", markup=False)
                    yield Static("Select a VM to inspect its details.", id="detail-box", markup=False)
                with TabPane("Host", id="host"):
                    with Horizontal(id="host-grid"):
                        yield Static("HOST STATUS\nWaiting for collection…", id="host-status", markup=False)
                        yield Static("HOST METRICS\nWaiting for collection…", id="host-metrics", markup=False)
                with TabPane("Audit", id="audit"):
                    yield Static("READ-ONLY AUDIT\nWaiting for session…", id="audit-panel", markup=False)
            yield Static("Press R to refresh · Enter for VM details · Q to quit", id="notice")
            Footer()

    def on_mount(self) -> None:
        self.query_one("#vm-list", Vertical).border_title = "VM LIST"
        table = self.query_one("#fleet-table", DataTable)
        table.add_columns("#", "VM name", "UUID", "Object state", "Process", "vCPU", "Memory")
        self.query_one("#tabs", TabbedContent).display = False
        self.query_one("#login-box", VerticalScroll).display = True
        self._refresh_timer = self.set_interval(
            self.application.settings.refresh_interval, self._request_refresh
        )
        self._resume_session()

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

    def _session_ended(self, message: str) -> None:
        self.session = None
        self.query_one("#session-label", Static).update("● Offline")
        self.query_one("#tabs", TabbedContent).display = False
        self.query_one("#login-box", VerticalScroll).display = True
        self.query_one("#login-error", Static).update(message)

    def _login_required(self, message: str) -> None:
        self.query_one("#login", Button).disabled = False
        self.query_one("#login-error", Static).update(message)

    def _session_ready(self, session: PvmSession) -> None:
        self.session = session
        self.query_one("#session-label", Static).update(
            redact_text(f"● {session.username}  /  session active")
        )
        self.query_one("#login-box", VerticalScroll).display = False
        self.query_one("#tabs", TabbedContent).display = True
        self._request_refresh()

    @on(TabbedContent.TabActivated, "#tabs")
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if self.session is None:
            return
        if event.pane.id == "audit":
            self._request_audit()
        else:
            self._request_refresh()

    def action_refresh(self) -> None:
        if self.query_one("#tabs", TabbedContent).active == "audit":
            self._request_audit()
        else:
            self._request_refresh()

    @on(Button.Pressed, "#refresh-button")
    def refresh_button(self) -> None:
        self._request_refresh()

    def _request_refresh(self) -> None:
        if self.session is None:
            return
        active = self.query_one("#tabs", TabbedContent).active
        if active == "audit":
            return
        sections = ("inventory",) if active == "fleet" else ("host_status", "host_metrics")
        self._collect_visible(sections)

    @work(thread=True, group="refresh", exclusive=True)
    def _collect_visible(self, sections: tuple[str, ...]) -> None:
        session = self.session
        if session is None:
            return
        try:
            snapshot = self.application.refresh(session.token, sections=sections)
        except Exception as exc:
            self.call_from_thread(self._show_error, f"Refresh failed: {type(exc).__name__}")
            return
        self.call_from_thread(self._publish_snapshot, snapshot)

    def _publish_snapshot(self, snapshot: ApplicationSnapshot) -> None:
        inventory_section = snapshot.section("inventory")
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
        table.clear(columns=False)
        records: list[VMRecord] = []
        if inventory is not None:
            records = sorted(
                inventory.records,
                key=lambda item: (0 if item.process_seen else 1, item.name.casefold(), item.uuid),
            )
            for index, record in enumerate(records, start=1):
                table.add_row(
                    Text(str(index)),
                    Text(redact_text(record.name)),
                    Text(record.uuid),
                    Text(redact_text(record.state)),
                    Text("Observed" if record.process_seen else "Not observed"),
                    Text(_display(record.vcpu)),
                    Text(_display(record.mem_mb, suffix=" MB")),
                    key=record.uuid,
                )
            self.query_one("#vm-count", Static).update(str(len(inventory.records)))
            self.query_one("#process-count", Static).update(
                str(sum(record.process_seen for record in inventory.records))
            )
        else:
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
            "#79e2a7" if inventory_section and inventory_section.status is CollectionStatus.CURRENT else "#ffc766"
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

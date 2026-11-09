"""Textual presentation for the local PVM management application."""

from __future__ import annotations

import os

from textual import events, on
from textual.app import App
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Select,
    Static,
    TabbedContent,
)

from plaivid_cli.application.operations import Admission, OperationCoordinator, TaskManager
from plaivid_cli.application.overview import OverviewHistory, OverviewSchedule
from plaivid_cli.application.services import (
    PlaividApplication,
)
from plaivid_cli.application.session import SessionManager
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.models import (
    ApplicationSnapshot,
    InventoryData,
    PvmSession,
    SectionSnapshot,
    TaskEvent,
    VMDetail,
    VMRecord,
)
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.charts import (
    default_chart_mode,
)
from plaivid_cli.presentation.theme import (
    apply_theme,
    group_color,
    group_title,
    palette_for,
)

from .audit import AuditMixin
from .components import CheckableTable, TaskViewFooter
from .layout import LayoutMixin
from .messages import (
    OperationFinished,
    TaskAdmissionRefused,
    TaskCompleted,
    TaskDispatched,
    TaskFailed,
    TaskMessage,
    TaskProgress,
    TaskRegistryReset,
    TaskSkipped,
    TaskStarted,
    TaskUnknown,
)
from .pages.overview.controller import OverviewMixin
from .pages.overview.host_controller import HostPageMixin
from .pages.virtual_desktops.controller import DesktopMixin
from .pages.virtual_machines.controller import VirtualMachinesMixin
from .refresh import RefreshMixin
from .session import SessionMixin
from .styles import TUI_CSS

# TaskManager event kind -> Textual message class. ``refused`` and ``reset`` are
# handled separately because they carry no task record.
_MESSAGE_FOR_KIND = {
    "dispatched": TaskDispatched,
    "started": TaskStarted,
    "progress": TaskProgress,
    "completed": TaskCompleted,
    "failed": TaskFailed,
    "skipped": TaskSkipped,
    "unknown": TaskUnknown,
}


class PlaividTui(
    LayoutMixin,
    SessionMixin,
    RefreshMixin,
    OverviewMixin,
    DesktopMixin,
    HostPageMixin,
    VirtualMachinesMixin,
    AuditMixin,
    App[None],
):
    """Operator dashboard shell assembled from page/session/refresh behaviors."""

    TITLE = "Plaivid PVM Console"
    SUB_TITLE = "Local management · Linux"
    CSS = TUI_CSS

    BINDINGS = [
        ("space", "toggle_check", "Select row"),
        ("a", "toggle_all", "Select all shown"),
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
        # Selected-VM detail: the record always paints, the asynchronous read and
        # its in-flight/failed state paint on top of it.
        self._detail_record: VMRecord | None = None
        self._detail_loaded: VMDetail | None = None
        self._detail_uuid: str | None = None
        self._detail_status = None
        self._refresh_timer = None
        # Per-target admission replaces the former global boolean. The listener
        # runs on whichever thread published the event (UI thread for admission,
        # worker thread for progress); `post_message` is thread-safe and returns
        # False instead of raising once the app is closing.
        self._tasks = TaskManager(self._publish_task_event)
        self._task_epoch = 0
        self._refresh_busy = False
        self._pending_manual_refresh = False
        self._session_epoch = 0
        self._inventory_generation: int | None = None
        self._table_order: tuple[str, ...] = ()
        self._table_content: dict[str, tuple[str, ...]] = {}
        self._table_columns = ()
        self._render_cache: dict[str, str] = {}
        self._chart_mode = default_chart_mode()
        self._load_scale: float | None = None
        self._cpu_scale: float | None = None
        # Next wall-clock chart redraw; the 60 s window advances without new samples.
        self._chart_tick_due = 0.0
        self._overview_schedule = OverviewSchedule(
            min(60, max(1, application.settings.refresh_interval)),
            host_status_interval=application.settings.host_status_interval,
        )
        self._history = OverviewHistory()
        self._nic_selected: str | None = None
        self._nic_tab_names: tuple[str, ...] = ()
        self._fleet_due = 0.0
        self._visible_snapshot: ApplicationSnapshot | None = None
        self._desktops: dict[str, VirtualDesktop] = {}
        self._desktop_selected: str | None = None
        self._vm_checked: set[str] = set()
        self._desktop_checked: set[str] = set()
        self._desktop_section: SectionSnapshot[object] | None = None
        self._desktop_generation: int | None = None
        self._desktop_min_generation = application.collection.snapshot.generation
        self._desktop_rows: tuple[str, ...] = ()
        self._desktop_cells: dict[str, tuple[str, ...]] = {}

    def _group_box(self, box, group: str, title: str) -> None:
        """Title and border of a card, coloured by its group (plain when colour is off)."""
        box.border_title = group_title(group, title, self._palette)
        colour = group_color(group, self._palette)
        if colour is not None:
            box.styles.border = ("round", colour)

    def on_mount(self) -> None:
        apply_theme(self, self._palette)
        self.query_one("#logout", Button).tooltip = "Logout"
        self._group_box(self.query_one("#vm-list", Vertical), "vms", "VM list")
        self._group_box(self.query_one("#desktop-list", Vertical), "vms", "Desktop list")
        self.query_one("#detail-scroll", VerticalScroll).border_title = group_title(
            "vms", "Selected VM", self._palette
        )
        table = self.query_one("#fleet-table", DataTable)
        self._table_columns = table.add_columns(
            "✓", "#", "VM name", "Object state", "Process", "vCPU", "Memory"
        )
        self._desktop_columns = self.query_one("#desktop-table", DataTable).add_columns(
            "✓", "Desktop", "UUID", "Cluster status", "OS", "vCPU"
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

    # ------------------------------------------------------------- task board

    @property
    def tasks(self) -> TaskManager:
        """The shared task board (admission + history) for this session."""
        return self._tasks

    @property
    def _operation_active(self) -> bool:
        """True while any admitted target is still in flight.

        Retained as a read-only compatibility surface for the session/refresh
        behaviors; admission decisions belong to ``TaskManager.admit``.
        """
        return self._tasks.any_active()

    def _publish_task_event(self, event: TaskEvent) -> None:
        """TaskManager listener: translate an event into a Textual message.

        Called from the UI thread during admission and from a worker thread for
        progress, so it must only post messages — never touch widgets.
        """
        kind = event.kind
        if kind == "reset":
            self.post_message(TaskRegistryReset(event.message))
            return
        epoch = self._task_epoch
        if kind == "refused":
            self.post_message(
                TaskAdmissionRefused(
                    event.action, event.targets, event.reason  # type: ignore[arg-type]
                )
            )
            return
        record = event.record
        if record is None:
            return
        message = _MESSAGE_FOR_KIND.get(kind)
        if message is not None:
            self.post_message(message(record, epoch))

    def _apply_task_message(self, message: TaskMessage) -> None:
        """Single UI-thread path that updates the board.

        Events published before the current board epoch are discarded: a worker
        message may be delivered after the reset that superseded it.
        """
        if message.epoch < self._task_epoch:
            return
        try:
            self.query_one("#task-footer", TaskViewFooter).apply_record(message.record)
        except NoMatches:
            return

    def _task_admission_message(self, event: TaskAdmissionRefused) -> str:
        """Explain a refused request without implying a task exists."""
        count = len(event.targets)
        scope = f"{count} target(s)" if count > 1 else "the selected target"
        if event.reason == Admission.DUPLICATE.value:
            return (
                f"{event.action.value.upper()} is already running for {scope}; "
                "the duplicate request was ignored."
            )
        if event.reason == Admission.CONFLICT.value:
            busy = ", ".join(
                action.value.upper() for action in self._tasks.busy_actions()
            )
            return (
                f"{event.action.value.upper()} refused: {scope} already has "
                f"{busy or 'another action'} in progress."
            )
        return (
            f"{event.action.value.upper()} refused: another operation is already in "
            "progress. Wait for it to finish or review the task board."
        )

    @on(TaskAdmissionRefused)
    def task_admission_refused(self, event: TaskAdmissionRefused) -> None:
        text = self._task_admission_message(event)
        # No row is created for a refused request: surface it inline only.
        try:
            self.query_one("#action-status", Static).update(redact_text(text))
            self.query_one("#desktop-action-status", Static).update(redact_text(text))
        except NoMatches:
            return

    @on(OperationFinished)
    def operation_finished(self, event: OperationFinished) -> None:
        """Re-enable the action controls once the whole submission settled.

        The whole body is guarded: a completion can arrive while the app is
        shutting down, when the widgets it addresses are already gone.
        """
        try:
            for selector in ("#bulk-actions", "#desktop-actions"):
                self.query_one(selector, Select).disabled = False
            self.query_one("#logout", Button).disabled = False
            if event.page == "desktops":
                if event.result is not None:
                    self._desktop_message(self._desktop_result_text(event.result))
                    self._publish_snapshot(self.application.collection.snapshot)
                elif event.error:
                    self._desktop_message(event.error)
            elif event.result is not None:
                self._show_operation(event.result)
            elif event.error:
                self._show_error(event.error)
            self._request_refresh()
        except NoMatches:
            return

    @on(TaskRegistryReset)
    def task_registry_reset(self, event: TaskRegistryReset) -> None:
        # Bump the epoch first so in-flight worker messages become stale.
        self._task_epoch += 1
        try:
            self.query_one("#task-footer", TaskViewFooter).clear_board()
        except NoMatches:
            return

    # Each message class maps to the same one-line handler; Textual dispatches
    # by message type, so the concrete class is what selects the handler.
    @on(TaskDispatched)
    def task_dispatched(self, event: TaskDispatched) -> None:
        self._apply_task_message(event)

    @on(TaskStarted)
    def task_started(self, event: TaskStarted) -> None:
        self._apply_task_message(event)

    @on(TaskProgress)
    def task_progress(self, event: TaskProgress) -> None:
        self._apply_task_message(event)

    @on(TaskCompleted)
    def task_completed(self, event: TaskCompleted) -> None:
        self._apply_task_message(event)

    @on(TaskFailed)
    def task_failed(self, event: TaskFailed) -> None:
        self._apply_task_message(event)

    @on(TaskSkipped)
    def task_skipped(self, event: TaskSkipped) -> None:
        self._apply_task_message(event)

    @on(TaskUnknown)
    def task_unknown(self, event: TaskUnknown) -> None:
        self._apply_task_message(event)

    # Textual discovers decorated handlers from the concrete App class. The
    # feature mixins keep behavior modular; these thin bindings register events.
    @on(Button.Pressed, "#login")
    def submit_login(self) -> None:
        SessionMixin.submit_login(self)

    @on(Button.Pressed, "#logout")
    def submit_logout(self) -> None:
        SessionMixin.submit_logout(self)

    @on(TabbedContent.TabActivated, "#tabs")
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        SessionMixin.tab_activated(self, event)

    @on(Button.Pressed, "#desktop-refresh")
    @on(Button.Pressed, "#refresh-button")
    @on(Button.Pressed, "#overview-refresh")
    def refresh_button(self) -> None:
        RefreshMixin.refresh_button(self)

    @on(Button.Pressed, "#audit-toggle")
    def show_audit(self) -> None:
        RefreshMixin.show_audit(self)

    @on(Button.Pressed, "#desktop-audit-toggle")
    def show_desktop_audit(self) -> None:
        RefreshMixin.show_desktop_audit(self)

    @on(Button.Pressed, "#interval-apply")
    def apply_interval(self) -> None:
        RefreshMixin.apply_interval(self)

    @on(Input.Changed, "#desktop-search")
    def desktop_search_changed(self) -> None:
        DesktopMixin.desktop_search_changed(self)

    @on(Checkbox.Changed, "#desktop-all")
    def desktop_scope_changed(self) -> None:
        DesktopMixin.desktop_scope_changed(self)

    @on(DataTable.RowHighlighted, "#desktop-table")
    def desktop_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        DesktopMixin.desktop_row_highlighted(self, event)

    @on(Select.Changed, "#desktop-actions")
    def desktop_action_requested(self, event: Select.Changed) -> None:
        DesktopMixin.desktop_action_requested(self, event)

    @on(Checkbox.Changed, "#select-all")
    def vm_scope_changed(self) -> None:
        VirtualMachinesMixin.vm_scope_changed(self)

    @on(Input.Changed, "#vm-search")
    def vm_search_changed(self) -> None:
        VirtualMachinesMixin.vm_search_changed(self)

    @on(CheckableTable.CheckRequested)
    def check_requested(self, event: CheckableTable.CheckRequested) -> None:
        VirtualMachinesMixin.check_requested(self, event)

    @on(DataTable.RowHighlighted, "#fleet-table")
    def row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        VirtualMachinesMixin.row_highlighted(self, event)

    @on(Select.Changed, "#bulk-actions")
    def bulk_action_selected(self, event: Select.Changed) -> None:
        VirtualMachinesMixin.bulk_action_selected(self, event)

"""Textual presentation for the local PVM management application."""

from __future__ import annotations

import os

from textual import events, on
from textual.app import App
from textual.containers import Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Select,
    TabbedContent,
)

from plaivid_cli.application.operations import OperationCoordinator
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
    VMRecord,
)
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
from .components import CheckableTable
from .layout import LayoutMixin
from .pages.overview.controller import OverviewMixin
from .pages.overview.host_controller import HostPageMixin
from .pages.virtual_desktops.controller import DesktopMixin
from .pages.virtual_machines.controller import VirtualMachinesMixin
from .refresh import RefreshMixin
from .session import SessionMixin
from .styles import TUI_CSS


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

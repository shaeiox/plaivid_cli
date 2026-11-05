"""Textual presentation for the local PVM management application."""

from __future__ import annotations

from textual import on, work
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Static,
    TabbedContent,
)

from plaivid_cli.application.overview import OverviewHistory
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    PvmSession,
)
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.charts import ChartView

from .support import _METRIC_PANELS


class SessionMixin:
    """Session behavior for the composed Textual application."""

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
        self._desktop_checked.clear()
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
        self.query_one("#desktop-audit-panel", Static).update(
            "Read-only audit\nWaiting for session…"
        )
        self.query_one("#desktop-audit-panel", Static).display = False
        self._inventory_section = None
        self._inventory = None
        self._inventory_generation = None
        self._records.clear()
        self.query_one("#vm-search", Input).value = ""
        self.query_one("#select-all", Checkbox).value = False
        self._selected_uuid = None
        self._vm_checked.clear()
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
        self.query_one("#host-banner", Static).update("")
        self.query_one("#host-status", Static).update("Waiting for collection…")
        for panel in _METRIC_PANELS:
            self.query_one(f"#{panel}", Static).update("Waiting for collection…")
        self._visible_snapshot = None
        self._history = OverviewHistory()
        self._render_cache.clear()
        self.query_one("#nic-tabs", Horizontal).remove_children()
        self._nic_tab_names = ()
        self._nic_selected = None
        for widget_id in (
            "running-card",
            "cpu-card",
            "memory-card",
            "load-card",
            "nic-detail",
            "host-identity",
        ):
            self.query_one(f"#{widget_id}", Static).update(
                "Waiting for authenticated monitoring data…"
            )
        for widget_id in ("cpu-chart", "load-chart"):
            self.query_one(f"#{widget_id}", ChartView).reset(
                "Waiting for authenticated monitoring data…"
            )
        self._load_scale = None
        self._cpu_scale = None

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

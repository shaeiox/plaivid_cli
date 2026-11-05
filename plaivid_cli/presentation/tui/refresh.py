"""Textual presentation for the local PVM management application."""

from __future__ import annotations

from textual import on, work
from textual.widgets import (
    Button,
    Input,
    Static,
    TabbedContent,
)

from plaivid_cli.domain.models import (
    ApplicationSnapshot,
)
from plaivid_cli.presentation.theme import styled_metric

from .pages.virtual_desktops.policy import MIN_REFRESH_SECONDS


class RefreshMixin:
    """Refresh behavior for the composed Textual application."""

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
            background = self._overview_schedule.background_due()
            if background:
                self._start_refresh(background)
                return
            import time

            now = time.monotonic()
            if now >= self._fleet_due:
                section = (
                    "desktops"
                    if self.query_one("#tabs", TabbedContent).active == "desktops"
                    else "inventory"
                )
                interval = (
                    max(MIN_REFRESH_SECONDS, self.application.settings.refresh_interval)
                    if section == "desktops"
                    else self.application.settings.refresh_interval
                )
                self._fleet_due = now + interval
                self._start_refresh((section,))

    def _request_refresh(self) -> None:
        if self.session is None:
            return
        if self._refresh_busy:
            self._pending_manual_refresh = True
            return
        if self.query_one("#tabs", TabbedContent).active == "overview":
            sections = (
                "physical_nics",
                "local_host",
                "nic_samples",
                "inventory",
                "dashboard",
                "host_status",
                "host_metrics",
            )
            self._overview_schedule.busy = True
        else:
            sections = (
                ("desktops",)
                if self.query_one("#tabs", TabbedContent).active == "desktops"
                else ("inventory",)
            )
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
            background = sections == ("local_host",)
            self.call_from_thread(self._publish_if_current, snapshot, epoch, background)
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

    def _publish_if_current(
        self, snapshot: ApplicationSnapshot, epoch: int, background: bool = False
    ) -> None:
        if self.session is not None and epoch == self._session_epoch:
            if background:
                # Another tab is visible: record the sample and redraw only the graphs.
                self._history.add(snapshot)
                self._render_charts()
            else:
                self._publish_snapshot(snapshot)

    def _put(self, widget_id: str, text: str, *, setter=None) -> None:
        if self._render_cache.get(widget_id) != text:
            rendered = styled_metric(text, palette=self._palette)
            if setter is None:
                self.query_one(f"#{widget_id}", Static).update(rendered)
            else:
                setter(rendered)
            self._render_cache[widget_id] = text

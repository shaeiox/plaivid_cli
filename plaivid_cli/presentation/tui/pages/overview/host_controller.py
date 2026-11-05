"""Host-status and metrics page rendering, isolated from Desktop inventory behavior."""

from __future__ import annotations

from plaivid_cli.application.services import as_host_metrics, as_host_status
from plaivid_cli.domain.models import ApplicationSnapshot, HostMetrics, SectionSnapshot
from plaivid_cli.domain.overview import LocalHostSample
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation import overview_metrics as hm
from plaivid_cli.presentation.logo import LOGO_COLOR, logo_text
from plaivid_cli.presentation.theme import ALARM, CAUTION, group_color
from plaivid_cli.presentation.tui.pages.overview.components import (
    HostStatusCard,
    NetworkCard,
    ProcessesCard,
    SessionsCard,
    StorageCard,
    TemperatureCard,
)

from ...components.status import section_status as _section_status
from .components.host_status import _host_banner_text, _host_status_text, _quorum_verdict


class HostPageMixin:
    """Format status and metrics snapshots into the Overview host panels."""

    def _render_host(self, snapshot: ApplicationSnapshot) -> None:
        status_section = snapshot.section("host_status")
        metric_section = snapshot.section("host_metrics")
        status = as_host_status(status_section) if status_section else None
        metrics = as_host_metrics(metric_section) if metric_section else None
        local = snapshot.section("local_host")
        local_sample = (
            local.value
            if local is not None and local.value is not None
            else (local.last_good_value if local else None)
        )
        pid_file = (
            local_sample.sballd_pid_file if isinstance(local_sample, LocalHostSample) else None
        )
        level, _, _ = _quorum_verdict(status_section, self._palette, pid_file)
        logo_colour = {"ok": LOGO_COLOR, "warn": CAUTION, "bad": ALARM}[level]
        host_card = self.query_one("#host-status-box", HostStatusCard)
        host_card.set_logo(logo_text(logo_colour))
        host_card.set_banner(_host_banner_text(status_section, self._palette, pid_file))
        host_card.set_details(
            _host_status_text(
                status, status_section, self._palette, pid_file, group_color("host", self._palette)
            )
        )
        self._render_metric_panels(metrics, metric_section)

    def _render_metric_panels(
        self, metrics: HostMetrics | None, section: SectionSnapshot[object] | None
    ) -> None:
        status = _section_status(section)
        texts = {
            "metrics-network": hm.finish(hm.network_body(metrics), status),
            "metrics-storage": hm.finish(hm.storage_body(metrics), status),
            "metrics-temperature": hm.finish(hm.temperature_body(metrics), status),
            "metrics-sessions": hm.finish(hm.sessions_body(metrics), status),
            "metrics-processes": hm.finish(hm.processes_body(metrics), status),
            "metrics-commands": redact_text("\n".join(hm.commands_body(metrics))),
        }
        self.query_one("#network-box", NetworkCard).set_metrics(texts["metrics-network"])
        self.query_one("#storage-box", StorageCard).set_content(texts["metrics-storage"])
        self.query_one("#temperature-box", TemperatureCard).set_content(
            texts["metrics-temperature"]
        )
        self.query_one("#sessions-box", SessionsCard).set_content(texts["metrics-sessions"])
        processes = self.query_one("#processes-card", ProcessesCard)
        processes.set_processes(texts["metrics-processes"])
        processes.set_commands(texts["metrics-commands"])
        total = metrics.process_total if metrics is not None else None
        title = (
            "Top processes by CPU" if total is None else f"Top processes by CPU · {total:,} total"
        )
        processes.set_title(title)

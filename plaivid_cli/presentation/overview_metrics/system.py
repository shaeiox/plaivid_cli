"""System telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _DASH, _NONE, row


def system_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    return [
        row("Host ID", m.host_id or _DASH),
        row("Platform", f"{m.os_version or _DASH} ({m.platform_family or _DASH})"),
        row("Kernel", m.kernel_version or _DASH),
        row("Virtual", m.virtualization or _DASH),
        row("Boot time", m.boot_time or _DASH),
    ]

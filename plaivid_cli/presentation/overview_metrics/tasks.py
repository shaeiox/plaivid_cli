"""Tasks telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import number, row


def tasks_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    return [
        row("Tasks", f"total {number(m.total_tasks)}  ·  blocked {number(m.blocked_tasks)}"),
        row("Processes", f"{number(m.num_processes)}  ·  threads {number(m.num_threads)}"),
        row("Open FDs", number(m.open_fds)),
    ]

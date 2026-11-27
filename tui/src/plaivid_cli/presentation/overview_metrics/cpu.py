"""Cpu telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _DASH, number, row


def cpu_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    clock = f"{m.cpu_current_hz / 1e9:.2f} GHz" if m.cpu_current_hz else _DASH
    return [
        row("Model", m.cpu_model or _DASH),
        row("Clock", clock),
        row(
            "Cores",
            f"logical {number(m.logical_cores)} · physical {number(m.physical_cores)} · scheduler {number(m.cpu_count)}",
        ),
        row(
            "Run queue",
            f"{number(m.run_queue)}  ·  blocked {number(m.blocked_tasks)} ({number(m.blocked_percent, '%')})",
        ),
        row("Context SW", number(m.context_switches)),
        row("Interrupts", f"{number(m.interrupts)}  ·  forks {number(m.forks)}"),
    ]

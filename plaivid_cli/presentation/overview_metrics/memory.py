"""Memory telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import bar, number, pct_of, row, size


def memory_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    swap_pct = pct_of(m.swap_used_bytes, m.swap_total_bytes)
    return [
        row(
            "Swap",
            f"{size(m.swap_used_bytes)} / {size(m.swap_total_bytes)}  {number(swap_pct, '%')}",
        ),
        bar(swap_pct),
    ]

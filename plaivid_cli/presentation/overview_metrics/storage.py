"""Storage telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _NONE, bar, number, size


def storage_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.storage:
        return ["No real filesystems reported."]
    lines: list[str] = []
    for part in m.storage[:8]:
        lines.append(f"{part.mountpoint[:26]:<27}{number(part.used_percent, '%'):>7}")
        lines.append(f"{bar(part.used_percent, 26)}")
        lines.append(f"{size(part.used_bytes)} of {size(part.total_bytes)}")
    if len(m.storage) > 8:
        lines.append(f"… {len(m.storage) - 8} more")
    return lines

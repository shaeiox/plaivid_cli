"""Network telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _DASH, _NONE, size


def network_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.interfaces:
        return ["No interfaces reported."]
    lines = [f"{'NAME':<12}{'TYPE':<11}{'STATE':<9}RX / TX"]
    for nic in m.interfaces[:12]:
        mark = "●" if (nic.state or "").lower() == "up" else "○"
        lines.append(
            f"{mark} {nic.name[:10]:<10}{(nic.kind or _DASH)[:10]:<11}{(nic.state or _DASH)[:8]:<9}"
            f"{size(nic.rx_bytes)} / {size(nic.tx_bytes)}"
        )
    if len(m.interfaces) > 12:
        lines.append(f"… {len(m.interfaces) - 12} more interfaces")
    return lines

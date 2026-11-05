"""Temperature telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _NONE, bar


def temperature_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.temperatures:
        return ["No sensors reported."]
    hottest = max(m.temperatures, key=lambda reading: reading.celsius)
    lines = [f"Hottest  {hottest.sensor}  {hottest.celsius:.1f} °C"]
    for reading in m.temperatures[:8]:
        ratio = max(0.0, min(100.0, reading.celsius))
        lines.append(f"{reading.sensor[:22]:<23}{reading.celsius:5.1f}° {bar(ratio, 12)}")
    if len(m.temperatures) > 8:
        lines.append(f"… {len(m.temperatures) - 8} more")
    return lines

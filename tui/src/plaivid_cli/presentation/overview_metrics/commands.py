"""Commands telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _NONE


def commands_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.command_summary:
        return ["No process samples reported."]
    return [f"● {name[:26]:<27}×{count}" for name, count in m.command_summary]

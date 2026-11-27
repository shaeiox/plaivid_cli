"""Sessions telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _DASH, _NONE


def sessions_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.users:
        return ["No sessions reported."]
    lines = [f"{'USER':<10}{'TERMINAL':<10}{'FROM':<17}STARTED"]
    for user in m.users[:10]:
        lines.append(
            f"● {user.user[:8]:<8}{(user.terminal or _DASH)[:9]:<10}{(user.host or 'local')[:16]:<17}{user.started or _DASH}"
        )
    return lines

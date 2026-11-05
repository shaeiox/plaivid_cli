"""Processes telemetry text presentation."""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics

from .common import _DASH, _NONE, number


def processes_body(m: HostMetrics | None, limit: int = 8) -> list[str]:
    if m is None:
        return _NONE
    if not m.processes:
        return ["No process samples reported."]
    lines = [f"{'PID':>7}  {'USER':<10}{'CPU%':>7}{'MEM%':>7}{'THR':>5}  {'STATE':<8}COMMAND"]
    for proc in m.processes[:limit]:
        name = proc.command or (proc.exe or "").rsplit("/", 1)[-1] or _DASH
        lines.append(
            f"{proc.pid:>7}  {(proc.username or _DASH)[:10]:<10}{number(proc.cpu_pct):>7}"
            f"{number(proc.memory_pct):>7}{number(proc.threads):>5}  {(proc.state or _DASH)[:8]:<8}{name[:30]}"
        )
    return lines

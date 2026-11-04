"""Purely presentational host-metrics panels built from one HostMetrics value.

Each function returns plain text; missing values render as an em dash, never as zero.
"""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics
from plaivid_cli.domain.redaction import redact_text

_DASH = "—"
_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


def size(value: int | None) -> str:
    if value is None:
        return _DASH
    amount = float(value)
    for unit in _UNITS:
        if amount < 1024 or unit == _UNITS[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return _DASH


def number(value: int | float | None, suffix: str = "") -> str:
    if value is None:
        return _DASH
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value:,}{suffix}"


def bar(percent: float | None, width: int = 16) -> str:
    if percent is None:
        return _DASH
    ratio = max(0, min(width, round(percent * width / 100)))
    return "━" * ratio + "╺" * (width - ratio)


def _pct_of(used: int | None, total: int | None) -> float | None:
    if used is None or not total:
        return None
    return 100.0 * used / total


def _panel(title: str, lines: list[str]) -> str:
    return redact_text("\n".join([title, *lines]))


def _empty(title: str) -> str:
    return _panel(title, ["No current monitoring values."])


def system_panel(m: HostMetrics | None, status: str) -> str:
    title = f"SYSTEM  ·  {status}"
    if m is None:
        return _empty(title)
    seconds = f" ({m.uptime_seconds:,} s)" if m.uptime_seconds is not None else ""
    return _panel(title, [
        f"Host        {m.hostname or _DASH}",
        f"Host ID     {m.host_id or _DASH}",
        f"Platform    {m.os_version or _DASH}  ·  family {m.platform_family or _DASH}",
        f"Kernel      {m.kernel_version or _DASH}",
        f"Virtual     {m.virtualization or _DASH}",
        f"Boot time   {m.boot_time or _DASH}",
        f"Uptime      {m.uptime or _DASH}{seconds}",
    ])


def cpu_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("CPU")
    return _panel("CPU", [
        f"Usage       {number(m.cpu_pct, '%')}  {bar(m.cpu_pct)}",
        f"Cores       logical {number(m.logical_cores)}  ·  physical {number(m.physical_cores)}  ·  scheduler {number(m.cpu_count)}",
        f"Run queue   {number(m.run_queue)}  ·  blocked {number(m.blocked_tasks)} ({number(m.blocked_percent, '%')})",
        f"Context sw  {number(m.context_switches)}",
        f"Interrupts  {number(m.interrupts)}  ·  forks {number(m.forks)}",
    ])


def memory_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("MEMORY")
    used_pct = _pct_of(m.memory_used_bytes, m.memory_total_bytes)
    swap_pct = _pct_of(m.swap_used_bytes, m.swap_total_bytes)
    return _panel("MEMORY", [
        f"RAM         {size(m.memory_used_bytes)} / {size(m.memory_total_bytes)}  {number(used_pct, '%')}",
        f"            {bar(used_pct)}",
        f"Swap        {size(m.swap_used_bytes)} / {size(m.swap_total_bytes)}  {number(swap_pct, '%')}",
    ])


def tasks_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("LOAD & TASKS")
    return _panel("LOAD & TASKS", [
        f"Tasks       total {number(m.total_tasks)}  ·  blocked {number(m.blocked_tasks)}",
        f"Processes   {number(m.num_processes)}  ·  threads {number(m.num_threads)}",
        f"Open fds    {number(m.open_fds)}",
        f"Run queue   {number(m.run_queue)} on {number(m.cpu_count)} schedulers",
    ])


def network_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("NETWORK INTERFACES")
    if not m.interfaces:
        return _panel("NETWORK INTERFACES", ["No interfaces reported."])
    lines = [f"{'NAME':<12}{'TYPE':<12}{'STATE':<10}RX / TX"]
    for nic in m.interfaces[:12]:
        lines.append(
            f"{nic.name[:11]:<12}{(nic.kind or _DASH)[:11]:<12}{(nic.state or _DASH)[:9]:<10}"
            f"{size(nic.rx_bytes)} / {size(nic.tx_bytes)}"
        )
    if len(m.interfaces) > 12:
        lines.append(f"… {len(m.interfaces) - 12} more")
    return _panel("NETWORK INTERFACES", lines)


def storage_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("STORAGE")
    if not m.storage:
        return _panel("STORAGE", ["No real filesystems reported."])
    lines = []
    for part in m.storage[:10]:
        lines.append(f"{part.category:<10}{part.mountpoint[:24]:<25}{number(part.used_percent, '%'):>7}  {bar(part.used_percent, 10)}")
        lines.append(f"{'':<10}{size(part.used_bytes)} of {size(part.total_bytes)}")
    if len(m.storage) > 10:
        lines.append(f"… {len(m.storage) - 10} more")
    return _panel("STORAGE", lines)


def temperature_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("TEMPERATURE")
    if not m.temperatures:
        return _panel("TEMPERATURE", ["No sensors reported."])
    hottest = max(m.temperatures, key=lambda reading: reading.celsius)
    lines = [f"Hottest     {hottest.sensor}  {hottest.celsius:.1f} °C"]
    lines.extend(f"{reading.sensor[:28]:<30}{reading.celsius:6.1f} °C" for reading in m.temperatures[:12])
    if len(m.temperatures) > 12:
        lines.append(f"… {len(m.temperatures) - 12} more")
    return _panel("TEMPERATURE", lines)


def sessions_panel(m: HostMetrics | None) -> str:
    if m is None:
        return _empty("SESSIONS")
    if not m.users:
        return _panel("SESSIONS", ["No sessions reported."])
    lines = [f"{'USER':<12}{'TERMINAL':<11}{'FROM':<17}STARTED"]
    for user in m.users[:12]:
        lines.append(f"{user.user[:11]:<12}{(user.terminal or _DASH)[:10]:<11}{(user.host or 'local')[:16]:<17}{user.started or _DASH}")
    return _panel(f"SESSIONS  ·  {len(m.users)}", lines)


def processes_panel(m: HostMetrics | None, limit: int = 10) -> str:
    title = "TOP PROCESSES BY CPU"
    if m is None:
        return _empty(title)
    if not m.processes:
        return _panel(title, ["No process samples reported."])
    total = f"{m.process_total:,} total" if m.process_total is not None else "total —"
    lines = [f"{'PID':>7}  {'USER':<10}{'CPU%':>7}{'MEM%':>7}{'THR':>5}  {'STATE':<8}COMMAND"]
    for proc in m.processes[:limit]:
        name = proc.command or (proc.exe or "").rsplit("/", 1)[-1] or _DASH
        lines.append(
            f"{proc.pid:>7}  {(proc.username or _DASH)[:10]:<10}{number(proc.cpu_pct):>7}"
            f"{number(proc.memory_pct):>7}{number(proc.threads):>5}  {(proc.state or _DASH)[:8]:<8}{name[:30]}"
        )
    return _panel(f"{title}  ·  {total}", lines)

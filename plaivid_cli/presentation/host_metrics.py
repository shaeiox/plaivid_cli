"""Card body builders for the Overview. Each function returns body lines only (the card title is
the widget border title). Missing values render as an em dash, never as zero.
"""

from __future__ import annotations

from plaivid_cli.domain.models import HostMetrics
from plaivid_cli.domain.redaction import redact_text

_DASH = "—"
_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
_NONE = ["No current monitoring values."]


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


def bar(percent: float | None, width: int = 20) -> str:
    if percent is None:
        return _DASH
    ratio = max(0, min(width, round(percent * width / 100)))
    return "█" * ratio + "░" * (width - ratio)


def pct_of(used: int | None, total: int | None) -> float | None:
    if used is None or not total:
        return None
    return 100.0 * used / total


def row(label: str, value: str) -> str:
    return f"{label:<12}: {value}"


def finish(lines: list[str], status: str) -> str:
    """Join body lines with the collection status and apply redaction."""
    return redact_text("\n".join([*lines, status]))


def system_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    return [
        row("Host ID", m.host_id or _DASH),
        row("Platform", f"{m.os_version or _DASH} ({m.platform_family or _DASH})"),
        row("Kernel", m.kernel_version or _DASH),
        row("Virtual", m.virtualization or _DASH),
        row("Boot time", m.boot_time or _DASH),
    ]


def cpu_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    clock = f"{m.cpu_current_hz / 1e9:.2f} GHz" if m.cpu_current_hz else _DASH
    return [
        row("Model", m.cpu_model or _DASH),
        row("Clock", clock),
        row("Cores", f"logical {number(m.logical_cores)} · physical {number(m.physical_cores)} · scheduler {number(m.cpu_count)}"),
        row("Run queue", f"{number(m.run_queue)}  ·  blocked {number(m.blocked_tasks)} ({number(m.blocked_percent, '%')})"),
        row("Context SW", number(m.context_switches)),
        row("Interrupts", f"{number(m.interrupts)}  ·  forks {number(m.forks)}"),
    ]


def memory_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    swap_pct = pct_of(m.swap_used_bytes, m.swap_total_bytes)
    return [
        row("Swap", f"{size(m.swap_used_bytes)} / {size(m.swap_total_bytes)}  {number(swap_pct, '%')}"),
        bar(swap_pct),
    ]


def tasks_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return []
    return [
        row("Tasks", f"total {number(m.total_tasks)}  ·  blocked {number(m.blocked_tasks)}"),
        row("Processes", f"{number(m.num_processes)}  ·  threads {number(m.num_threads)}"),
        row("Open FDs", number(m.open_fds)),
    ]


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


def commands_body(m: HostMetrics | None) -> list[str]:
    if m is None:
        return _NONE
    if not m.command_summary:
        return ["No process samples reported."]
    return [f"● {name[:26]:<27}×{count}" for name, count in m.command_summary]

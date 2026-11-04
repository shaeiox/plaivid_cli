"""Purely presentational Overview formatting; no gateway or filesystem access."""

from __future__ import annotations

from plaivid_cli.application.overview import OverviewHistory, health, sparkline
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, ProcessObservation
from plaivid_cli.domain.overview import DashboardSample, LocalHostSample, NicSample, PhysicalNic
from plaivid_cli.domain.redaction import redact_text


def _value(section):
    return section.value if section and section.value is not None else section.last_good_value if section else None


def _label(section, cadence: float) -> str:
    state = health(section, cadence)
    if state.age is None:
        return state.status
    return f"{state.status} · {state.age:.0f}s ago"


def _bar(value: float | None) -> str:
    if value is None:
        return "N/A"
    ratio = max(0, min(10, round(value / 10)))
    return "━" * ratio + "╺" * (10 - ratio)


def _size(value: int | float | None) -> str:
    if value is None:
        return "N/A"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return "N/A"


def _uptime(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    total = int(seconds)
    weeks, rest = divmod(total, 604800)
    days, rest = divmod(rest, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{weeks}w {days}d {hours}h {minutes}m {secs}s"


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}%"


def cards(snapshot: ApplicationSnapshot, history: OverviewHistory, interval: float) -> dict[str, str]:
    host_section = snapshot.section("local_host")
    host = _value(host_section)
    host = host if isinstance(host, LocalHostSample) else LocalHostSample()
    process_section = snapshot.section("processes")
    process_rows = process_section.value if process_section is not None else None
    running = None
    if (
        process_section is not None
        and process_section.status is CollectionStatus.CURRENT
        and isinstance(process_rows, tuple)
        and process_rows
        and all(isinstance(row, ProcessObservation) for row in process_rows)
        and tuple(row.row_number for row in process_rows) == tuple(range(1, len(process_rows) + 1))
    ):
        # The last validated ROW is the helper's total, even if object inventory
        # has unmatched/partial records. Never infer a count from object states.
        running = process_rows[-1].row_number
        history.last_verified_running = running
    elif process_section is not None and process_section.status is CollectionStatus.STALE:
        running = history.last_verified_running
    memory_pct = 100 * host.memory_used / host.memory_total if host.memory_used is not None and host.memory_total else None
    groups = {
        "running-card": f"Running VMs\n{running if running is not None else 'N/A'}\n{_label(process_section, max(18, interval))}",
        "cpu-card": f"Host CPU\n{_pct(host.cpu_percent)}\n{_bar(host.cpu_percent)}  {_label(host_section, interval)}",
        "memory-card": f"Host memory\n{_size(host.memory_used)} / {_size(host.memory_total)}\n{_bar(memory_pct)}  {_label(host_section, interval)}",
        "load-card": f"System load\n{host.load1 if host.load1 is not None else 'N/A'}\n5m / 15m: {host.load5 if host.load5 is not None else 'N/A'} / {host.load15 if host.load15 is not None else 'N/A'} · {_label(host_section, interval)}",
        "cpu-chart": f"CPU utilization\n{sparkline(history.values['cpu'])}",
        "memory-chart": f"Memory utilization\n{sparkline(history.values['memory'])}",
        "load-chart": f"System load\n{sparkline(history.values['load'])}",
    }
    dashboard_section = snapshot.section("dashboard")
    dashboard = _value(dashboard_section)
    dashboard = dashboard if isinstance(dashboard, DashboardSample) else DashboardSample()
    groups["host-identity"] = (
        f"LOCAL  {host.hostname or 'N/A'}\n"
        f"sballd uptime  {_uptime(host.pvm_uptime_seconds)}\n"
        f"Server uptime  {_uptime(host.uptime_seconds)}"
    )
    return {key: redact_text(value) for key, value in groups.items()}


def nic_details(snapshot: ApplicationSnapshot, selected: str | None) -> tuple[tuple[PhysicalNic, ...], str]:
    discovered = _value(snapshot.section("physical_nics"))
    devices = discovered if isinstance(discovered, tuple) else ()
    devices = tuple(device for device in devices if isinstance(device, PhysicalNic))
    if not devices:
        return (), "No verified physical NICs discovered · N/A (check NIC-list response and permissions)"
    if selected is None or selected not in {device.name for device in devices}:
        selected = devices[0].name
    device = next(device for device in devices if device.name == selected)
    samples = _value(snapshot.section("nic_samples"))
    sample = next((row for row in samples if isinstance(row, NicSample) and row.name == selected), None) if isinstance(samples, tuple) else None
    if sample is None:
        return devices, f"{selected} · counters unavailable · {_label(snapshot.section('nic_samples'), 3)}"
    lines = [
        f"{device.name} · link {sample.state or 'N/A'} · MAC {device.mac or 'N/A'} · IP {device.ip or 'N/A'}",
        f"RX {_size(sample.rx_bytes_per_second)}/s   TX {_size(sample.tx_bytes_per_second)}/s",
        f"Packets RX {sample.rx_packets if sample.rx_packets is not None else 'N/A'} / TX {sample.tx_packets if sample.tx_packets is not None else 'N/A'}",
        f"Errors RX {sample.rx_errors if sample.rx_errors is not None else 'N/A'} / TX {sample.tx_errors if sample.tx_errors is not None else 'N/A'}  ·  CRC {sample.rx_crc_errors if sample.rx_crc_errors is not None else 'N/A'}",
        f"Drops RX {sample.rx_dropped if sample.rx_dropped is not None else 'N/A'} / TX {sample.tx_dropped if sample.tx_dropped is not None else 'N/A'}",
        f"NIC discovery {_label(snapshot.section('physical_nics'), float('inf'))} · Counters {_label(snapshot.section('nic_samples'), 3)}",
    ]
    return devices, redact_text("\n".join(lines))

"""Purely presentational Overview formatting; no gateway or filesystem access."""

from __future__ import annotations

from plaivid_cli.application.overview import OverviewHistory, health, sparkline
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, InventoryData
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


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1f}%"


def cards(snapshot: ApplicationSnapshot, history: OverviewHistory, interval: float) -> dict[str, str]:
    host_section = snapshot.section("local_host")
    host = _value(host_section)
    host = host if isinstance(host, LocalHostSample) else LocalHostSample()
    inventory_section = snapshot.section("inventory")
    inventory = _value(inventory_section)
    running = None
    if (
        isinstance(inventory, InventoryData) and inventory_section is not None
        and inventory_section.status is CollectionStatus.CURRENT
        and not inventory.unmatched_process_rows
        and not any(record.state_disagreed for record in inventory.records)
    ):
        running = sum(record.process_seen and record.state in {"running", "started"} for record in inventory.records)
        history.last_verified_running = running
    elif inventory_section is not None and inventory_section.status is CollectionStatus.STALE:
        running = history.last_verified_running
    memory_pct = 100 * host.memory_used / host.memory_total if host.memory_used is not None and host.memory_total else None
    groups = {
        "running-card": f"◆  RUNNING VMS\n{running if running is not None else 'N/A'}\n{_label(inventory_section, max(18, interval))}",
        "cpu-card": f"◉  HOST CPU\n{_pct(host.cpu_percent)}\n{_bar(host.cpu_percent)}  {_label(host_section, interval)}",
        "memory-card": f"▣  HOST MEMORY\n{_size(host.memory_used)} / {_size(host.memory_total)}\n{_bar(memory_pct)}  {_label(host_section, interval)}",
        "load-card": f"⌁  LOAD AVERAGE\n{host.load1 if host.load1 is not None else 'N/A'}\n5m / 15m: {host.load5 if host.load5 is not None else 'N/A'} / {host.load15 if host.load15 is not None else 'N/A'} · {_label(host_section, interval)}",
        "cpu-chart": f"CPU UTILIZATION\n{sparkline(history.values['cpu'])}",
        "memory-chart": f"MEMORY UTILIZATION\n{sparkline(history.values['memory'])}",
        "load-chart": f"SYSTEM LOAD\n{sparkline(history.values['load'])}",
    }
    required = {
        "Dashboard API": (snapshot.section("dashboard"), max(18, interval)),
        "Local host": (host_section, interval),
        "VM inventory": (inventory_section, max(18, interval)),
        "NIC discovery": (snapshot.section("physical_nics"), float("inf")),
        "NIC counters": (snapshot.section("nic_samples") or snapshot.section("physical_nics"), interval),
    }
    statuses = {key: health(section, cadence) for key, (section, cadence) in required.items()}
    relevant = [entry.status for entry in statuses.values() if entry.status != "N/A"]
    nic_unverified = statuses["NIC discovery"].status == "N/A" or statuses["NIC counters"].status == "N/A"
    overall = "OFFLINE" if "OFFLINE" in relevant else "WARNING" if "WARNING" in relevant or nic_unverified else "LOADING" if "LOADING" in relevant else "ONLINE" if relevant else "N/A"
    successes = [section for section, _ in required.values() if section and section.succeeded_monotonic is not None]
    latest = max(successes, key=lambda section: section.succeeded_monotonic or 0) if successes else None
    latency = f"{latest.latency_seconds * 1000:.0f} ms" if latest and latest.latency_seconds is not None else "N/A"
    lines = [f"{name}: {entry.status} · {entry.age:.0f}s" if entry.age is not None else f"{name}: {entry.status}" for name, entry in statuses.items()]
    groups["heartbeat-card"] = f"♥  HOST HEARTBEAT\n{overall}\nLast {latest.succeeded_at.astimezone().strftime('%H:%M:%S') if latest and latest.succeeded_at else 'N/A'} · {latency}"
    groups["heartbeat-details"] = "COLLECTION HEALTH  ·  " + "  |  ".join(lines) + "  |  VDI: N/A (unverified)"
    dashboard_section = snapshot.section("dashboard")
    dashboard = _value(dashboard_section)
    dashboard = dashboard if isinstance(dashboard, DashboardSample) else DashboardSample()
    groups["vm-monitor"] = (
        "VIRTUAL MACHINES · " + (str(running) if running is not None else "N/A") + " running\n"
        "Count uses object + process evidence; running-state semantics pending PVM review\n"
        "Top CPU / RAM / Network: N/A (response fields/units unverified)\n"
        f"Dashboard API {_label(dashboard_section, max(18, interval))}"
    )
    groups["vdi-monitor"] = "VIRTUAL DISK IMAGES\nN/A · no verified per-VDI inventory or capacity/usage contract"
    groups["host-identity"] = (
        f"LOCAL HOST  {host.hostname or 'N/A'}   ·   PVM HOST  {dashboard.host_name or 'N/A'}"
        f"  /  ID {dashboard.host_id or 'N/A'} · {_label(dashboard_section, max(18, interval))}\n"
        f"PVM reported CPU entries: {len(dashboard.cpu_info) if dashboard.cpu_info else 'N/A'} · "
        f"RAM used / free / total (API raw units): {dashboard.ram_used_raw or 'N/A'} / "
        f"{dashboard.ram_free_raw or 'N/A'} / {dashboard.ram_total_raw or 'N/A'}\n"
        "Local /proc values are identified separately from PVM Dashboard data."
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

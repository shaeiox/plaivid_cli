"""Sball host status and host telemetry XML parsers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter

from plaivid_cli.domain.models import (
    CollectionStatus,
    HostMetrics,
    HostStatus,
    NetworkInterface,
    ProcessSample,
    SourceResult,
    StoragePartition,
    TemperatureReading,
    UserSession,
)

from .common import _average_cpu, _detail_text, _float, _int, _real, _text

ParseResult = SourceResult
_PROCESS_LIMIT = 50
_REAL_FILESYSTEMS = frozenset(
    {"ext2", "ext3", "ext4", "xfs", "btrfs", "vfat", "zfs", "nfs", "nfs4"}
)


def parse_sball_status(root: ET.Element) -> ParseResult[HostStatus | None]:
    node = root.find(".//cluster/node")
    if node is None:
        return ParseResult(
            None,
            CollectionStatus.UNAVAILABLE,
            source="sball/show",
            quality_issues=("node status unavailable",),
        )
    # Real sball/show uses underscores: node/resource_usage/...
    usage = node.find("resource_usage")
    info = usage.find("system_information") if usage is not None else None
    root_fs = usage.find("root") if usage is not None else None
    cpu_pct, cpu_count = _average_cpu(usage)
    total = _int(info.findtext("total_memory")) if info is not None else None
    free = _int(info.findtext("free_memory")) if info is not None else None
    node_id = (node.findtext("id") or "").strip() or None
    if node_id is None and usage is not None:
        node_id = (usage.findtext("node_id") or "").strip() or None
    status = HostStatus(
        name=node.findtext("name"),
        ip=node.findtext("ip"),
        node_id=node_id,
        sball_state=node.findtext("sball-state"),
        node_state=node.findtext("node-state"),
        version=usage.findtext("release_info/version") if usage is not None else None,
        host_time=usage.findtext("host_time/unix_time") if usage is not None else None,
        cpu_pct=cpu_pct,
        cpu_count=cpu_count,
        ram_used_bytes=total - free if total is not None and free is not None else None,
        ram_total_bytes=total,
        load1=_float(info.findtext("load_average_1m")) if info is not None else None,
        load5=_float(info.findtext("load_average_5m")) if info is not None else None,
        load15=_float(info.findtext("load_average_15m")) if info is not None else None,
        storage_total_bytes=_int(root_fs.findtext("total")) if root_fs is not None else None,
        storage_available_bytes=_int(root_fs.findtext("free")) if root_fs is not None else None,
    )
    if usage is None:
        # Never report "current" for a node whose resource block is absent.
        return ParseResult(
            status,
            CollectionStatus.PARTIAL,
            source="sball/show",
            quality_issues=("resource usage unavailable",),
        )
    return ParseResult(status, CollectionStatus.CURRENT, source="sball/show")


def _host_facts(metrics: ET.Element, system: ET.Element | None) -> dict[str, object]:
    """Fields from system_info, load_stats, process_stats, system_stats and the lists."""
    load = metrics.find(".//load_stats")
    procs = metrics.find(".//process_stats")
    sysstats = metrics.find(".//system_stats")
    temperatures = tuple(
        TemperatureReading(sensor=_text(item, "sensor_key") or "sensor", celsius=value)
        for item in metrics.findall(".//temperature_stat")
        if (value := _real(item.findtext("temperature"))) is not None
    )
    users = tuple(
        UserSession(
            user=_text(item, "user") or "?",
            terminal=_text(item, "terminal"),
            host=_text(item, "host"),
            started=_text(item, "started_human"),
        )
        for item in metrics.findall(".//user_stat")
    )
    rows: list[ProcessSample] = []
    for item in metrics.findall(".//process_info_item"):
        pid = _int(item.findtext("pid"))
        if pid is None:
            continue
        # full_command is deliberately never read: it can contain sbell argv and tokens.
        rows.append(
            ProcessSample(
                pid=pid,
                ppid=_int(item.findtext("ppid")),
                username=_text(item, "username"),
                cpu_pct=_float(item.findtext("cpu")),
                memory_pct=_float(item.findtext("memory")),
                threads=_int(item.findtext("threads")),
                state=_text(item, "status_list/item"),
                command=_text(item, "command"),
                exe=_text(item, "exe"),
                started=_text(item, "start_time_human"),
                uptime=_text(item, "uptime_human"),
            )
        )
    commands = Counter((row.command or (row.exe or "").rsplit("/", 1)[-1] or "?") for row in rows)
    rows.sort(key=lambda row: (-(row.cpu_pct or 0.0), row.pid))
    total = _int(procs.findtext("num_processes")) if procs is not None else None
    return {
        "host_id": _text(system, "host_id"),
        "platform_family": _text(system, "platform_family"),
        "kernel_version": _text(system, "kernel_version"),
        "virtualization": " ".join(
            part
            for part in (
                _text(system, "virtualization_system"),
                _text(system, "virtualization_role"),
            )
            if part
        )
        or None,
        "boot_time": _text(system, "boot_time_human"),
        "uptime_seconds": _int(system.findtext("uptime")) if system is not None else None,
        "cpu_count": _int(load.findtext("cpus")) if load is not None else None,
        "run_queue": _int(load.findtext("run_queue")) if load is not None else None,
        "blocked_tasks": _int(load.findtext("blocked")) if load is not None else None,
        "blocked_percent": _float(load.findtext("blocked_percent")) if load is not None else None,
        "total_tasks": _int(load.findtext("total_tasks")) if load is not None else None,
        "num_processes": total,
        "num_threads": _int(procs.findtext("num_threads")) if procs is not None else None,
        "open_fds": _int(procs.findtext("open_fds")) if procs is not None else None,
        "context_switches": _int(sysstats.findtext("context_switches"))
        if sysstats is not None
        else None,
        "interrupts": _int(sysstats.findtext("interrupts")) if sysstats is not None else None,
        "forks": _int(sysstats.findtext("forks")) if sysstats is not None else None,
        "temperatures": temperatures,
        "users": users,
        "processes": tuple(rows[:_PROCESS_LIMIT]),
        "process_total": total if total is not None else (len(rows) or None),
        "command_summary": tuple(commands.most_common(8)),
    }


def parse_metrics(root: ET.Element) -> ParseResult[HostMetrics | None]:
    metrics = root.find(".//metrics")
    if metrics is None:
        return ParseResult(
            None,
            CollectionStatus.UNAVAILABLE,
            source="monitoring/metrics",
            quality_issues=("metrics element unavailable",),
        )
    cpu = metrics.find("cpu_info")
    memory = metrics.find("memory_info/virtual_memory")
    swap = metrics.find("memory_info/swap_memory")
    system = metrics.find("system_info")
    interfaces: list[NetworkInterface] = []
    for item in metrics.findall("network_info/interface_list/interface"):
        kind = item.findtext("iface_type") or ""
        if kind.strip().lower() == "loopback":
            continue
        name = (item.findtext("name") or "").strip()
        if name:
            interfaces.append(
                NetworkInterface(
                    name=name,
                    rx_bytes=_int(item.findtext("bytes_recv")),
                    tx_bytes=_int(item.findtext("bytes_sent")),
                    kind=kind.strip() or None,
                    state=(item.findtext("state") or "").strip() or None,
                )
            )
    storage: list[StoragePartition] = []
    for item in metrics.findall("disk_info/disk_partition_list/disk_partition"):
        filesystem = (item.findtext("fstype") or "").strip().lower()
        total = _int(item.findtext("total_bytes"))
        if filesystem not in _REAL_FILESYSTEMS or total is None or total <= 0:
            continue
        mountpoint = item.findtext("mountpoint") or ""
        category = (
            "DataStore"
            if mountpoint.startswith("/DataStore")
            else "Flash"
            if "VirtualFlash" in mountpoint or "FlashMount" in mountpoint
            else "System"
            if mountpoint in {"/", "/boot"}
            else "Other"
        )
        storage.append(
            StoragePartition(
                mountpoint=mountpoint,
                filesystem=filesystem,
                total_bytes=total,
                used_bytes=_int(item.findtext("used_bytes")),
                used_percent=_float(item.findtext("used_percent")),
                category=category,
            )
        )
    value = HostMetrics(
        cpu_pct=_float(cpu.findtext("cpu_usage/total_usage")) if cpu is not None else None,
        logical_cores=_int(cpu.findtext("logical_cores")) if cpu is not None else None,
        physical_cores=_int(cpu.findtext("physical_cores")) if cpu is not None else None,
        cpu_model=_detail_text(cpu, "model_name"),
        cpu_current_hz=_float(cpu.findtext("cpu_detail_list/cpu_detail/frequency/current_hz"))
        if cpu is not None
        else None,
        memory_used_bytes=_int(memory.findtext("used")) if memory is not None else None,
        memory_total_bytes=_int(memory.findtext("total")) if memory is not None else None,
        swap_used_bytes=_int(swap.findtext("used")) if swap is not None else None,
        swap_total_bytes=_int(swap.findtext("total")) if swap is not None else None,
        hostname=system.findtext("host_name") if system is not None else None,
        uptime=system.findtext("uptime_human") if system is not None else None,
        os_version=(
            " ".join(
                part
                for part in (
                    system.findtext("platform") if system is not None else None,
                    system.findtext("platform_version") if system is not None else None,
                )
                if part
            )
            or None
        ),
        interfaces=tuple(interfaces),
        storage=tuple(sorted(storage, key=lambda item: (item.category, item.mountpoint))),
        **_host_facts(metrics, system),
    )
    return ParseResult(value, CollectionStatus.CURRENT, source="monitoring/metrics")

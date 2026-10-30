"""Pure parsers for the repository's currently consumed PVM response fields.

Fixtures exercise parser behavior only. They are not captured target output.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from plaivid_cli.domain.models import (
    CollectionStatus,
    HostMetrics,
    HostStatus,
    NetworkInterface,
    ObjectVM,
    ProcessObservation,
    SourceResult,
    StoragePartition,
    VMDetail,
    canonical_uuid,
)

ParseResult = SourceResult


_OBJECT_RE = re.compile(r"^\s*\d+\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9a-fA-F-]{36})\s+(.+?)\s*$")
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_REAL_FILESYSTEMS = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "vfat", "zfs", "nfs", "nfs4"})


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except (AttributeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _average_cpu(node: ET.Element) -> tuple[float | None, int | None]:
    values = [_float(cpu.text) for cpu in node.findall("resource-usage/cpus/cpu")]
    valid = [value for value in values if value is not None]
    return (sum(valid) / len(valid), len(values)) if valid else (None, len(values) or None)


def parse_object_inventory(root: ET.Element) -> ParseResult[tuple[ObjectVM, ...]]:
    """Parse defined VM facts and report bad/duplicate UUID records as partial."""
    candidates: list[ObjectVM] = []
    issues: list[str] = []
    counts: Counter[str] = Counter()
    for obj in root.iter("pvm_vmm_obj"):
        raw_uuid = obj.findtext("uuid") or ""
        try:
            uuid = canonical_uuid(raw_uuid)
        except ValueError:
            issues.append("object record with invalid UUID excluded")
            continue
        counts[uuid] += 1
        machine = obj.find("virtual_machine")
        state = (
            machine.findtext("cluster/cluster_status/status")
            if machine is not None
            else None
        ) or "unknown"
        vcpu = _parse_vcpu(machine.find("hardware/cpu")) if machine is not None else None
        mem = _int(machine.findtext("hardware/memory/size")) if machine is not None else None
        port = _int(machine.findtext("hardware/console/port")) if machine is not None else None
        candidates.append(
            ObjectVM(
                uuid=uuid,
                name=obj.findtext("name") or uuid,
                state=state,
                vcpu=vcpu,
                mem_mb=mem,
                description=(obj.findtext("description") or "").strip(),
                configured_port=port,
            )
        )

    duplicates = {uuid for uuid, count in counts.items() if count > 1}
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate object UUID group(s) excluded")
    values = tuple(item for item in candidates if item.uuid not in duplicates)
    status = CollectionStatus.PARTIAL if issues else CollectionStatus.CURRENT
    return ParseResult(values, status, source="user/objects", quality_issues=tuple(issues))


def _parse_vcpu(cpu: ET.Element | None) -> int | None:
    if cpu is None:
        return None
    vcpu = cpu.find("vcpu")
    if vcpu is None:
        return None
    parts = [_int(vcpu.findtext(key)) for key in ("socket", "core", "thread")]
    if any(value is None or value < 1 for value in parts):
        return None
    total = 1
    for part in parts:
        assert part is not None
        total *= part
    return total


def parse_process_rows(raw: str) -> ParseResult[tuple[ProcessObservation, ...]]:
    """Parse recognized pvm-running-vms rows; malformed data is partial."""
    candidates: list[ProcessObservation] = []
    issues: list[str] = []
    for line in _ANSI_RE.sub("", raw).splitlines():
        if not line.strip() or line.lstrip().upper().startswith("ROW "):
            continue
        match = _OBJECT_RE.match(line)
        if match is None:
            issues.append("unrecognized running-process row excluded")
            continue
        pid_text, uptime, port_text, vcpu_text, mem_text, uuid_text, name = match.groups()
        try:
            uuid = canonical_uuid(uuid_text)
            pid, port, vcpu, mem = map(int, (pid_text, port_text, vcpu_text, mem_text))
            observation = ProcessObservation(
                uuid=uuid,
                pid=pid,
                uptime=uptime,
                port=port,
                vcpu=vcpu,
                mem_mb=mem,
                name=name.strip(),
            )
        except (ValueError, TypeError):
            issues.append("invalid running-process row excluded")
            continue
        candidates.append(observation)

    groups: dict[str, list[ProcessObservation]] = defaultdict(list)
    for item in candidates:
        groups[item.uuid].append(item)
    duplicates = {uuid for uuid, group in groups.items() if len(group) > 1}
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate process UUID group(s) excluded")
    values = tuple(item for item in candidates if item.uuid not in duplicates)
    status = CollectionStatus.PARTIAL if issues else CollectionStatus.CURRENT
    return ParseResult(values, status, source="pvm-running-vms", quality_issues=tuple(issues))


def parse_sball_status(root: ET.Element) -> ParseResult[HostStatus | None]:
    node = root.find(".//cluster/node")
    if node is None:
        return ParseResult(None, CollectionStatus.UNAVAILABLE, source="sball/show", quality_issues=("node status unavailable",))
    usage = node.find("resource-usage")
    cpu_pct, cpu_count = _average_cpu(node)
    used = _int(usage.findtext("ram/used")) if usage is not None else None
    total = _int(usage.findtext("ram/total")) if usage is not None else None
    storage_total = storage_available = None
    if usage is not None:
        storage = usage.find("main-storage")
        if storage is not None:
            storage_total = _int(storage.findtext("total_size"))
            storage_available = _int(storage.findtext("available_size"))
    status = HostStatus(
        name=node.findtext("name"),
        ip=node.findtext("ip"),
        sball_state=node.findtext("sball-state"),
        node_state=node.findtext("node-state"),
        version=usage.findtext("release_info/version") if usage is not None else None,
        host_time=usage.findtext("host_time") if usage is not None else None,
        cpu_pct=cpu_pct,
        cpu_count=cpu_count,
        ram_used_bytes=used,
        ram_total_bytes=total,
        load1=_float(usage.findtext("load-average/_1_minute")) if usage is not None else None,
        load5=_float(usage.findtext("load-average/_5_minutes")) if usage is not None else None,
        load15=_float(usage.findtext("load-average/_15_minutes")) if usage is not None else None,
        storage_total_bytes=storage_total,
        storage_available_bytes=storage_available,
    )
    return ParseResult(status, CollectionStatus.CURRENT, source="sball/show")


def parse_metrics(root: ET.Element) -> ParseResult[HostMetrics | None]:
    metrics = root.find(".//metrics")
    if metrics is None:
        return ParseResult(None, CollectionStatus.UNAVAILABLE, source="monitoring/metrics", quality_issues=("metrics element unavailable",))
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
            "DataStore" if mountpoint.startswith("/DataStore")
            else "Flash" if "VirtualFlash" in mountpoint or "FlashMount" in mountpoint
            else "System" if mountpoint in {"/", "/boot"}
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
        memory_used_bytes=_int(memory.findtext("used")) if memory is not None else None,
        memory_total_bytes=_int(memory.findtext("total")) if memory is not None else None,
        swap_used_bytes=_int(swap.findtext("used")) if swap is not None else None,
        swap_total_bytes=_int(swap.findtext("total")) if swap is not None else None,
        hostname=system.findtext("host_name") if system is not None else None,
        uptime=system.findtext("uptime_human") if system is not None else None,
        os_version=(
            " ".join(
                part for part in (
                    system.findtext("platform") if system is not None else None,
                    system.findtext("platform_version") if system is not None else None,
                ) if part
            ) or None
        ),
        interfaces=tuple(interfaces),
        storage=tuple(sorted(storage, key=lambda item: (item.category, item.mountpoint))),
    )
    return ParseResult(value, CollectionStatus.CURRENT, source="monitoring/metrics")


def parse_vm_detail(root: ET.Element, requested_uuid: str) -> ParseResult[VMDetail | None]:
    """Parse an on-demand object detail response for one canonical UUID."""
    from plaivid_cli.domain.models import ConsoleInfo, DiskInfo, NicInfo, VMDetail

    target = canonical_uuid(requested_uuid)
    matches = []
    for obj in root.iter("pvm_vmm_obj"):
        try:
            if canonical_uuid(obj.findtext("uuid") or "") == target:
                matches.append(obj)
        except ValueError:
            continue
    if len(matches) != 1:
        reason = "VM detail UUID is ambiguous" if matches else "VM detail is unavailable"
        return ParseResult(None, CollectionStatus.UNAVAILABLE, source="user/objects/detail", quality_issues=(reason,))

    obj = matches[0]
    machine = obj.find("virtual_machine")
    if machine is None:
        machine = ET.Element("virtual_machine")
    cpu = machine.find("hardware/cpu")
    topology = cpu.find("vcpu") if cpu is not None else None
    parts = [_int(topology.findtext(name)) if topology is not None else None for name in ("socket", "core", "thread")]
    vcpu = None
    if all(part is not None and part > 0 for part in parts):
        vcpu = 1
        for part in parts:
            assert part is not None
            vcpu *= part
    disk_rows = tuple(
        DiskInfo(
            name=item.findtext("name") or "",
            media=item.findtext("media"),
            controller=item.findtext("controller"),
            boot_index=item.findtext("boot_index"),
            cache=item.findtext("cache"),
        )
        for item in machine.findall("hardware/disk_manager/disk_list/disk")
    )
    nic_rows = tuple(
        NicInfo(
            name=item.findtext("name") or "",
            device=item.findtext("device"),
            mac=item.findtext("macaddr"),
            tap_name=item.findtext("tap_name"),
            enabled=item.findtext("enable"),
        )
        for item in machine.findall("hardware/net_adaptor_list/net_adaptor")
    )
    console_element = machine.find("hardware/console")
    console = None
    if console_element is not None:
        console = ConsoleInfo(
            kind=console_element.findtext("type"),
            port=_int(console_element.findtext("port")),
            bind_address=console_element.findtext("bind_address"),
            password_enabled=console_element.findtext("password_enable"),
            tls=console_element.findtext("tls"),
        )
    state = machine.findtext("cluster/cluster_status/status") or "unknown"
    value = VMDetail(
        uuid=target,
        name=obj.findtext("name") or target,
        state=state,
        host=machine.findtext("cluster/host"),
        description=(obj.findtext("description") or "").strip(),
        enabled=obj.findtext("is_enabled"),
        ha=obj.findtext("ha_enabled"),
        created=obj.findtext("created_datetime"),
        modified=obj.findtext("modified_datetime"),
        auto_start=machine.findtext("cluster/auto_start"),
        always_on=machine.findtext("cluster/always_on"),
        qemu_version=machine.findtext("cluster/cluster_status/qemu_version"),
        vcpu=vcpu,
        vcpu_topology="x".join(str(part) if part is not None else "?" for part in parts),
        cpu_model=machine.findtext("hardware/cpu/model"),
        memory_mb=_int(machine.findtext("hardware/memory/size")),
        machine=machine.findtext("hardware/emulated_machine/type"),
        uefi=machine.findtext("hardware/bios/uefi"),
        disks=disk_rows,
        nics=nic_rows,
        console=console,
    )
    return ParseResult(value, CollectionStatus.CURRENT, source="user/objects/detail")


def parse_tap_mapping(root: ET.Element) -> ParseResult[dict[str, str]]:
    """Parse optional tap mapping from the separately requested object query."""
    mapping: dict[str, str] = {}
    for obj in root.iter("pvm_vmm_obj"):
        name = obj.findtext("name") or ""
        for adaptor in obj.iter("net_adaptor"):
            tap = (adaptor.findtext("tap_name") or "").strip()
            if tap:
                mapping[tap] = name
    return ParseResult(mapping, CollectionStatus.CURRENT, source="user/objects/tap-map")

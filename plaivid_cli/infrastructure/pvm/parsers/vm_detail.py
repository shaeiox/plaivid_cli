"""On-demand VM detail and tap mapping XML parsers."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from plaivid_cli.domain.models import (
    CollectionStatus,
    ConsoleInfo,
    DiskInfo,
    NicInfo,
    SourceResult,
    VMDetail,
    canonical_uuid,
)

from .common import _int

ParseResult = SourceResult


def parse_vm_detail(root: ET.Element, requested_uuid: str) -> ParseResult[VMDetail | None]:
    """Parse an on-demand object detail response for one canonical UUID."""
    from plaivid_cli.domain.models import VMDetail

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
        return ParseResult(
            None,
            CollectionStatus.UNAVAILABLE,
            source="user/objects/detail",
            quality_issues=(reason,),
        )

    obj = matches[0]
    machine = obj.find("virtual_machine")
    if machine is None:
        machine = ET.Element("virtual_machine")
    cpu = machine.find("hardware/cpu")
    topology = cpu.find("vcpu") if cpu is not None else None
    parts = [
        _int(topology.findtext(name)) if topology is not None else None
        for name in ("socket", "core", "thread")
    ]
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

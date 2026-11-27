"""Conservative parsers for the proposed dashboard and NIC-list read response.

Only dashboard paths supplied in the integration specification are interpreted.
The NIC-list *command* is documented, but its response schema is not: do not
invent XML fields and present guessed devices as physical network interfaces.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from plaivid_cli.domain.models import CollectionStatus, SourceResult
from plaivid_cli.domain.overview import DashboardSample, PhysicalNic


def parse_dashboard(description: ET.Element) -> SourceResult[DashboardSample]:
    hosts = description.findall(".//host_list/host_dashboard")
    if len(hosts) > 1:
        return SourceResult(
            None, CollectionStatus.UNAVAILABLE, "user/objects/dashboard",
            error="multiple hosts; host identity not established",
        )
    host = hosts[0] if hosts else None
    cpus = (
        tuple((" ".join(cpu.itertext())).strip()[:120] for cpu in host.findall("cpus/cpu"))
        if host is not None else ()
    )
    def field(path: str, limit: int = 64) -> str | None:
        if host is None:
            return None
        value = (host.findtext(path) or "").strip()
        return value[:limit] or None

    sample = DashboardSample(
        host_name=field("name", 128),
        host_id=field("id"),
        cpu_info=cpus[:32],
        ram_free_raw=field("ram/free"),
        ram_used_raw=field("ram/used"),
        ram_total_raw=field("ram/total"),
    )
    return SourceResult(
        sample, CollectionStatus.CURRENT if host is not None else CollectionStatus.PARTIAL,
        "user/objects/dashboard",
    )


def parse_nic_list(description: ET.Element) -> SourceResult[tuple[PhysicalNic, ...]]:
    """Parse ``sbell network nic-list``: one ``<nic>`` per record under ``nic_list``.

    ``<device>`` (e.g. ``eno4``) is the Linux interface name and becomes ``PhysicalNic.name``;
    ``<name>`` (e.g. ``NIC4``) is the PVM identifier. Any record missing either one fails closed.
    """
    lists = description.findall(".//nic_list")
    if not lists:
        return SourceResult(
            None, CollectionStatus.UNSUPPORTED, "network/nic-list",
            error="NIC-list response has no nic_list element; no physical devices inferred",
        )
    devices: list[PhysicalNic] = []
    for record in (nic for nic_list in lists for nic in nic_list.findall("nic")):
        name = _text(record, "name", 64)
        device = _text(record, "device", 32)
        if name is None or device is None:
            return SourceResult(
                None, CollectionStatus.UNAVAILABLE, "network/nic-list",
                error="NIC-list record lacks name or device; no physical devices inferred",
            )
        redundant = record.find("management_redundant")
        redundancy = None
        if redundant is not None:
            enable = _text(redundant, "enable", 8)
            vlan = _text(redundant, "vlanid", 8)
            redundancy = f"enable={enable or 'N/A'} vlan={vlan or 'N/A'}"
        devices.append(PhysicalNic(
            name=device,
            identifier=name,
            mac=_text(record, "mac", 32),
            ip=_text(record, "ip", 64),
            gateway=_text(record, "gateway", 64),
            management=_text(record, "target", 32),
            redundancy=redundancy,
        ))
    return SourceResult(tuple(devices), CollectionStatus.CURRENT, "network/nic-list")


def _text(element: ET.Element, path: str, limit: int) -> str | None:
    value = (element.findtext(path) or "").strip()
    return value[:limit] or None

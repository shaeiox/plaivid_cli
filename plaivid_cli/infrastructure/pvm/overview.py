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
    """Fail closed until a redacted installed-version NIC-list fixture is supplied."""
    return SourceResult(
        None, CollectionStatus.UNSUPPORTED, "network/nic-list",
        error="NIC-list response schema is unverified; no physical devices inferred",
    )

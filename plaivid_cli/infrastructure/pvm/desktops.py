"""Pure parser for the operator-verified Lite Desktop list response."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter

from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.models import CollectionStatus, SourceResult, canonical_uuid
from plaivid_cli.infrastructure.pvm.parsers import _parse_vcpu


def _text(node: ET.Element, path: str) -> str | None:
    value = (node.findtext(path) or "").strip()
    return value or None


def parse_virtual_desktops(description: ET.Element) -> SourceResult[tuple[VirtualDesktop, ...]]:
    """Exclude invalid/duplicate identities; never confuse an absent wrapper with zero rows."""
    objects = description if description.tag == "objects" else description.find(".//objects")
    if objects is None:
        return SourceResult(None, CollectionStatus.UNAVAILABLE, "user/objects/desktops",
                            error="Desktop list wrapper missing")
    candidates: list[VirtualDesktop] = []
    counts: Counter[str] = Counter()
    issues: list[str] = []
    for obj in objects.iter("pvm_desktop_obj"):
        if _text(obj, "type") != "pvm_desktop_lite_virtual_desktop":
            continue
        try:
            uuid = canonical_uuid(_text(obj, "uuid") or "")
        except ValueError:
            issues.append("Desktop record with invalid UUID excluded")
            continue
        counts[uuid] += 1
        machine = obj.find("virtual_machine")
        candidates.append(VirtualDesktop(
            uuid=uuid,
            name=_text(obj, "name") or uuid,
            enabled=_text(obj, "is_enabled"),
            local_status=_text(machine, "local_status") if machine is not None else None,
            cluster_status=_text(machine, "cluster/cluster_status/status") if machine is not None else None,
            os_type=_text(machine, "os/type") if machine is not None else None,
            os_version=_text(machine, "os/version") if machine is not None else None,
            vcpu=_parse_vcpu(machine.find("hardware/cpu")) if machine is not None else None,
            memory_size_raw=_text(machine, "hardware/memory/size") if machine is not None else None,
            parent_id=_text(obj, "parent"),
        ))
    duplicates = {uuid for uuid, count in counts.items() if count > 1}
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate Desktop UUID group(s) excluded")
    return SourceResult(
        tuple(item for item in candidates if item.uuid not in duplicates),
        CollectionStatus.PARTIAL if issues else CollectionStatus.CURRENT,
        "user/objects/desktops", quality_issues=tuple(issues),
    )

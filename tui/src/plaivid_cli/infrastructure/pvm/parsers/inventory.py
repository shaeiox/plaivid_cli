"""VM object and running-process inventory parsers."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from plaivid_cli.domain.models import (
    CollectionStatus,
    ObjectVM,
    ProcessObservation,
    SourceResult,
    canonical_uuid,
)

from .common import _int, _parse_vcpu

ParseResult = SourceResult

_OBJECT_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9a-fA-F-]{36})\s+(.+?)\s*$"
)
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PROCESS_TITLE_RE = re.compile(r"^List of running virtual machines:\s*$", re.IGNORECASE)
_PROCESS_HEADER_RE = re.compile(
    r"^ROW\s+PID\s+UPTIME\s+PORT\s+VCPU\s+MEMORY\s+UUID\s+NAME\s*$", re.IGNORECASE
)
_PROCESS_VCPU_TOTAL_RE = re.compile(r"^Total\s+VCPU\s*:\s*(\d+)(?:\s*\(\d+\))?\s*$", re.IGNORECASE)
_PROCESS_MEMORY_TOTAL_RE = re.compile(
    r"^Total\s+Memory\s*:\s*\d+(?:\s*\(\d+\))?(?:\s*(?:GB|MB))?\s*$", re.IGNORECASE
)


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
            machine.findtext("cluster/cluster_status/status") if machine is not None else None
        ) or "unknown"
        vcpu = _parse_vcpu(machine.find("hardware/cpu")) if machine is not None else None
        mem = _int(machine.findtext("hardware/memory/size")) if machine is not None else None
        port = _int(machine.findtext("hardware/console/port")) if machine is not None else None
        host = machine.findtext("cluster/host") if machine is not None else None
        candidates.append(
            ObjectVM(
                uuid=uuid,
                name=obj.findtext("name") or uuid,
                state=state,
                vcpu=vcpu,
                mem_mb=mem,
                description=(obj.findtext("description") or "").strip(),
                configured_port=port,
                host=host,
            )
        )

    duplicates = {uuid for uuid, count in counts.items() if count > 1}
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate object UUID group(s) excluded")
    values = tuple(item for item in candidates if item.uuid not in duplicates)
    status = CollectionStatus.PARTIAL if issues else CollectionStatus.CURRENT
    return ParseResult(values, status, source="user/objects", quality_issues=tuple(issues))


def parse_process_rows(raw: str) -> ParseResult[tuple[ProcessObservation, ...]]:
    """Parse recognized pvm-running-vms rows; malformed data is partial."""
    candidates: list[ProcessObservation] = []
    row_numbers: list[int] = []
    issues: list[str] = []
    saw_header = False
    vcpu_total: int | None = None
    for line in _ANSI_RE.sub("", raw).splitlines():
        stripped = line.strip()
        if (
            not stripped
            or _PROCESS_TITLE_RE.fullmatch(stripped)
            or _PROCESS_MEMORY_TOTAL_RE.fullmatch(stripped)
        ):
            continue
        if _PROCESS_HEADER_RE.fullmatch(stripped):
            saw_header = True
            continue
        if total := _PROCESS_VCPU_TOTAL_RE.fullmatch(stripped):
            vcpu_total = int(total.group(1))
            continue
        match = _OBJECT_RE.match(line)
        if match is None:
            issues.append("unrecognized running-process row excluded")
            continue
        row_text, pid_text, uptime, port_text, vcpu_text, mem_text, uuid_text, name = match.groups()
        try:
            uuid = canonical_uuid(uuid_text)
            row_number, pid, port, vcpu, mem = map(
                int, (row_text, pid_text, port_text, vcpu_text, mem_text)
            )
            observation = ProcessObservation(
                uuid=uuid,
                pid=pid,
                uptime=uptime,
                port=port,
                vcpu=vcpu,
                mem_mb=mem,
                name=name.strip(),
                row_number=row_number,
            )
        except (ValueError, TypeError):
            issues.append("invalid running-process row excluded")
            continue
        candidates.append(observation)
        row_numbers.append(row_number)

    # Only a complete 1..N listing licenses the last ROW as a total. If the
    # helper reports a VCPU sum, it also detects a missing final row.
    if row_numbers and not saw_header:
        issues.append("running-process header missing")
    if row_numbers and row_numbers != list(range(1, len(row_numbers) + 1)):
        issues.append("running-process ROW numbers are not contiguous from 1")
    if vcpu_total is not None and sum(row.vcpu or 0 for row in candidates) != vcpu_total:
        issues.append("running-process VCPU total does not match rows")

    groups: dict[str, list[ProcessObservation]] = defaultdict(list)
    for item in candidates:
        groups[item.uuid].append(item)
    duplicates = {uuid for uuid, group in groups.items() if len(group) > 1}
    if duplicates:
        issues.append(f"{len(duplicates)} duplicate process UUID group(s) excluded")
    values = tuple(item for item in candidates if item.uuid not in duplicates)
    status = CollectionStatus.PARTIAL if issues else CollectionStatus.CURRENT
    return ParseResult(values, status, source="pvm-running-vms", quality_issues=tuple(issues))

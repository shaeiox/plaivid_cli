"""Read-only CLI command handlers."""

from __future__ import annotations

from plaivid_cli.application.services import PlaividApplication
from plaivid_cli.domain.models import (
    CollectionStatus,
    HostMetrics,
    HostStatus,
    InventoryData,
    PvmSession,
    VMDetail,
)
from plaivid_cli.domain.redaction import redact_text

from .operations import EXIT_OK, EXIT_PARTIAL
from .serialization import _format_bytes, _print_json, _section_payload


def _inventory(
    application: PlaividApplication, session: PvmSession, *, as_json: bool = False
) -> int:
    _, section = application.inventory(session.token)
    value = section.value or section.last_good_value
    inventory = value if isinstance(value, InventoryData) else None
    if as_json:
        _print_json(_section_payload(section, inventory))
        return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL
    if inventory is None:
        print(
            f"VM inventory unavailable · {section.status.value}: {redact_text(section.error or 'no data')}"
        )
        return EXIT_PARTIAL
    print(f"VM inventory · {section.status.value} · generation {section.generation}")
    print(" #  VM name                 UUID                                  OBJECT STATE  PROCESS")
    records = sorted(
        inventory.records,
        key=lambda record: (0 if record.process_seen else 1, record.name.casefold(), record.uuid),
    )
    for index, record in enumerate(records, start=1):
        process = f"observed pid={record.process.pid}" if record.process else "not observed"
        issue = " [state conflict]" if record.state_disagreed else ""
        name = redact_text(record.name)[:22]
        state = redact_text(record.state)
        print(f"{index:2}  {name:22}  {record.uuid}  {state:12}  {process}{issue}")
    for issue in inventory.quality_issues:
        print(f"Quality: {redact_text(issue)}")
    if section.error:
        print(f"Collection note: {redact_text(section.error)}")
    return EXIT_PARTIAL if section.status is not CollectionStatus.CURRENT else EXIT_OK


def _host(application: PlaividApplication, session: PvmSession, *, as_json: bool = False) -> int:
    snapshot = application.refresh(session.token, sections=("host_status", "host_metrics"))
    status_section = snapshot.section("host_status")
    metrics_section = snapshot.section("host_metrics")
    status_value = (
        (status_section.value or status_section.last_good_value) if status_section else None
    )
    metrics_value = (
        (metrics_section.value or metrics_section.last_good_value) if metrics_section else None
    )
    status = status_value if isinstance(status_value, HostStatus) else None
    metrics = metrics_value if isinstance(metrics_value, HostMetrics) else None
    if as_json:
        _print_json(
            {
                "command": "host",
                "sections": {
                    "host_status": _section_payload(status_section, status),
                    "host_metrics": _section_payload(metrics_section, metrics),
                },
            }
        )
        return (
            EXIT_OK
            if all(
                item is not None and item.status is CollectionStatus.CURRENT
                for item in (status_section, metrics_section)
            )
            else EXIT_PARTIAL
        )
    if status is None and metrics is None:
        print("Host status unavailable.")
        return EXIT_PARTIAL
    if status is not None:
        print(
            redact_text(
                f"Host {status.name or '—'} ({status.ip or '—'}) · sball_state={status.sball_state or '—'} "
                f"· node_state={status.node_state or '—'} · version={status.version or '—'}"
            )
        )
        print(
            redact_text(
                f"CPU {status.cpu_pct if status.cpu_pct is not None else '—'}% "
                f"({status.cpu_count if status.cpu_count is not None else '—'} cores) · "
                f"RAM {_format_bytes(status.ram_used_bytes)} / {_format_bytes(status.ram_total_bytes)} · "
                f"storage free {_format_bytes(status.storage_available_bytes)} / "
                f"{_format_bytes(status.storage_total_bytes)}"
            )
        )
    if metrics is not None:
        print(
            redact_text(
                f"Metrics {metrics.hostname or '—'} · CPU {metrics.cpu_pct if metrics.cpu_pct is not None else '—'}% · "
                f"memory {_format_bytes(metrics.memory_used_bytes)} / {_format_bytes(metrics.memory_total_bytes)} · "
                f"interfaces {len(metrics.interfaces)} · mounts {len(metrics.storage)}"
            )
        )
    return (
        EXIT_OK
        if all(
            item is None or item.status is CollectionStatus.CURRENT
            for item in (status_section, metrics_section)
        )
        else EXIT_PARTIAL
    )


def _detail(
    application: PlaividApplication,
    session: PvmSession,
    uuid: str,
    *,
    as_json: bool = False,
) -> int:
    section = application.detail(session.token, uuid)
    detail_value = section.value or section.last_good_value
    detail = detail_value if isinstance(detail_value, VMDetail) else None
    if as_json:
        _print_json(_section_payload(section, detail))
        return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL
    if detail is None:
        print(f"VM detail unavailable · {section.status.value}: {section.error or 'no data'}")
        return EXIT_PARTIAL
    print(redact_text(f"{detail.name} · {detail.uuid} · state={detail.state}"))
    print(
        redact_text(
            f"Host {detail.host or '—'} · vCPU {detail.vcpu if detail.vcpu is not None else '—'} · "
            f"memory {detail.memory_mb if detail.memory_mb is not None else '—'} MB · "
            f"machine {detail.machine or '—'}"
        )
    )
    print(redact_text(f"Description: {detail.description or '—'}"))
    print(
        redact_text(
            f"CPU: {detail.cpu_model or '—'} · topology {detail.vcpu_topology or '—'} · UEFI {detail.uefi or '—'}"
        )
    )
    print(
        redact_text(
            f"Disks: {len(detail.disks)} · NICs: {len(detail.nics)} · console: {detail.console.kind if detail.console else '—'}"
        )
    )
    return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL


def _audit(application: PlaividApplication, limit: int, *, as_json: bool = False) -> int:
    entries = application.recent_audit(limit)
    if as_json:
        _print_json({"command": "audit", "status": "current", "data": entries})
        return EXIT_OK
    print("READ-ONLY local audit · newest first")
    if not entries:
        print("No matching audit rows.")
        return EXIT_OK
    for entry in entries:
        status = "OK" if entry.succeeded else "FAILED"
        print(
            f"{entry.time}  {entry.user}  {entry.user_ip}  {entry.command}  {status}: {entry.result}"
        )
    return EXIT_OK

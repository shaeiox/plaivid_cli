"""Read provider sections and assemble the inventory read model."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast

from plaivid_cli.application.ports import MonitoringGateway, PvmGateway
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.inventory import merge_inventory
from plaivid_cli.domain.models import (
    CollectionStatus,
    SourceResult,
)
from plaivid_cli.domain.overview import PhysicalNic


class SectionReader:
    """Perform provider reads and domain-level source correlation for one request."""

    def __init__(self, provider: PvmGateway, get_section) -> None:
        self._provider = provider
        self._monitor = cast(MonitoringGateway, provider)
        self._get_section = get_section

    def collect(self, token: str, requested: tuple[str, ...]) -> dict[str, SourceResult[object]]:
        results: dict[str, SourceResult[object]] = {}

        needs_objects = "inventory" in requested or "objects" in requested
        needs_processes = "inventory" in requested or "processes" in requested
        if needs_objects:
            results["objects"] = self._read(
                "objects", lambda: self._provider.list_objects(token), "user/objects"
            )
        if needs_processes:
            results["processes"] = self._read(
                "processes", self._provider.list_processes, "pvm-running-vms"
            )
        if "inventory" in requested:
            object_result = results["objects"]
            process_result = results["processes"]
            if object_result.value is not None:
                process_available = process_result.value is not None and process_result.status in {
                    CollectionStatus.CURRENT,
                    CollectionStatus.PARTIAL,
                }
                issues = object_result.quality_issues + process_result.quality_issues
                merged = merge_inventory(
                    object_result.value,  # type: ignore[arg-type]
                    process_result.value if process_available else (),  # type: ignore[arg-type]
                    process_available=process_available,
                    process_complete=process_result.status is CollectionStatus.CURRENT,
                    quality_issues=issues,
                )
                inventory_status = (
                    CollectionStatus.PARTIAL
                    if object_result.status is CollectionStatus.PARTIAL
                    or process_result.status is not CollectionStatus.CURRENT
                    or bool(merged.quality_issues)
                    or any(record.state_disagreed for record in merged.records)
                    else CollectionStatus.CURRENT
                )
                results["inventory"] = SourceResult(
                    value=merged,
                    status=inventory_status,
                    source="user/objects+pvm-running-vms",
                    quality_issues=merged.quality_issues,
                    error=process_result.error,
                    attempted_at=object_result.attempted_at,
                    succeeded_at=process_result.succeeded_at or object_result.succeeded_at,
                    latency_seconds=(object_result.latency_seconds or 0)
                    + (process_result.latency_seconds or 0),
                    attempted_monotonic=object_result.attempted_monotonic,
                    succeeded_monotonic=process_result.succeeded_monotonic
                    or object_result.succeeded_monotonic,
                )
            else:
                results["inventory"] = SourceResult(
                    value=None,
                    status=object_result.status,
                    source="user/objects+pvm-running-vms",
                    error=object_result.error or "object inventory unavailable",
                    quality_issues=object_result.quality_issues + process_result.quality_issues,
                    attempted_at=object_result.attempted_at,
                    latency_seconds=(object_result.latency_seconds or 0)
                    + (process_result.latency_seconds or 0),
                    attempted_monotonic=object_result.attempted_monotonic,
                )
        if "desktops" in requested:
            results["desktops"] = self._read(
                "desktops", lambda: self._provider.list_desktops(token), "user/objects/desktops"
            )
        if "host_status" in requested:
            results["host_status"] = self._read(
                "host_status", lambda: self._provider.host_status(token), "sball/show"
            )
        if "host_metrics" in requested:
            results["host_metrics"] = self._read(
                "host_metrics", lambda: self._provider.host_metrics(token), "monitoring/metrics"
            )
        if "dashboard" in requested:
            results["dashboard"] = self._read(
                "dashboard", lambda: self._monitor.dashboard(token), "user/objects/dashboard"
            )
        if "local_host" in requested:
            results["local_host"] = self._read(
                "local_host", lambda: self._monitor.local_host(), "local /proc"
            )
        if "physical_nics" in requested:
            results["physical_nics"] = self._read(
                "physical_nics", lambda: self._monitor.physical_nics(token), "network/nic-list"
            )
        if "nic_samples" in requested:
            discovered = results.get("physical_nics")
            if discovered is None:
                prior_nics = self._get_section("physical_nics")
                if prior_nics is not None:
                    discovered = SourceResult(
                        prior_nics.value or prior_nics.last_good_value,
                        prior_nics.status,
                        prior_nics.source or "network/nic-list",
                    )
            if discovered is not None and isinstance(discovered.value, tuple):
                devices = tuple(nic for nic in discovered.value if isinstance(nic, PhysicalNic))
                results["nic_samples"] = self._read(
                    "nic_samples", lambda: self._monitor.nic_samples(devices), "local sysfs"
                )
            else:
                results["nic_samples"] = SourceResult(
                    None,
                    CollectionStatus.UNSUPPORTED,
                    "local sysfs",
                    error="physical NIC inventory unavailable",
                )
        if "tap_mapping" in requested:
            results["tap_mapping"] = self._read(
                "tap_mapping", lambda: self._provider.tap_mapping(token), "user/objects/tap-map"
            )
        for section in requested:
            if section.startswith("detail:"):
                from plaivid_cli.domain.models import canonical_uuid

                uuid = canonical_uuid(section.split(":", 1)[1])
                results[section] = self._read(
                    section,
                    lambda uuid=uuid: self._provider.vm_detail(token, uuid),
                    "user/objects/detail",
                )

        return results

    def _read(self, name: str, call, source: str) -> SourceResult[object]:
        started = time.monotonic()
        attempted = datetime.now(UTC)
        try:
            result = call()
            return SourceResult(
                value=result.value,
                status=result.status,
                source=result.source or source,
                error=result.error,
                quality_issues=result.quality_issues,
                attempted_at=attempted,
                succeeded_at=datetime.now(UTC),
                latency_seconds=time.monotonic() - started,
                attempted_monotonic=started,
                succeeded_monotonic=time.monotonic(),
            )
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, AppError)
                else f"{type(exc).__name__} during {name} collection"
            )
            return SourceResult(
                value=None,
                status=CollectionStatus.UNAVAILABLE,
                source=source,
                error=message,
                attempted_at=attempted,
                latency_seconds=time.monotonic() - started,
                attempted_monotonic=started,
            )

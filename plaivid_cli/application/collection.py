"""Single owner for local reads, source freshness, and last-good publication."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import cast

from plaivid_cli.application.ports import MonitoringGateway, PvmGateway
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.inventory import merge_inventory
from plaivid_cli.domain.models import (
    ApplicationSnapshot,
    CollectionStatus,
    SectionSnapshot,
    SourceResult,
)
from plaivid_cli.domain.overview import PhysicalNic

_SECTIONS = {
    "inventory", "objects", "processes", "host_status", "host_metrics", "tap_mapping",
    "dashboard", "local_host", "physical_nics", "nic_samples"
}


class CollectionSuperseded(RuntimeError):
    """A newer bounded pending refresh replaced this obsolete request."""


class CollectionCoordinator:
    """Serializes blocking reads and retains independent last-good sections."""

    def __init__(self, provider: PvmGateway, *, refresh_interval: float = 3.0) -> None:
        if refresh_interval <= 0:
            raise ValueError("refresh_interval must be positive")
        self._provider = provider
        self._monitor = cast(MonitoringGateway, provider)
        self.refresh_interval = refresh_interval
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plaivid-read")
        self._lock = threading.RLock()
        self._sections: dict[str, SectionSnapshot[object]] = {}
        self._generation = 0
        self._mutation_epoch = 0
        self._mutating: set[str] = set()
        self._active: tuple[tuple[object, ...], Future[ApplicationSnapshot]] | None = None
        self._pending: tuple[
            tuple[object, ...], str, tuple[str, ...], Future[ApplicationSnapshot]
        ] | None = None
        self._closed = False

    @property
    def snapshot(self) -> ApplicationSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def request_refresh(
        self, token: str, *, sections: Iterable[str] = ("inventory", "host_status", "host_metrics")
    ) -> Future[ApplicationSnapshot]:
        requested = tuple(dict.fromkeys(sections))
        dynamic = {name for name in requested if name.startswith("detail:")}
        unknown = set(requested) - _SECTIONS - dynamic
        if unknown:
            raise ValueError(f"unsupported collection section: {sorted(unknown)[0]}")
        if dynamic:
            from plaivid_cli.domain.models import canonical_uuid

            for name in dynamic:
                canonical_uuid(name.split(":", 1)[1])
        if not requested:
            raise ValueError("at least one collection section is required")
        token_identity = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        outer: Future[ApplicationSnapshot] = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError("collection coordinator is closed")
            key: tuple[object, ...] = (
                token_identity, self._mutation_epoch, *sorted(requested)
            )
            if self._mutating:
                if self._pending is not None and self._pending[0] == key:
                    return self._pending[3]
                if self._pending is not None and not self._pending[3].done():
                    self._pending[3].set_exception(
                        CollectionSuperseded("refresh superseded by newer view demand")
                    )
                self._pending = (key, token, requested, outer)
                return outer
            if self._active is None:
                self._launch_locked(key, token, requested, outer)
                return outer
            if self._active[0] == key:
                return self._active[1]
            if self._pending is not None and self._pending[0] == key:
                return self._pending[3]
            if self._pending is not None:
                old = self._pending[3]
                if not old.done():
                    old.set_exception(CollectionSuperseded("refresh superseded by newer view demand"))
            self._pending = (key, token, requested, outer)
            return outer

    def collect_once(
        self, token: str, *, sections: Iterable[str] = ("inventory", "host_status", "host_metrics")
    ) -> ApplicationSnapshot:
        """Perform one bounded request through the owned read lane."""
        return self.request_refresh(token, sections=sections).result()

    def begin_mutation(
        self,
        target_uuids: Iterable[str],
        *,
        expected_inventory_generation: int | None = None,
        max_age_seconds: float | None = None,
        require_complete_inventory: bool = False,
    ) -> int:
        """Atomically validate an optional plan generation and erect its barrier."""
        from plaivid_cli.domain.models import canonical_uuid

        targets = {canonical_uuid(uuid) for uuid in target_uuids}
        if not targets:
            raise ValueError("mutation barrier requires at least one target")
        with self._lock:
            if expected_inventory_generation is not None:
                inventory = self._sections.get("inventory")
                objects = self._sections.get("objects")
                if (
                    inventory is None
                    or inventory.generation != expected_inventory_generation
                    or inventory.status not in {CollectionStatus.CURRENT, CollectionStatus.PARTIAL}
                    or (require_complete_inventory and inventory.status is not CollectionStatus.CURRENT)
                    or objects is None
                    or objects.generation != expected_inventory_generation
                    or objects.status is not CollectionStatus.CURRENT
                    or not self._fresh_locked(objects, max_age_seconds)
                    or (
                        require_complete_inventory
                        and not self._fresh_locked(inventory, max_age_seconds)
                    )
                ):
                    raise CollectionSuperseded(
                        "inventory changed or expired immediately before dispatch"
                    )
            self._generation += 1
            self._mutation_epoch += 1
            self._mutating.update(targets)
            if self._pending is not None:
                pending = self._pending[3]
                self._pending = None
                if not pending.done():
                    pending.set_exception(
                        CollectionSuperseded("refresh invalidated by lifecycle mutation")
                    )
            return self._generation

    def end_mutation(self, target_uuids: Iterable[str]) -> ApplicationSnapshot:
        from plaivid_cli.domain.models import canonical_uuid

        targets = {canonical_uuid(uuid) for uuid in target_uuids}
        now, monotonic = datetime.now(UTC), time.monotonic()
        with self._lock:
            self._generation += 1
            self._mutating.difference_update(targets)
            prior = self._sections.get("inventory")
            if prior is not None:
                self._sections["inventory"] = SectionSnapshot(
                    name="inventory",
                    value=None,
                    last_good_value=(prior.last_good_value if prior.last_good_value is not None else prior.value),
                    status=CollectionStatus.STALE,
                    attempted_at=now,
                    succeeded_at=prior.succeeded_at,
                    generation=self._generation,
                    source=prior.source,
                    error="inventory requires post-operation reconciliation",
                    quality_issues=prior.quality_issues,
                    attempted_monotonic=monotonic,
                    succeeded_monotonic=prior.succeeded_monotonic,
                )
            snapshot = self._snapshot_locked()
            if not self._mutating and self._active is None and self._pending is not None:
                pending, self._pending = self._pending, None
                self._launch_locked(*pending)
            return snapshot

    def is_fresh(self, section_name: str, *, max_age_seconds: float | None) -> bool:
        if max_age_seconds is None or max_age_seconds <= 0:
            return False
        with self._lock:
            section = self._sections.get(section_name)
            return self._fresh_locked(section, max_age_seconds)

    @staticmethod
    def _fresh_locked(section: SectionSnapshot[object] | None, max_age_seconds: float | None) -> bool:
        if (
            section is None
            or max_age_seconds is None
            or max_age_seconds <= 0
            or section.status is not CollectionStatus.CURRENT
            or section.succeeded_monotonic is None
        ):
            return False
        return max(0.0, time.monotonic() - section.succeeded_monotonic) <= max_age_seconds

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = self._pending
            self._pending = None
            if pending and not pending[3].done():
                pending[3].set_exception(RuntimeError("application is shutting down"))
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _launch_locked(
        self,
        key: tuple[object, ...],
        token: str,
        requested: tuple[str, ...],
        outer: Future[ApplicationSnapshot],
    ) -> None:
        with self._lock:
            self._generation += 1
            generation = self._generation
            mutation_epoch = self._mutation_epoch
            self._active = (key, outer)
        inner = self._executor.submit(self._collect, token, requested, generation, mutation_epoch)
        inner.add_done_callback(lambda future: self._finish(key, outer, future))

    def _finish(self, key, outer, inner) -> None:
        with self._lock:
            if inner.cancelled():
                if not outer.done():
                    outer.cancel()
            elif inner.exception() is not None:
                if not outer.done():
                    outer.set_exception(inner.exception())
            elif not outer.done():
                outer.set_result(inner.result())
            if self._active is not None and self._active[0] == key:
                self._active = None
            if self._closed:
                pending, self._pending = self._pending, None
                if pending is not None and not pending[3].done():
                    pending[3].set_exception(RuntimeError("application is shutting down"))
            elif not self._mutating and self._pending is not None:
                pending, self._pending = self._pending, None
                self._launch_locked(*pending)

    def _collect(
        self, token: str, requested: tuple[str, ...], generation: int, mutation_epoch: int
    ) -> ApplicationSnapshot:
        started_at = datetime.now(UTC)
        started_mono = time.monotonic()
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
                process_available = (
                    process_result.value is not None
                    and process_result.status in {CollectionStatus.CURRENT, CollectionStatus.PARTIAL}
                )
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
                    latency_seconds=(object_result.latency_seconds or 0) + (process_result.latency_seconds or 0),
                    attempted_monotonic=object_result.attempted_monotonic,
                    succeeded_monotonic=process_result.succeeded_monotonic or object_result.succeeded_monotonic,
                )
            else:
                results["inventory"] = SourceResult(
                    value=None,
                    status=object_result.status,
                    source="user/objects+pvm-running-vms",
                    error=object_result.error or "object inventory unavailable",
                    quality_issues=object_result.quality_issues + process_result.quality_issues,
                    attempted_at=object_result.attempted_at,
                    latency_seconds=(object_result.latency_seconds or 0) + (process_result.latency_seconds or 0),
                    attempted_monotonic=object_result.attempted_monotonic,
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
                with self._lock:
                    prior_nics = self._sections.get("physical_nics")
                if prior_nics is not None:
                    discovered = SourceResult(
                        prior_nics.value or prior_nics.last_good_value,
                        prior_nics.status, prior_nics.source or "network/nic-list",
                    )
            if discovered is not None and isinstance(discovered.value, tuple):
                devices = tuple(nic for nic in discovered.value if isinstance(nic, PhysicalNic))
                results["nic_samples"] = self._read(
                    "nic_samples", lambda: self._monitor.nic_samples(devices), "local sysfs"
                )
            else:
                results["nic_samples"] = SourceResult(
                    None, CollectionStatus.UNSUPPORTED, "local sysfs",
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

        attempted_at = started_at
        attempted_mono = started_mono
        with self._lock:
            if mutation_epoch != self._mutation_epoch:
                return self._snapshot_locked()
            for name, result in results.items():
                prior = self._sections.get(name)
                previous_value = (
                    prior.last_good_value if prior.last_good_value is not None else prior.value
                ) if prior else None
                success = result.value is not None and result.status in {
                    CollectionStatus.CURRENT, CollectionStatus.PARTIAL
                }
                value = result.value if success else None
                last_good = result.value if success else previous_value
                status = result.status
                if not success and previous_value is not None and status is not CollectionStatus.NEVER:
                    status = CollectionStatus.STALE
                result_time = result.succeeded_at or datetime.now(UTC)
                result_mono = result.succeeded_monotonic or time.monotonic()
                succeeded_at = result_time if success else (prior.succeeded_at if prior else None)
                succeeded_mono = result_mono if success else (prior.succeeded_monotonic if prior else None)
                self._sections[name] = SectionSnapshot(
                    name=name,
                    value=value,
                    last_good_value=last_good,
                    status=status,
                    attempted_at=result.attempted_at or attempted_at,
                    succeeded_at=succeeded_at,
                    generation=generation,
                    source=result.source or (prior.source if prior else None),
                    error=result.error,
                    quality_issues=result.quality_issues,
                    attempted_monotonic=result.attempted_monotonic or attempted_mono,
                    succeeded_monotonic=succeeded_mono,
                    latency_seconds=result.latency_seconds if success else (prior.latency_seconds if prior else None),
                )
            return self._snapshot_locked()

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
            message = str(exc) if isinstance(exc, AppError) else f"{type(exc).__name__} during {name} collection"
            return SourceResult(
                value=None,
                status=CollectionStatus.UNAVAILABLE,
                source=source,
                error=message,
                attempted_at=attempted,
                latency_seconds=time.monotonic() - started,
                attempted_monotonic=started,
            )

    def _snapshot_locked(self) -> ApplicationSnapshot:
        return ApplicationSnapshot(
            generation=self._generation,
            created_at=datetime.now(UTC),
            sections=tuple(self._sections[name] for name in sorted(self._sections)),
        )

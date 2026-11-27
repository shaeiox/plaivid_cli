"""Single owner for local reads, source freshness, and last-good publication."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import cast

from plaivid_cli.application.collection.freshness import section_is_fresh
from plaivid_cli.application.collection.publisher import publish_results, stale_after_mutation
from plaivid_cli.application.collection.sections import normalize_sections
from plaivid_cli.application.ports import MonitoringGateway, PvmGateway
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot


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
        self._pending: (
            tuple[tuple[object, ...], str, tuple[str, ...], Future[ApplicationSnapshot]] | None
        ) = None
        self._closed = False
        from plaivid_cli.application.collection.reader import SectionReader

        self._reader = SectionReader(provider, self._get_section)

    @property
    def snapshot(self) -> ApplicationSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def request_refresh(
        self, token: str, *, sections: Iterable[str] = ("inventory", "host_status", "host_metrics")
    ) -> Future[ApplicationSnapshot]:
        requested = normalize_sections(sections)
        token_identity = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        outer: Future[ApplicationSnapshot] = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError("collection coordinator is closed")
            key: tuple[object, ...] = (token_identity, self._mutation_epoch, *sorted(requested))
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
                    old.set_exception(
                        CollectionSuperseded("refresh superseded by newer view demand")
                    )
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
        expected_desktop_generation: int | None = None,
        max_age_seconds: float | None = None,
        require_complete_inventory: bool = False,
    ) -> int:
        """Atomically validate an optional plan generation and erect its barrier."""
        from plaivid_cli.domain.models import canonical_uuid

        targets = {canonical_uuid(uuid) for uuid in target_uuids}
        if not targets:
            raise ValueError("mutation barrier requires at least one target")
        with self._lock:
            if (
                expected_inventory_generation is not None
                and expected_desktop_generation is not None
            ):
                raise ValueError("only one inventory barrier may be selected")
            if expected_desktop_generation is not None:
                from plaivid_cli.domain.desktops import VirtualDesktop

                desktops = self._sections.get("desktops")
                if (
                    desktops is None
                    or desktops.generation != expected_desktop_generation
                    or desktops.status is not CollectionStatus.CURRENT
                    or not isinstance(desktops.value, tuple)
                    or not section_is_fresh(desktops, max_age_seconds)
                    or not targets.issubset(
                        {item.uuid for item in desktops.value if isinstance(item, VirtualDesktop)}
                    )
                ):
                    raise CollectionSuperseded(
                        "Desktop inventory changed or expired before dispatch"
                    )
            if expected_inventory_generation is not None:
                inventory = self._sections.get("inventory")
                objects = self._sections.get("objects")
                if (
                    inventory is None
                    or inventory.generation != expected_inventory_generation
                    or inventory.status not in {CollectionStatus.CURRENT, CollectionStatus.PARTIAL}
                    or (
                        require_complete_inventory
                        and inventory.status is not CollectionStatus.CURRENT
                    )
                    or objects is None
                    or objects.generation != expected_inventory_generation
                    or objects.status is not CollectionStatus.CURRENT
                    or not section_is_fresh(objects, max_age_seconds)
                    or (
                        require_complete_inventory
                        and not section_is_fresh(inventory, max_age_seconds)
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

    def end_mutation(
        self, target_uuids: Iterable[str], *, section_name: str = "inventory"
    ) -> ApplicationSnapshot:
        from plaivid_cli.domain.models import canonical_uuid

        targets = {canonical_uuid(uuid) for uuid in target_uuids}
        if section_name not in {"inventory", "desktops"}:
            raise ValueError("unsupported mutation section")
        now, monotonic = datetime.now(UTC), time.monotonic()
        with self._lock:
            self._generation += 1
            self._mutating.difference_update(targets)
            prior = self._sections.get(section_name)
            if prior is not None:
                self._sections[section_name] = stale_after_mutation(
                    prior,
                    section_name,
                    generation=self._generation,
                    attempted_at=now,
                    attempted_monotonic=monotonic,
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
            return section_is_fresh(section, max_age_seconds)

    def clear_desktop_session(self) -> None:
        """Discard prior operator's Desktop identities and in-flight read publication."""
        with self._lock:
            self._mutation_epoch += 1
            self._sections.pop("desktops", None)
            if self._pending is not None:
                pending = self._pending[3]
                self._pending = None
                if not pending.done():
                    pending.set_exception(CollectionSuperseded("session changed"))

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = self._pending
            self._pending = None
            if pending and not pending[3].done():
                pending[3].set_exception(RuntimeError("application is shutting down"))
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _get_section(self, name: str) -> SectionSnapshot[object] | None:
        with self._lock:
            return self._sections.get(name)

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
        results = self._reader.collect(token, requested)

        with self._lock:
            return publish_results(
                self._sections,
                results,
                generation=generation,
                current_epoch=self._mutation_epoch,
                mutation_epoch=mutation_epoch,
                started_at=started_at,
                started_mono=started_mono,
                snapshot_factory=self._snapshot_locked,
            )

    def _snapshot_locked(self) -> ApplicationSnapshot:
        return ApplicationSnapshot(
            generation=self._generation,
            created_at=datetime.now(UTC),
            sections=tuple(self._sections[name] for name in sorted(self._sections)),
        )

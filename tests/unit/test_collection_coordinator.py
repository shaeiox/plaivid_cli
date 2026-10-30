from __future__ import annotations

import threading

from plaivid_cli.application.collection import CollectionCoordinator, CollectionSuperseded
from plaivid_cli.domain.models import (
    CollectionStatus,
    HostMetrics,
    HostStatus,
    ObjectVM,
    ProcessObservation,
    SourceResult,
)

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"


class FakeProvider:
    def __init__(self) -> None:
        self.object_result = SourceResult(
            (ObjectVM(UUID_A, "vm-a", state="started"),),
            CollectionStatus.CURRENT,
            "user/objects",
        )
        self.process_result = SourceResult(
            (ProcessObservation(UUID_A, pid=10),),
            CollectionStatus.CURRENT,
            "pvm-running-vms",
        )
        self.host_result = SourceResult(HostStatus(name="node-a"), CollectionStatus.CURRENT, "sball/show")
        self.metrics_result = SourceResult(HostMetrics(cpu_pct=20), CollectionStatus.CURRENT, "monitoring/metrics")
        self.block = None
        self.calls: dict[str, int] = {}

    def _count(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1

    def list_objects(self, token):
        self._count("objects")
        if self.block:
            self.block.wait(2)
        if isinstance(self.object_result, Exception):
            raise self.object_result
        return self.object_result

    def list_processes(self):
        self._count("processes")
        if isinstance(self.process_result, Exception):
            raise self.process_result
        return self.process_result

    def host_status(self, token):
        self._count("host")
        if isinstance(self.host_result, Exception):
            raise self.host_result
        return self.host_result

    def host_metrics(self, token):
        self._count("metrics")
        if isinstance(self.metrics_result, Exception):
            raise self.metrics_result
        return self.metrics_result

    def vm_detail(self, token, uuid):
        raise NotImplementedError


def test_object_inventory_survives_failed_process_enrichment() -> None:
    provider = FakeProvider()
    provider.process_result = RuntimeError("helper unavailable")
    coordinator = CollectionCoordinator(provider)
    snapshot = coordinator.collect_once("fake", sections=("inventory",))
    inventory = snapshot.section("inventory")
    objects = snapshot.section("objects")
    processes = snapshot.section("processes")
    assert inventory is not None and inventory.value is not None
    assert inventory.status is CollectionStatus.PARTIAL
    assert objects is not None and objects.status is CollectionStatus.CURRENT
    assert processes is not None and processes.status is CollectionStatus.UNAVAILABLE
    assert len(inventory.value.records) == 1
    coordinator.close()


def test_identical_in_flight_collection_requests_share_one_future() -> None:
    provider = FakeProvider()
    gate = threading.Event()
    provider.block = gate
    coordinator = CollectionCoordinator(provider)
    first = coordinator.request_refresh("fake", sections=("inventory",))
    second = coordinator.request_refresh("fake", sections=("inventory",))
    assert first is second
    gate.set()
    first.result(timeout=2)
    assert provider.calls["objects"] == 1
    coordinator.close()


def test_failed_refresh_retains_last_good_section_as_stale() -> None:
    provider = FakeProvider()
    coordinator = CollectionCoordinator(provider)
    first = coordinator.collect_once("fake", sections=("host_metrics",))
    provider.metrics_result = RuntimeError("synthetic timeout")
    second = coordinator.collect_once("fake", sections=("host_metrics",))
    section = second.section("host_metrics")
    assert section is not None
    assert section.status is CollectionStatus.STALE
    assert section.value is None
    assert section.last_good_value.cpu_pct == 20
    assert section.succeeded_at == first.section("host_metrics").succeeded_at
    coordinator.close()


def test_separate_object_request_does_not_trigger_process_helper() -> None:
    provider = FakeProvider()
    coordinator = CollectionCoordinator(provider)
    snapshot = coordinator.collect_once("fake", sections=("objects",))
    assert snapshot.section("objects").status is CollectionStatus.CURRENT
    assert "processes" not in provider.calls
    coordinator.close()


def test_pre_mutation_read_cannot_publish_after_generation_barrier() -> None:
    provider = FakeProvider()
    gate = threading.Event()
    provider.block = gate
    coordinator = CollectionCoordinator(provider)
    future = coordinator.request_refresh("fake", sections=("inventory",))
    coordinator.begin_mutation((UUID_A,))
    gate.set()
    snapshot = future.result(timeout=2)
    assert snapshot.section("inventory") is None
    after = coordinator.end_mutation((UUID_A,))
    assert after.generation > snapshot.generation
    coordinator.close()


def test_reads_requested_during_mutation_wait_until_reconciliation_barrier_lifts() -> None:
    provider = FakeProvider()
    gate = threading.Event()
    provider.block = gate
    coordinator = CollectionCoordinator(provider)
    coordinator.begin_mutation((UUID_A,))
    future = coordinator.request_refresh("fake", sections=("inventory",))
    assert provider.calls == {}
    coordinator.end_mutation((UUID_A,))
    same = coordinator.request_refresh("fake", sections=("inventory",))
    assert same is future
    gate.set()
    snapshot = future.result(timeout=2)
    assert snapshot.section("inventory") is not None
    assert provider.calls["objects"] == 1
    assert provider.calls["processes"] == 1
    coordinator.close()


def test_atomic_mutation_barrier_rejects_a_superseded_plan_generation() -> None:
    coordinator = CollectionCoordinator(FakeProvider())
    original = coordinator.collect_once("fake", sections=("inventory",))
    old_generation = original.section("inventory").generation
    coordinator.collect_once("fake", sections=("inventory",))
    try:
        coordinator.begin_mutation(
            (UUID_A,),
            expected_inventory_generation=old_generation,
            max_age_seconds=10,
        )
    except CollectionSuperseded:
        pass
    else:
        raise AssertionError("mutation barrier accepted a superseded generation")
    assert coordinator._mutating == set()
    coordinator.close()


def test_snapshot_empty_data_is_not_failure() -> None:
    provider = FakeProvider()
    provider.object_result = SourceResult((), CollectionStatus.CURRENT, "user/objects")
    provider.process_result = SourceResult((), CollectionStatus.CURRENT, "pvm-running-vms")
    coordinator = CollectionCoordinator(provider)
    snapshot = coordinator.collect_once("fake", sections=("inventory",))
    section = snapshot.section("inventory")
    assert section is not None and section.value.records == ()
    assert section.status is CollectionStatus.CURRENT
    coordinator.close()

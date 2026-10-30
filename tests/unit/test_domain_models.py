from __future__ import annotations

from datetime import UTC, datetime

import pytest

from plaivid_cli.domain.inventory import merge_inventory
from plaivid_cli.domain.models import (
    CollectionStatus,
    ObjectVM,
    ProcessObservation,
    SectionSnapshot,
    VMRecord,
    canonical_uuid,
)

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"


def test_uuid_is_canonicalized_and_invalid_uuid_rejected() -> None:
    assert canonical_uuid(UUID_A.upper()) == UUID_A
    with pytest.raises(ValueError, match="UUID"):
        canonical_uuid("not-a-uuid")


def test_process_presence_does_not_overwrite_object_state() -> None:
    obj = ObjectVM(uuid=UUID_A, name="vm-a", state="stopped")
    process = ProcessObservation(uuid=UUID_A, pid=100, uptime="00:01", port=5900)
    record = VMRecord(object=obj, process=process, state_disagreed=True)
    assert record.object.state == "stopped"
    assert record.process is process
    assert record.state_disagreed is True


def test_partial_process_enrichment_does_not_treat_absence_as_state_conflict() -> None:
    object_vm = ObjectVM(uuid=UUID_A, name="vm-a", state="running")
    inventory = merge_inventory(
        (object_vm,),
        (),
        process_available=True,
        process_complete=False,
    )
    assert inventory.records[0].state_disagreed is False


def test_complete_process_source_can_still_report_negative_evidence() -> None:
    object_vm = ObjectVM(uuid=UUID_A, name="vm-a", state="running")
    inventory = merge_inventory(
        (object_vm,),
        (),
        process_available=True,
        process_complete=True,
    )
    assert inventory.records[0].state_disagreed is True


def test_section_status_distinguishes_empty_partial_stale_and_unavailable() -> None:
    now = datetime.now(UTC)
    empty = SectionSnapshot(
        name="inventory", value=(), last_good_value=(), status=CollectionStatus.CURRENT,
        attempted_at=now, succeeded_at=now, generation=1,
    )
    failed = SectionSnapshot(
        name="processes", value=None, last_good_value=("old",), status=CollectionStatus.STALE,
        attempted_at=now, succeeded_at=None, generation=2, error="timeout",
    )
    unavailable = SectionSnapshot(
        name="metrics", value=None, last_good_value=None,
        status=CollectionStatus.UNAVAILABLE, attempted_at=now, succeeded_at=None,
        generation=1, error="permission denied",
    )
    partial = SectionSnapshot(
        name="objects", value=("good",), last_good_value=("good",),
        status=CollectionStatus.PARTIAL, attempted_at=now, succeeded_at=now,
        generation=1, quality_issues=("invalid row",),
    )
    assert empty.value == () and empty.status is CollectionStatus.CURRENT
    assert failed.last_good_value == ("old",) and failed.status is CollectionStatus.STALE
    assert unavailable.last_good_value is None
    assert partial.value == ("good",) and partial.status is CollectionStatus.PARTIAL

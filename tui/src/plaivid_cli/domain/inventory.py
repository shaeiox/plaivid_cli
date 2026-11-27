"""Pure correlation of independent PVM object and process evidence."""

from __future__ import annotations

from collections import defaultdict

from plaivid_cli.domain.models import (
    InventoryData,
    ObjectVM,
    ProcessObservation,
    VMRecord,
)


def merge_inventory(
    objects: tuple[ObjectVM, ...],
    process_rows: tuple[ProcessObservation, ...],
    *,
    process_available: bool,
    process_complete: bool | None = None,
    quality_issues: tuple[str, ...] = (),
) -> InventoryData:
    """Join by UUID without changing either source's facts or inventing VMs."""
    if process_complete is None:
        process_complete = process_available
    object_groups: dict[str, list[ObjectVM]] = defaultdict(list)
    process_groups: dict[str, list[ProcessObservation]] = defaultdict(list)
    for item in objects:
        object_groups[item.uuid].append(item)
    for item in process_rows:
        process_groups[item.uuid].append(item)

    issues = list(quality_issues)
    duplicate_objects = {uuid for uuid, rows in object_groups.items() if len(rows) > 1}
    duplicate_process = {uuid for uuid, rows in process_groups.items() if len(rows) > 1}
    if duplicate_objects:
        issues.append(f"{len(duplicate_objects)} duplicate object UUID group(s) excluded")
    if duplicate_process:
        issues.append(f"{len(duplicate_process)} duplicate process UUID group(s) excluded")

    usable_objects = {
        uuid: rows[0]
        for uuid, rows in object_groups.items()
        if len(rows) == 1 and uuid not in duplicate_objects
    }
    usable_process = {
        uuid: rows[0]
        for uuid, rows in process_groups.items()
        if len(rows) == 1 and uuid not in duplicate_process
    }

    records: list[VMRecord] = []
    for uuid, obj in usable_objects.items():
        process = usable_process.get(uuid)
        disagreed = False
        if process_available:
            # A paused VM keeps its hypervisor process alive, so "paused" is
            # consistent with a process being observed and conflicts with its absence.
            if obj.state in {"stopped", "off"} and process is not None:
                disagreed = True
            elif (
                process_complete
                and obj.state in {"started", "running", "paused"}
                and process is None
            ):
                disagreed = True
        records.append(VMRecord(object=obj, process=process, state_disagreed=disagreed))

    unmatched = tuple(
        row for uuid, row in usable_process.items() if uuid not in usable_objects
    )
    return InventoryData(
        objects=tuple(usable_objects.values()),
        process_rows=tuple(usable_process.values()),
        records=tuple(sorted(records, key=lambda item: (item.name.casefold(), item.uuid))),
        unmatched_process_rows=unmatched,
        quality_issues=tuple(issues),
    )

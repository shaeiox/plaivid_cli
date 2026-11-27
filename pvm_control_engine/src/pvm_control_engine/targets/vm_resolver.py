"""Resolve canonical VM UUID inputs against the current Engine inventory."""

from __future__ import annotations

from collections.abc import Sequence

from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import (
    ErrorKind,
    InventoryData,
    SectionSnapshot,
    VMRecord,
    canonical_uuid,
)


class VMResolver:
    """Validate UUID spelling and bind targets to one current inventory snapshot."""

    def __init__(self, application: PlaividApplication) -> None:
        self._application = application

    def resolve_many(
        self, vm_inputs: Sequence[str], token: str
    ) -> tuple[tuple[VMRecord, ...], SectionSnapshot[object]]:
        if not vm_inputs:
            raise AppError(
                ErrorKind.POLICY, "at least one VM UUID is required", code="INVALID_UUID"
            )
        if len(vm_inputs) > 100:
            raise AppError(
                ErrorKind.POLICY, "operation target limit exceeded", code="INVALID_TARGET_COUNT"
            )
        keys = tuple(self.resolve(value) for value in vm_inputs)
        if len(set(keys)) != len(keys):
            raise AppError(ErrorKind.POLICY, "VM UUIDs must be unique", code="INVALID_UUID")

        _, section = self._application.inventory(token)
        if not isinstance(section.value, InventoryData):
            raise AppError(
                ErrorKind.POLICY, "current VM inventory is required", code="INVENTORY_UNAVAILABLE"
            )
        by_uuid = {record.uuid: record for record in section.value.records}
        if any(key not in by_uuid for key in keys):
            raise AppError(
                ErrorKind.POLICY, "VM is not present in current inventory", code="VM_NOT_FOUND"
            )
        return tuple(by_uuid[key] for key in keys), section

    @staticmethod
    def resolve(vm_input: str) -> str:
        try:
            key = canonical_uuid(vm_input)
        except (ValueError, TypeError) as exc:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            ) from exc
        if key != vm_input:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            )
        return key

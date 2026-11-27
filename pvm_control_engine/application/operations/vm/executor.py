"""Shared, policy-preserving single and bulk VM operation execution."""

from __future__ import annotations

from pvm_control_engine.application.operations import OperationCoordinator
from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import (
    Action,
    ErrorKind,
    InventoryData,
    OperationResult,
    canonical_uuid,
)


class VMOperationExecutor:
    def __init__(self, application: PlaividApplication, operations: OperationCoordinator) -> None:
        self.application = application
        self.operations = operations

    def execute(self, token: str, action: Action, vm_uuids: tuple[str, ...]) -> OperationResult:
        """Validate targets, plan the mutation, and hand it to the operation coordinator."""
        if not vm_uuids:
            raise AppError(
                ErrorKind.POLICY, "at least one VM UUID is required", code="INVALID_UUID"
            )
        canonical_ids = tuple(self._canonical_uuid(value) for value in vm_uuids)
        if len(set(canonical_ids)) != len(canonical_ids):
            raise AppError(ErrorKind.POLICY, "VM UUIDs must be unique", code="INVALID_UUID")
        if len(canonical_ids) > 100:
            raise AppError(
                ErrorKind.POLICY, "operation target limit exceeded", code="INVALID_TARGET_COUNT"
            )

        _, section = self.application.inventory(token)
        if not isinstance(section.value, InventoryData):
            raise AppError(
                ErrorKind.POLICY, "current VM inventory is required", code="INVENTORY_UNAVAILABLE"
            )
        by_uuid = {record.uuid: record for record in section.value.records}
        missing = tuple(key for key in canonical_ids if key not in by_uuid)
        if missing:
            raise AppError(
                ErrorKind.POLICY, "VM is not present in current inventory", code="VM_NOT_FOUND"
            )
        records = tuple(by_uuid[key] for key in canonical_ids)
        is_bulk = len(records) > 1
        plan = self.operations.create_plan(action, records, section, is_bulk=is_bulk)
        return self.operations.execute(token, action, records, section, is_bulk=is_bulk, plan=plan)

    @staticmethod
    def _canonical_uuid(value: str) -> str:
        try:
            canonical = canonical_uuid(value)
        except ValueError as exc:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            ) from exc
        if canonical != value:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            )
        return canonical

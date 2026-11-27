"""Shared, policy-preserving VM operation execution."""

from __future__ import annotations

from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, ErrorKind, InventoryData, canonical_uuid


class VMOperationExecutor:
    def __init__(self, application: PlaividApplication, operations: OperationCoordinator) -> None:
        self.application = application
        self.operations = operations

    def execute(self, token: str, action: Action, vm_uuid: str) -> object:
        try:
            canonical = canonical_uuid(vm_uuid)
        except ValueError as exc:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            ) from exc
        if canonical != vm_uuid:
            raise AppError(
                ErrorKind.POLICY, "VM identifier must be a canonical UUID", code="INVALID_UUID"
            )
        _, section = self.application.inventory(token)
        if not isinstance(section.value, InventoryData):
            raise AppError(
                ErrorKind.POLICY, "current VM inventory is required", code="INVENTORY_UNAVAILABLE"
            )
        record = next((item for item in section.value.records if item.uuid == canonical), None)
        if record is None:
            raise AppError(
                ErrorKind.POLICY, "VM is not present in the current inventory", code="VM_NOT_FOUND"
            )
        plan = self.operations.create_plan(action, (record,), section, is_bulk=False)
        return self.operations.execute(token, action, (record,), section, is_bulk=False, plan=plan)

"""Freshness and completeness admission for VM and Desktop operation plans."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.config import Settings
from plaivid_cli.domain.desktops import VirtualDesktop
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    InventoryData,
    OperationPlan,
    SectionSnapshot,
    VMRecord,
)
from plaivid_cli.domain.policies import bulk_may_dispatch


class OperationPlanner:
    """Build immutable plans against current source truth without dispatching."""

    def __init__(self, collection: CollectionCoordinator, settings: Callable[[], Settings]) -> None:
        self._collection = collection
        self._settings = settings

    def create_plan(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        """Build an immutable, freshness-checked plan without dispatching."""
        return self._build_plan(action, targets, inventory, is_bulk=is_bulk)

    def _build_plan(
        self,
        action: Action,
        targets: tuple[VMRecord, ...],
        inventory: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        settings = self._settings()
        target_ids = tuple(record.uuid for record in targets)
        if not target_ids or len(set(target_ids)) != len(target_ids):
            raise AppError(ErrorKind.POLICY, "operation targets must be non-empty and unique")
        if len(target_ids) > 1 and not is_bulk:
            raise AppError(ErrorKind.POLICY, "multiple targets must be declared as one bulk plan")
        current = self._collection.snapshot.section("inventory")
        if current is None or current.generation != inventory.generation:
            raise AppError(
                ErrorKind.POLICY, "inventory changed after target selection; refresh and retry"
            )
        if not isinstance(inventory.value, InventoryData):
            raise AppError(ErrorKind.POLICY, "operation plan has no current inventory records")
        current_records = {record.uuid: record for record in inventory.value.records}
        if any(current_records.get(record.uuid) != record for record in targets):
            raise AppError(
                ErrorKind.POLICY, "operation targets do not exactly match current inventory records"
            )
        object_section = self._collection.snapshot.section("objects")
        if (
            object_section is None
            or object_section.generation != inventory.generation
            or object_section.status is not CollectionStatus.CURRENT
            or object_section.value is None
            or object_section.succeeded_at is None
        ):
            raise AppError(
                ErrorKind.POLICY, "mutations require a current successful object inventory"
            )
        max_age = settings.max_inventory_age_seconds
        if max_age is None:
            if is_bulk:
                raise AppError(
                    ErrorKind.POLICY,
                    "bulk operations are disabled until PLAIVID_MAX_INVENTORY_AGE_SECONDS is configured",
                )
            max_age = settings.refresh_interval * 2
        if not self._collection.is_fresh("objects", max_age_seconds=max_age):
            raise AppError(
                ErrorKind.POLICY, "object inventory is too old for a mutation; refresh and retry"
            )
        if is_bulk and (
            inventory.status is not CollectionStatus.CURRENT
            or not self._collection.is_fresh("inventory", max_age_seconds=max_age)
        ):
            raise AppError(ErrorKind.POLICY, "bulk mutations require a complete current inventory")
        if any(record.state_disagreed or record.quality_issues for record in targets):
            raise AppError(
                ErrorKind.POLICY, "a selected VM has conflicting or incomplete state evidence"
            )
        if is_bulk:
            complete = (
                inventory.status is CollectionStatus.CURRENT
                and not inventory.quality_issues
                and not any(record.state_disagreed for record in targets)
            )
            if not bulk_may_dispatch(
                action=action,
                is_bulk=True,
                complete=complete,
                fresh=True,
                max_age_seconds=settings.max_inventory_age_seconds,
            ):
                raise AppError(
                    ErrorKind.POLICY, "bulk operation lacks complete fresh inventory evidence"
                )
        return OperationPlan(
            action=action,
            target_uuids=target_ids,
            inventory_generation=inventory.generation,
            inventory_succeeded_at=object_section.succeeded_at,
            is_bulk=is_bulk,
            freshness_limit_seconds=max_age,
            created_at=datetime.now(UTC),
        )

    def create_desktop_plan(
        self,
        action: Action,
        targets: tuple[VirtualDesktop, ...],
        section: SectionSnapshot[object],
        *,
        is_bulk: bool,
    ) -> OperationPlan:
        """Desktop-only admission; never substitute a VMRecord or VM inventory."""
        settings = self._settings()
        ids = tuple(item.uuid for item in targets)
        if not ids or len(set(ids)) != len(ids) or (len(ids) > 1 and not is_bulk):
            raise AppError(
                ErrorKind.POLICY, "Desktop targets must be non-empty, unique and explicitly scoped"
            )
        latest = self._collection.snapshot.section("desktops")
        if (
            latest is None
            or latest != section
            or section.status is not CollectionStatus.CURRENT
            or not isinstance(section.value, tuple)
        ):
            raise AppError(ErrorKind.POLICY, "complete current Desktop inventory required")
        current = {item.uuid: item for item in section.value if isinstance(item, VirtualDesktop)}
        if len(current) != len(section.value) or any(
            current.get(item.uuid) != item for item in targets
        ):
            raise AppError(ErrorKind.POLICY, "Desktop targets do not match the current listing")
        if is_bulk and tuple(sorted(current)) != ids:
            raise AppError(
                ErrorKind.POLICY, "all-target plan must include the full unfiltered Desktop listing"
            )
        age = settings.max_inventory_age_seconds
        if age is None:
            if is_bulk:
                raise AppError(
                    ErrorKind.POLICY, "bulk Desktop actions need PLAIVID_MAX_INVENTORY_AGE_SECONDS"
                )
            age = max(30.0, settings.refresh_interval * 2)
        if not self._collection.is_fresh("desktops", max_age_seconds=age):
            raise AppError(ErrorKind.POLICY, "Desktop listing expired; refresh before operating")
        if section.succeeded_at is None or section.quality_issues:
            raise AppError(ErrorKind.POLICY, "Desktop listing is incomplete")
        return OperationPlan(
            action=action,
            target_uuids=ids,
            inventory_generation=section.generation,
            inventory_succeeded_at=section.succeeded_at,
            is_bulk=is_bulk,
            freshness_limit_seconds=age,
            created_at=datetime.now(UTC),
        )

"""Application-facing read and target-selection use cases."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.application.ports import AuditGateway, PvmGateway
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    ApplicationSnapshot,
    AuditEntry,
    CollectionStatus,
    ErrorKind,
    HostMetrics,
    HostStatus,
    InventoryData,
    SectionSnapshot,
    VMDetail,
    VMRecord,
    canonical_uuid,
)


@dataclass(frozen=True, slots=True)
class TargetSelection:
    records: tuple[VMRecord, ...]
    is_bulk: bool
    selectors: tuple[str, ...]

    @property
    def uuids(self) -> tuple[str, ...]:
        return tuple(record.uuid for record in self.records)


class PlaividApplication:
    """Small facade shared by command-line and Textual presentations."""

    def __init__(
        self,
        provider: PvmGateway,
        collection: CollectionCoordinator,
        settings: Settings,
        audit: AuditGateway | None = None,
    ) -> None:
        self.provider = provider
        self.collection = collection
        self.settings = settings
        self.audit = audit

    def refresh(
        self,
        token: str,
        *,
        sections: Iterable[str] = ("inventory", "host_status", "host_metrics"),
    ) -> ApplicationSnapshot:
        return self.collection.collect_once(token, sections=sections)

    def inventory(self, token: str) -> tuple[ApplicationSnapshot, SectionSnapshot[object]]:
        snapshot = self.refresh(token, sections=("inventory",))
        section = snapshot.section("inventory")
        if section is None:
            raise AppError(ErrorKind.COLLECTION, "inventory collection did not produce a section")
        return snapshot, section

    def detail(self, token: str, uuid: str) -> SectionSnapshot[object]:
        key = canonical_uuid(uuid)
        snapshot = self.refresh(token, sections=(f"detail:{key}",))
        section = snapshot.section(f"detail:{key}")
        if section is None:
            raise AppError(ErrorKind.COLLECTION, "VM detail collection did not produce a section")
        return section

    def host_status(self, token: str) -> SectionSnapshot[object] | None:
        return self.refresh(token, sections=("host_status",)).section("host_status")

    def host_metrics(self, token: str) -> SectionSnapshot[object] | None:
        return self.refresh(token, sections=("host_metrics",)).section("host_metrics")

    def tap_mapping(self, token: str) -> SectionSnapshot[object] | None:
        return self.refresh(token, sections=("tap_mapping",)).section("tap_mapping")

    def recent_audit(self, limit: int = 100) -> tuple[AuditEntry, ...]:
        if self.audit is None:
            raise AppError(ErrorKind.AUDIT, "audit database is not configured")
        return self.audit.recent(limit)

    @staticmethod
    def resolve_targets(inventory: InventoryData, selectors: Iterable[str]) -> TargetSelection:
        raw = tuple(item.strip() for item in selectors if item.strip())
        if not raw:
            raise AppError(ErrorKind.POLICY, "at least one VM selector is required")
        if len(raw) == 1 and raw[0].casefold() == "all":
            targets = tuple(sorted(inventory.records, key=_record_order))
            if not targets:
                raise AppError(ErrorKind.POLICY, "inventory contains no actionable VM records")
            return TargetSelection(targets, True, raw)
        if any(item.casefold() == "all" for item in raw):
            raise AppError(ErrorKind.POLICY, "'all' cannot be combined with other selectors")

        resolved: list[VMRecord] = []
        for selector in raw:
            matches = _resolve_one(inventory.records, selector)
            if not matches:
                raise AppError(ErrorKind.POLICY, f"no VM matches selector {selector!r}")
            if len(matches) > 1 and not _is_group_selector(selector):
                names = ", ".join(record.name for record in matches[:4])
                raise AppError(
                    ErrorKind.POLICY,
                    f"selector {selector!r} is ambiguous; use a UUID or longer prefix ({names})",
                )
            for record in matches:
                if any(existing.uuid == record.uuid for existing in resolved):
                    raise AppError(ErrorKind.POLICY, "the same VM was selected more than once")
                resolved.append(record)
        resolved.sort(key=_record_order)
        bulk = len(raw) > 1 or any(_is_group_selector(item) for item in raw)
        return TargetSelection(tuple(resolved), bulk, raw)

    @staticmethod
    def inventory_value(section: SectionSnapshot[object]) -> InventoryData:
        if section.status not in {CollectionStatus.CURRENT, CollectionStatus.PARTIAL}:
            raise AppError(
                ErrorKind.COLLECTION,
                section.error or f"inventory is {section.status.value.replace('_', ' ')}",
            )
        value = section.value
        if not isinstance(value, InventoryData):
            raise AppError(ErrorKind.COLLECTION, "inventory has no current object records")
        return value


def _record_order(record: VMRecord) -> tuple[int, str, str]:
    return (0 if record.process_seen else 1, record.name.casefold(), record.uuid)


def _is_group_selector(selector: str) -> bool:
    prefix = selector.casefold().split(":", 1)[0]
    return prefix in {"state", "process", "tag"}


def _resolve_one(records: tuple[VMRecord, ...], selector: str) -> list[VMRecord]:
    lowered = selector.casefold()
    if lowered.startswith("state:"):
        state = lowered.partition(":")[2].strip()
        if not state:
            raise AppError(ErrorKind.POLICY, "state selector requires a state")
        accepted = {"started", "running"} if state == "running" else {state}
        return [record for record in records if record.state.casefold() in accepted]
    if lowered.startswith("process:"):
        presence = lowered.partition(":")[2].strip()
        if presence not in {"present", "missing"}:
            raise AppError(ErrorKind.POLICY, "process selector must be process:present or process:missing")
        return [record for record in records if record.process_seen is (presence == "present")]
    if lowered.startswith("tag:"):
        raise AppError(ErrorKind.POLICY, "tag selectors are unsupported by the local object contract")
    if lowered.isdecimal():
        index = int(lowered)
        ordered = sorted(records, key=_record_order)
        return [ordered[index - 1]] if 1 <= index <= len(ordered) else []
    try:
        key = canonical_uuid(selector)
    except ValueError:
        key = ""
    if key:
        return [record for record in records if record.uuid == key]
    exact = [record for record in records if record.name.casefold() == lowered]
    if exact:
        return exact
    return [record for record in records if record.name.casefold().startswith(lowered)]


def as_inventory(section: SectionSnapshot[object]) -> InventoryData:
    """Typed helper used by the presenters without coupling them to storage."""
    value = PlaividApplication.inventory_value(section)
    return value


def as_vm_detail(section: SectionSnapshot[object]) -> VMDetail:
    value = section.value if isinstance(section.value, VMDetail) else section.last_good_value
    if not isinstance(value, VMDetail):
        raise AppError(ErrorKind.COLLECTION, section.error or "VM detail is unavailable")
    return value


def as_host_status(section: SectionSnapshot[object] | None) -> HostStatus | None:
    if section is None:
        return None
    value = section.value if isinstance(section.value, HostStatus) else section.last_good_value
    return value if isinstance(value, HostStatus) else None


def as_host_metrics(section: SectionSnapshot[object] | None) -> HostMetrics | None:
    if section is None:
        return None
    value = section.value if isinstance(section.value, HostMetrics) else section.last_good_value
    return value if isinstance(value, HostMetrics) else None

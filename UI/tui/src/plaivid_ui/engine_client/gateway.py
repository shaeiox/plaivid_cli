"""Presentation-facing adapters that translate allowlisted RPC results into UI DTOs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .client import EngineClient
from .dto import (
    Action,
    ApplicationSnapshot,
    AuditEntry,
    EngineConnection,
    OperationResult,
    SectionSnapshot,
    TargetSelection,
    VMRecord,
    as_audit_entries,
    as_operation_result,
    as_snapshot,
    decode_dataclass,
)


@dataclass(frozen=True, slots=True)
class UISettings:
    default_username: str = "Engine session"
    refresh_interval: int = 3
    host_status_interval: int = 60


class EngineGateway:
    """Small UI-side RPC adapter; all PVM/session work remains in the Engine."""

    def __init__(self, client: EngineClient) -> None:
        self.client = client
        self.settings = UISettings()

    def connect(self) -> EngineConnection:
        self.client.call("engine.health")
        # An authenticated read validates the Engine's pre-established session without
        # exposing the token to this process.
        self.client.call("vm.list")
        return EngineConnection()

    def logout(self, _session: EngineConnection | None = None) -> None:
        self.client.call("session.logout")

    def refresh(self, *, sections: tuple[str, ...]) -> ApplicationSnapshot:
        raw = self.client.call("snapshot.collect", {"sections": list(sections)})
        return as_snapshot(raw)

    def detail(self, uuid: str) -> SectionSnapshot:
        raw = self.client.call("vm.get", {"uuid": uuid})
        return _section_from_wire("detail", raw, fallback_generation=0)

    def recent_audit(self, limit: int = 20) -> tuple[AuditEntry, ...]:
        raw = self.client.call("audit.recent", {"limit": limit})
        if not isinstance(raw, dict):
            raise ValueError("invalid audit response")
        return as_audit_entries(raw.get("entries", []))

    def desktop_list(self) -> SectionSnapshot:
        raw = self.client.call("desktop.list")
        return _section_from_wire("desktops", raw, fallback_generation=0)

    def resolve_targets(self, inventory, selectors: tuple[str, ...]) -> TargetSelection:
        records = tuple(inventory.records)
        wanted = set(selectors)
        selected = records if selectors == ("all",) else tuple(r for r in records if r.uuid in wanted)
        if len(selected) != len(wanted) and selectors != ("all",):
            raise ValueError("one or more selected VMs are no longer in the current inventory")
        return TargetSelection(selected, selectors == ("all",) or len(selected) > 1)

    def create_plan(self, action, records, section, *, is_bulk):
        # Engine-side freshness, allowlisting, UUID validation, and admission are authoritative.
        return (action, tuple(records), section.generation, bool(is_bulk))

    def create_desktop_plan(self, action, targets, section, *, is_bulk):
        return (action, tuple(targets), section.generation, bool(is_bulk))

    def execute(
        self,
        action: Action,
        records: tuple[VMRecord, ...],
        _section,
        *,
        is_bulk: bool,
        plan=None,
        on_progress=None,
    ) -> OperationResult:
        del is_bulk, plan, on_progress
        uuids = [item.uuid for item in records]
        if not uuids:
            raise ValueError("no VM targets selected")
        params: dict[str, Any] = {"action": action.value}
        params["uuid" if len(uuids) == 1 else "uuids"] = uuids[0] if len(uuids) == 1 else uuids
        return as_operation_result(self.client.call("vm.operate", params))

    def execute_desktop(
        self,
        action: Action,
        targets,
        _section,
        *,
        is_bulk: bool,
        plan=None,
        on_progress=None,
    ) -> OperationResult:
        del is_bulk, plan, on_progress
        return as_operation_result(self.client.call("desktop.operate", {
            "action": action.value,
            "uuids": [item.uuid for item in targets],
        }))


def _section_from_wire(name: str, raw: object, *, fallback_generation: int) -> SectionSnapshot:
    if not isinstance(raw, dict) or not isinstance(raw.get("status"), str):
        raise ValueError("invalid section response")
    return decode_dataclass(SectionSnapshot, {
        "name": name,
        "value": raw.get("value"),
        "last_good_value": raw.get("value"),
        "status": raw.get("status"),
        "attempted_at": raw.get("attempted_at"),
        "succeeded_at": raw.get("succeeded_at"),
        "generation": raw.get("generation", fallback_generation),
        "source": raw.get("source"),
        "error": raw.get("error"),
        "quality_issues": raw.get("quality_issues", []),
        "latency_seconds": raw.get("latency_seconds"),
        "succeeded_monotonic": (
            max(0.0, time.monotonic() - raw["age_seconds"])
            if isinstance(raw.get("age_seconds"), (float, int))
            else None
        ),
    })

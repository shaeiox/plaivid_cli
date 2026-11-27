"""Engine-facing allowlisted service for the local JSON-RPC boundary."""

from __future__ import annotations

import math
import time
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import ErrorKind, InventoryData, VMDetail, canonical_uuid
from pvm_control_engine.infrastructure.sbell.commands.registry import CommandRegistry


class EngineService:
    """Authenticate once per request, then delegate only to registered commands."""

    def __init__(
        self,
        *,
        application,
        auth: AuthProvider,
        registry: CommandRegistry,
    ) -> None:
        self.application = application
        self.auth = auth
        self.registry = registry

    def _session(self):
        return self.auth.session()

    def login(self, username: str, password: str) -> dict[str, Any]:
        session, created = self.registry.get("user.login").execute(username, password)
        return {"authenticated": True, "username": session.username, "new_session": created}

    def logout(self) -> dict[str, bool]:
        self.registry.get("user.logout").execute()
        return {"authenticated": False}

    def snapshot(self, sections: tuple[str, ...]) -> dict[str, Any]:
        allowed = {
            "inventory",
            "dashboard",
            "host_status",
            "host_metrics",
            "local_host",
            "physical_nics",
            "nic_samples",
            "tap_mapping",
            "desktops",
        }
        if (
            not sections
            or len(sections) > len(allowed)
            or len(set(sections)) != len(sections)
            or any(item not in allowed for item in sections)
        ):
            raise AppError(
                ErrorKind.POLICY, "unsupported snapshot sections", code="INVALID_SECTIONS"
            )
        session = self._session()
        snapshot = self.application.refresh(session.token, sections=sections)
        return {
            "generation": snapshot.generation,
            "sections": {
                name: _section_payload(
                    section, section.value if section.value is not None else section.last_good_value
                )
                for name in sections
                if (section := snapshot.section(name)) is not None
            },
        }

    def list_vms(self) -> dict[str, Any]:
        section = self.registry.get("user.objects").execute("vm_inventory")
        value = section.value if section.value is not None else section.last_good_value
        if not isinstance(value, InventoryData):
            value = None
        return _section_payload(section, value)

    def vm_detail(self, uuid: str) -> dict[str, Any]:
        key = _canonical_wire_uuid(uuid)
        section = self.registry.get("user.objects").execute("vm_detail", uuid=key)
        value = section.value if section.value is not None else section.last_good_value
        if not isinstance(value, VMDetail):
            value = None
        return _section_payload(section, value)

    def host_status(self) -> dict[str, Any]:
        section = self.registry.get("sball.show").execute()
        return _section_payload(section, section.value if section else None)

    def host_metrics(self) -> dict[str, Any]:
        section = self.registry.get("monitoring.metrics").execute()
        return _section_payload(section, section.value if section else None)

    def desktop_list(self) -> dict[str, Any]:
        section = self.registry.get("user.objects").execute("desktop_list")
        return _section_payload(section, section.value if section else None)

    def dashboard(self) -> dict[str, Any]:
        section = self.registry.get("user.objects").execute("dashboard")
        return _section_payload(section, section.value if section else None)

    def tap_mapping(self) -> dict[str, Any]:
        section = self.registry.get("user.objects").execute("vm_tap_mapping")
        return _section_payload(section, section.value if section else None)

    def nic_list(self) -> dict[str, Any]:
        section = self.registry.get("network.nic_list").execute()
        return _section_payload(section, section.value if section else None)

    def local_host(self) -> dict[str, Any]:
        section = self.registry.get("local.host_metrics").execute()
        return _section_payload(section, section.value if section else None)

    def nic_samples(self) -> dict[str, Any]:
        physical, samples = self.registry.get("local.nic_samples").execute()
        return {
            "physical_nics": _section_payload(physical, physical.value if physical else None),
            "nic_samples": _section_payload(samples, samples.value if samples else None),
        }

    def recent_audit(self, limit: int = 100) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise AppError(
                ErrorKind.POLICY, "audit limit must be between 1 and 500", code="INVALID_LIMIT"
            )
        entries = self.registry.get("local.audit").execute(limit)
        return {"entries": _safe_value(entries), "limit": limit}

    def operate(
        self, action: str, uuid: str | None = None, uuids: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        if (uuid is None) == (uuids is None):
            raise AppError(
                ErrorKind.POLICY, "provide exactly one UUID or UUID list", code="INVALID_UUID"
            )
        command = self.registry.vm_action(action)
        result = command.execute(uuid) if uuid is not None else command.execute_many(uuids or ())
        return _safe_value(result)

    def operate_desktop(self, action: str, uuids: tuple[str, ...]) -> dict[str, Any]:
        result = self.registry.get("desktop.operate").execute(action, uuids)
        return _safe_value(result)


def _canonical_wire_uuid(value: str) -> str:
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


def _section_payload(section, value) -> dict[str, Any]:
    if section is None:
        return {"status": "unavailable", "value": None, "error": "no data returned"}
    return {
        "status": section.status.value,
        "generation": section.generation,
        "source": section.source,
        "attempted_at": _safe_value(section.attempted_at),
        "succeeded_at": _safe_value(section.succeeded_at),
        "age_seconds": (
            max(0.0, time.monotonic() - section.succeeded_monotonic)
            if section.succeeded_monotonic is not None
            else None
        ),
        "latency_seconds": section.latency_seconds,
        "error": section.error,
        "quality_issues": list(section.quality_issues),
        "value": _safe_value(value),
    }


def _safe_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key).casefold() not in {"token", "password", "command", "full_command", "argv"}
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_safe_value(item) for item in value]
    if is_dataclass(value):
        blocked = {"token", "password", "full_command", "argv"}
        if type(value).__name__ != "AuditEntry":
            blocked.add("command")
        return {
            item.name: _safe_value(getattr(value, item.name))
            for item in fields(value)
            if item.name.casefold() not in blocked
        }
    # Unknown object types are never stringified: repr/str may contain XML, argv, or credentials.
    return None

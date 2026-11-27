"""Engine use cases exposed to the local JSON-RPC boundary."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Protocol

from pvm_control_engine.application.session import SessionManager, SessionStore
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import ErrorKind, InventoryData, VMDetail, canonical_uuid


class EngineCommand(Protocol):
    def execute(self, *args: Any, **kwargs: Any) -> Any: ...


class VMOperation(Protocol):
    def execute(self, token: str, vm_uuid: str) -> Any: ...

    def execute_many(self, token: str, vm_uuids: tuple[str, ...]) -> Any: ...


class EngineService:
    """Structured, allowlisted calls over the existing application contracts."""

    def __init__(
        self,
        *,
        application,
        sessions: SessionManager,
        session_store: SessionStore,
        provider,
        operations,
        vm_operations: dict[str, VMOperation],
        commands: dict[str, EngineCommand],
    ) -> None:
        self.application = application
        self.sessions = sessions
        self.session_store = session_store
        self.provider = provider
        self.operations = operations
        self.vm_operations = vm_operations
        self.commands = commands

    def _session(self):
        session = self.session_store.load()
        if session is None:
            raise AppError(ErrorKind.AUTHENTICATION, "login required", code="LOGIN_REQUIRED")
        if not self.commands["user.whoami"].execute(session):
            self.session_store.clear()
            raise AppError(ErrorKind.AUTHENTICATION, "login required", code="LOGIN_REQUIRED")
        return session

    def login(self, username: str, password: str) -> dict[str, Any]:
        session, created = self.commands["user.login"].execute(username, password)
        # Never serialize PvmSession: its token is intentionally not part of the IPC contract.
        return {"authenticated": True, "username": session.username, "new_session": created}

    def logout(self) -> dict[str, bool]:
        session = self.session_store.load()
        if session is not None:
            self.commands["user.logout"].execute(session)
        else:
            self.sessions.clear_local_cache()
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
        session = self._session()
        section = self.commands["user.objects"].execute(session.token, "vm_inventory")
        value = section.value if section.value is not None else section.last_good_value
        if not isinstance(value, InventoryData):
            value = None
        return _section_payload(section, value)

    def vm_detail(self, uuid: str) -> dict[str, Any]:
        key = _canonical_wire_uuid(uuid)
        session = self._session()
        section = self.commands["user.objects"].execute(session.token, "vm_detail", uuid=key)
        value = section.value if section.value is not None else section.last_good_value
        if not isinstance(value, VMDetail):
            value = None
        return _section_payload(section, value)

    def host_status(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["sball.show"].execute(session.token)
        return _section_payload(section, section.value if section else None)

    def host_metrics(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["monitoring.metrics"].execute(session.token)
        return _section_payload(section, section.value if section else None)

    def desktop_list(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["user.objects"].execute(session.token, "desktop_list")
        return _section_payload(section, section.value if section else None)

    def dashboard(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["user.objects"].execute(session.token, "dashboard")
        return _section_payload(section, section.value if section else None)

    def tap_mapping(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["user.objects"].execute(session.token, "vm_tap_mapping")
        return _section_payload(section, section.value if section else None)

    def nic_list(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["network.nic_list"].execute(session.token)
        return _section_payload(section, section.value if section else None)

    def local_host(self) -> dict[str, Any]:
        session = self._session()
        section = self.commands["local.host_metrics"].execute(session.token)
        return _section_payload(section, section.value if section else None)

    def nic_samples(self) -> dict[str, Any]:
        session = self._session()
        snapshot = self.commands["local.nic_samples"].execute(session.token)
        physical = snapshot[0]
        samples = snapshot[1]
        return {
            "physical_nics": _section_payload(physical, physical.value if physical else None),
            "nic_samples": _section_payload(samples, samples.value if samples else None),
        }

    def recent_audit(self, limit: int = 100) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise AppError(
                ErrorKind.POLICY, "audit limit must be between 1 and 500", code="INVALID_LIMIT"
            )
        entries = self.commands["local.audit"].execute(limit)
        return {"entries": _safe_value(entries), "limit": limit}

    def operate(
        self, action: str, uuid: str | None = None, uuids: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        command = self.vm_operations.get(action)
        if command is None:
            raise AppError(ErrorKind.POLICY, "unsupported VM action", code="INVALID_ACTION")
        if (uuid is None) == (uuids is None):
            raise AppError(
                ErrorKind.POLICY, "provide exactly one UUID or UUID list", code="INVALID_UUID"
            )
        keys = (
            (_canonical_wire_uuid(uuid),)
            if uuid is not None
            else tuple(_canonical_wire_uuid(item) for item in uuids or ())
        )
        session = self._session()
        result = (
            command.execute(session.token, keys[0])
            if len(keys) == 1
            else command.execute_many(session.token, keys)
        )
        return _safe_value(result)

    def operate_desktop(self, action: str, uuids: tuple[str, ...]) -> dict[str, Any]:
        from pvm_control_engine.domain.desktops import VirtualDesktop
        from pvm_control_engine.domain.models import Action

        try:
            action_value = Action(action)
        except ValueError as exc:
            raise AppError(
                ErrorKind.POLICY, "unsupported VM action", code="INVALID_ACTION"
            ) from exc
        keys = tuple(_canonical_wire_uuid(item) for item in uuids)
        if not keys or len(set(keys)) != len(keys) or len(keys) > 100:
            raise AppError(
                ErrorKind.POLICY,
                "Desktop UUID list must be non-empty and unique",
                code="INVALID_UUID",
            )
        session = self._session()
        section = self.application.refresh(session.token, sections=("desktops",)).section(
            "desktops"
        )
        if section is None or not isinstance(section.value, tuple):
            raise AppError(
                ErrorKind.POLICY,
                "current Desktop inventory is required",
                code="INVENTORY_UNAVAILABLE",
            )
        by_uuid = {item.uuid: item for item in section.value if isinstance(item, VirtualDesktop)}
        if any(key not in by_uuid for key in keys):
            raise AppError(
                ErrorKind.POLICY,
                "Desktop is not present in current inventory",
                code="DESKTOP_NOT_FOUND",
            )
        targets = tuple(by_uuid[key] for key in keys)
        is_bulk = len(targets) > 1
        plan = self.operations.create_desktop_plan(action_value, targets, section, is_bulk=is_bulk)
        result = self.operations.execute_desktop(
            session.token, action_value, targets, section, is_bulk=is_bulk, plan=plan
        )
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

"""Engine use cases exposed to the local JSON-RPC boundary."""

from __future__ import annotations

import math
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from plaivid_cli.application.session import SessionManager, SessionStore
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import ErrorKind, InventoryData, VMDetail, canonical_uuid


class EngineService:
    """Structured, allowlisted calls over the existing application contracts."""

    def __init__(
        self,
        *,
        application,
        sessions: SessionManager,
        session_store: SessionStore,
        provider,
        commands: dict[str, object],
    ) -> None:
        self.application = application
        self.sessions = sessions
        self.session_store = session_store
        self.provider = provider
        self.commands = commands
        self.vm_operations = {
            key.removeprefix("vm."): value
            for key, value in commands.items()
            if key.startswith("vm.")
        }

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

    def operate(self, action: str, uuid: str) -> dict[str, Any]:
        key = _canonical_wire_uuid(uuid)
        command = self.vm_operations.get(action)
        if command is None:
            raise AppError(ErrorKind.POLICY, "unsupported VM action", code="INVALID_ACTION")
        session = self._session()
        result = command.execute(session.token, key)
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


def _safe_value(value):
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
        return {
            item.name: _safe_value(getattr(value, item.name))
            for item in fields(value)
            if item.name.casefold() not in {"token", "password", "command", "full_command", "argv"}
        }
    return str(value)

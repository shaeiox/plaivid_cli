"""Allowlisted Desktop lifecycle command using the shared mutation safety lane."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.domain.desktops import VirtualDesktop
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import (
    Action,
    ErrorKind,
    OperationResult,
    PvmReply,
    canonical_uuid,
)
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator


class VMDispatchCommand(Protocol):
    def dispatch(self, token: str, vm_uuid: str) -> PvmReply: ...


class DesktopOperate:
    def __init__(
        self,
        auth: AuthProvider,
        application: PlaividApplication,
        operations: VMOperationCoordinator,
        vm_actions: Mapping[Action, VMDispatchCommand],
    ) -> None:
        self._auth = auth
        self._application = application
        self._operations = operations
        self._vm_actions = dict(vm_actions)

    def execute(self, action: str, uuids: tuple[str, ...]) -> OperationResult:
        try:
            fixed_action = Action(action)
        except ValueError as exc:
            raise AppError(
                ErrorKind.POLICY, "unsupported Desktop action", code="INVALID_ACTION"
            ) from exc
        keys = tuple(self._canonical_uuid(value) for value in uuids)
        if not keys or len(set(keys)) != len(keys) or len(keys) > 100:
            raise AppError(
                ErrorKind.POLICY,
                "Desktop UUID list must be non-empty and unique",
                code="INVALID_UUID",
            )

        token = self._auth.token()
        section = self._application.refresh(token, sections=("desktops",)).section("desktops")
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
        plan = self._operations.create_desktop_plan(fixed_action, targets, section, is_bulk=is_bulk)
        vm_command = self._vm_actions[fixed_action]
        return self._operations.execute_desktop(
            token,
            fixed_action,
            targets,
            section,
            is_bulk=is_bulk,
            plan=plan,
            dispatch=vm_command.dispatch,
        )

    @staticmethod
    def _canonical_uuid(value: str) -> str:
        try:
            key = canonical_uuid(value)
        except (ValueError, TypeError) as exc:
            raise AppError(
                ErrorKind.POLICY, "Desktop identifier must be a canonical UUID", code="INVALID_UUID"
            ) from exc
        if key != value:
            raise AppError(
                ErrorKind.POLICY, "Desktop identifier must be a canonical UUID", code="INVALID_UUID"
            )
        return key

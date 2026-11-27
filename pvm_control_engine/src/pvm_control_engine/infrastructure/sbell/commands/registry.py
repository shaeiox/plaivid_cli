"""Explicit registration of Engine commands exposed to the JSON-RPC service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import Action, ErrorKind


class CommandRegistry:
    """Keep command names and VM action classes in one reviewed allowlist."""

    def __init__(
        self,
        commands: Mapping[str, Any],
        vm_actions: Mapping[Action, Any],
    ) -> None:
        if set(vm_actions) != set(Action):
            raise ValueError("registry must contain every supported VM lifecycle action")
        if any(not name or "." not in name for name in commands):
            raise ValueError("command registry keys must be explicit dotted names")
        self._commands = dict(commands)
        self._vm_actions = dict(vm_actions)

    @property
    def commands(self) -> Mapping[str, Any]:
        return self._commands.copy()

    def get(self, name: str) -> Any:
        try:
            return self._commands[name]
        except KeyError as exc:
            raise AppError(
                ErrorKind.POLICY, "unsupported Engine command", code="INVALID_COMMAND"
            ) from exc

    def vm_action(self, action: str) -> Any:
        try:
            fixed_action = Action(action)
        except ValueError as exc:
            raise AppError(
                ErrorKind.POLICY, "unsupported VM action", code="INVALID_ACTION"
            ) from exc
        try:
            return self._vm_actions[fixed_action]
        except KeyError as exc:
            raise AppError(
                ErrorKind.POLICY, "unsupported VM action", code="INVALID_ACTION"
            ) from exc

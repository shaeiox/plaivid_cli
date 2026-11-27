"""Explicit registration of Engine commands exposed to the JSON-RPC service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.application.session_manager import SessionManager
from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import Action, ErrorKind
from pvm_control_engine.infrastructure.audit import ReadOnlyAuditAdapter
from pvm_control_engine.infrastructure.local.audit import LocalAudit
from pvm_control_engine.infrastructure.local.host_metrics import LocalHostMetrics
from pvm_control_engine.infrastructure.local.nic_samples import LocalNicSamples
from pvm_control_engine.infrastructure.pvm.adapter import LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.desktop.operate import DesktopOperate
from pvm_control_engine.infrastructure.sbell.commands.monitoring.metrics import MonitoringMetrics
from pvm_control_engine.infrastructure.sbell.commands.network.nic_list import NetworkNicList
from pvm_control_engine.infrastructure.sbell.commands.sball.show import SballShow
from pvm_control_engine.infrastructure.sbell.commands.user.login import UserLogin
from pvm_control_engine.infrastructure.sbell.commands.user.logout import UserLogout
from pvm_control_engine.infrastructure.sbell.commands.user.objects import UserObjects
from pvm_control_engine.infrastructure.sbell.commands.user.whoami import UserWhoami
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator
from pvm_control_engine.infrastructure.sbell.commands.vm.kill import KillVM
from pvm_control_engine.infrastructure.sbell.commands.vm.pause import PauseVM
from pvm_control_engine.infrastructure.sbell.commands.vm.reset import ResetVM
from pvm_control_engine.infrastructure.sbell.commands.vm.resume import ResumeVM
from pvm_control_engine.infrastructure.sbell.commands.vm.start import StartVM
from pvm_control_engine.infrastructure.sbell.commands.vm.stop import StopVM
from pvm_control_engine.targets.vm_resolver import VMResolver


def build_command_registry(
    provider: LocalPvmAdapter,
    application: PlaividApplication,
    sessions: SessionManager,
    auth: AuthProvider,
    audit: ReadOnlyAuditAdapter,
    operations: VMOperationCoordinator,
    sbell: SbellClient,
    *,
    action_timeout: float,
) -> CommandRegistry:
    """Construct and register only the fixed local sbell commands the Engine exposes."""
    resolver = VMResolver(application)
    vm_actions = {
        Action.START: StartVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
        Action.STOP: StopVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
        Action.KILL: KillVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
        Action.RESET: ResetVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
        Action.PAUSE: PauseVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
        Action.RESUME: ResumeVM(auth, resolver, operations, sbell, action_timeout=action_timeout),
    }
    commands = {
        "user.login": UserLogin(sessions),
        "user.whoami": UserWhoami(provider),
        "user.logout": UserLogout(sessions, auth),
        "user.objects": UserObjects(application, auth),
        "sball.show": SballShow(application, auth),
        "monitoring.metrics": MonitoringMetrics(application, auth),
        "network.nic_list": NetworkNicList(application, auth),
        "local.host_metrics": LocalHostMetrics(application, auth),
        "local.nic_samples": LocalNicSamples(application, auth),
        "local.audit": LocalAudit(audit),
        "desktop.operate": DesktopOperate(auth, application, operations, vm_actions),
    }
    return CommandRegistry(commands, vm_actions)


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

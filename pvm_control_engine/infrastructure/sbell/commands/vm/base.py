"""Small execution base for fixed, action-owned VM sbell commands."""

from __future__ import annotations

from collections.abc import Sequence

from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.domain.models import Action, OperationPlan, OperationResult, PvmReply
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator
from pvm_control_engine.targets.vm_resolver import VMResolver


class VMActionCommand:
    """Common token, target, safety-plan and transport wiring; subclasses own command data."""

    ACTION: Action
    MODULE = "vm"
    COMMAND: str

    def __init__(
        self,
        auth: AuthProvider,
        resolver: VMResolver,
        operations: VMOperationCoordinator,
        sbell: SbellClient,
        *,
        action_timeout: float,
    ) -> None:
        self._auth = auth
        self._resolver = resolver
        self._operations = operations
        self._sbell = sbell
        self._action_timeout = action_timeout

    def execute(self, vm_input: str) -> OperationResult:
        return self._execute((vm_input,))

    def execute_many(self, vm_inputs: tuple[str, ...]) -> OperationResult:
        return self._execute(vm_inputs)

    def _execute(self, vm_inputs: Sequence[str]) -> OperationResult:
        token = self._auth.token()
        records, section = self._resolver.resolve_many(vm_inputs, token)
        is_bulk = len(records) > 1
        plan: OperationPlan = self._operations.create_plan(
            self.ACTION, records, section, is_bulk=is_bulk
        )
        return self._operations.execute(
            token,
            self.ACTION,
            records,
            section,
            is_bulk=is_bulk,
            plan=plan,
            dispatch=self.dispatch,
        )

    def dispatch(self, token: str, vm_uuid: str) -> PvmReply:
        """Execute this class's fixed sbell request; never accepts a command name."""
        response = self._sbell.call(
            self.MODULE,
            self.COMMAND,
            self.build_params(vm_uuid),
            token,
            timeout=self._action_timeout,
        )
        return response.reply()

    def build_params(self, vm_uuid: str) -> str:
        raise NotImplementedError

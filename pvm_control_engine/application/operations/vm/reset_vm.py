"""Reset-VM use case."""

from pvm_control_engine.domain.models import Action

from .common import VMOperationExecutor


class ResetVM:
    def __init__(self, executor: VMOperationExecutor) -> None:
        self.executor = executor

    def execute(self, token: str, vm_uuid: str):
        return self.executor.execute(token, Action.RESET, vm_uuid)

    def execute_many(self, token: str, vm_uuids: tuple[str, ...]):
        return self.executor.execute_many(token, Action.RESET, vm_uuids)

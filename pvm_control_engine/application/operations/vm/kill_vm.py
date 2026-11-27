"""Kill-VM use case."""

from pvm_control_engine.domain.models import Action

from .common import VMOperationExecutor


class KillVM:
    def __init__(self, executor: VMOperationExecutor) -> None:
        self.executor = executor

    def execute(self, token: str, vm_uuid: str):
        return self.executor.execute(token, Action.KILL, vm_uuid)

    def execute_many(self, token: str, vm_uuids: tuple[str, ...]):
        return self.executor.execute_many(token, Action.KILL, vm_uuids)

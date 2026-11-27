"""Kill-VM use case."""

from plaivid_cli.domain.models import Action

from .common import VMOperationExecutor


class KillVM:
    def __init__(self, executor: VMOperationExecutor) -> None:
        self.executor = executor

    def execute(self, token: str, vm_uuid: str):
        return self.executor.execute(token, Action.KILL, vm_uuid)

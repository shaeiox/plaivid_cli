"""Pause-VM use case."""

from plaivid_cli.domain.models import Action

from .common import VMOperationExecutor


class PauseVM:
    def __init__(self, executor: VMOperationExecutor) -> None:
        self.executor = executor

    def execute(self, token: str, vm_uuid: str):
        return self.executor.execute(token, Action.PAUSE, vm_uuid)

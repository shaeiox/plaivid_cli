"""Resume-VM use case."""

from pvm_control_engine.domain.models import Action, OperationResult

from .executor import VMOperationExecutor


class ResumeVM:
    """Run a resume action through shared VM validation and operation policy."""

    def __init__(self, executor: VMOperationExecutor) -> None:
        self.executor = executor

    def execute(self, token: str, vm_uuid: str) -> OperationResult:
        return self.executor.execute(token, Action.RESUME, (vm_uuid,))

    def execute_many(self, token: str, vm_uuids: tuple[str, ...]) -> OperationResult:
        return self.executor.execute(token, Action.RESUME, vm_uuids)

# Human-readable documentation for `common.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/vm/common.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Bounded-parallel lifecycle dispatch with inventory and outcome safeguards.

## 2. Functional summary

Bounded-parallel lifecycle dispatch with inventory and outcome safeguards.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `VMOperationCoordinator.create_plan(self, action: Action, targets: tuple[VMRecord, ...], inventory: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

Calls `self._planner.create_plan`. Explicit return value(s): `self._planner.create_plan(action, targets, inventory, is_bulk=is_bulk)`.

### `VMOperationCoordinator.create_desktop_plan(self, action: Action, targets: tuple[VirtualDesktop, ...], section: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

Calls `self._planner.create_desktop_plan`. Explicit return value(s): `self._planner.create_desktop_plan(action, targets, section, is_bulk=is_bulk)`.

### `VMOperationCoordinator.__init__(self, provider: PvmGateway, collection: CollectionCoordinator, settings: Settings) -> None`

Calls `OperationPlanner`, `threading.Lock`, `threading.Event`, `DesktopOperationExecutor`. Reads or updates `self._provider`, `self._collection`, `self._settings`, `self._planner`, `self._lane`, `self._closing`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `VMOperationCoordinator.close(self) -> None`

Stop new operation admission and wait for active dispatch/reconciliation.

### `VMOperationCoordinator.execute_desktop(self, token: str, action: Action, targets: tuple[VirtualDesktop, ...], section: SectionSnapshot[object], *, is_bulk: bool, plan: OperationPlan, dispatch: Dispatch, on_progress: ProgressSink | None=None) -> OperationResult`

Calls `self._desktop_executor.execute`. Explicit return value(s): `self._desktop_executor.execute(token, action, targets, section, is_bulk=is_bulk, plan=plan, dispatch`.

### `VMOperationCoordinator.cancel(plan: OperationPlan) -> OperationResult`

Record an explicit cancellation before any target was dispatched.

### `VMOperationCoordinator.execute(self, token: str, action: Action, targets: tuple[VMRecord, ...], inventory: SectionSnapshot[object], *, is_bulk: bool, plan: OperationPlan | None=None, dispatch: Dispatch, on_progress: ProgressSink | None=None) -> OperationResult`

Calls `self._closing.is_set`, `AppError`, `self._execute_locked`. Explicit return value(s): `self._execute_locked(token, action, targets, inventory, is_bulk=is_bulk, plan=plan, dispatch=dispatc`. Can raise `AppError(ErrorKind.POLICY, 'operation coordinator is shutting down')`.

### `VMOperationCoordinator._execute_locked(self, token: str, action: Action, targets: tuple[VMRecord, ...], inventory: SectionSnapshot[object], *, is_bulk: bool, plan: OperationPlan | None, dispatch: Dispatch, on_progress: ProgressSink | None=None) -> OperationResult`

Calls `self.create_plan`, `datetime.now`, `str`, `aggregate_state`, `OperationResult`. Reads or updates `current_plan`, `plan`, `target_ids`, `started`, `operation_id`, `stop_reason`. Explicit return value(s): `OperationResult(operation_id=operation_id, action=action, state=aggregate, targets=tuple(outcomes), `. Can raise `AppError(ErrorKind.POLICY, 'operation plan is stale or does not match current targets')`, `AppError(ErrorKind.POLICY, 'inventory changed or expired immediately before dispatch; review a new p`.

### `VMOperationCoordinator._check_daemon_alive(self, token: str, timeout: float=2.0) -> bool`

Calls `getattr`, `bool`, `probe`. Reads or updates `probe`. Explicit return value(s): `True`, `bool(probe(timeout=timeout, token=token))`, `False`, `bool(probe(timeout))`.

### `VMOperationCoordinator._dispatch_one(self, token: str, action: Action, record: VMRecord | VirtualDesktop, *, dispatch: Dispatch, on_progress: ProgressSink | None=None) -> TargetOutcome`

Calls `report_progress`, `self._dispatch_outcome`, `self._check_daemon_alive`, `logger.error`, `TargetOutcome`. Reads or updates `outcome`, `daemon_alive`, `timeout_s`, `detail`. Explicit return value(s): `outcome`.

### `VMOperationCoordinator._dispatch_outcome(self, token: str, action: Action, record: VMRecord | VirtualDesktop, dispatch: Dispatch) -> TargetOutcome`

Calls `TargetOutcome`, `dispatch`, `redact_text`, `str`, `type`. Reads or updates `reply`, `code`, `detail`. Explicit return value(s): `TargetOutcome(record.uuid, OperationState.OUTCOME_UNKNOWN, 'unexpected PVM status; reconcile indepen`, `TargetOutcome(record.uuid, OperationState.SUCCEEDED, f'PVM accepted vm/{action.value}', dispatched=T`, `TargetOutcome(record.uuid, OperationState.FAILED, redact_text(f'PVM reported failure{code}: {detail}`, `TargetOutcome(record.uuid, OperationState.OUTCOME_UNKNOWN, str(exc), dispatched=True, errno=exc.errn`.

## 6. Classes and data structures

### `VMOperationCoordinator`

- **Bases:** no explicit base class.
- **Description:** Own operation admission, mutation barriers, and bounded batch accounting.
- **Methods:** `create_plan`, `create_desktop_plan`, `__init__`, `close`, `execute_desktop`, `cancel`, `execute`, `_execute_locked`, `_check_daemon_alive`, `_dispatch_one`, `_dispatch_outcome`.

### Module-level values

- `Dispatch` = `Callable[[str, str], PvmReply]`
- `logger` = `logging.getLogger('plaivid')`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `self._closing.is_set()`
- `plan is not None and (plan.action is not current_plan.action or plan.target_uuids != current_plan.target_uuids or plan.inventory_generation != current_plan.inventory_generation or (plan.inventory_succeeded_at != current_plan.inventory_succe`
- `stop_reason != DAEMON_OFFLINE_REASON`
- `probe is None`
- `outcome.code == COMMAND_TIMEOUT_CODE or outcome.state in {OperationState.FAILED, OperationState.OUTCOME_UNKNOWN}`
- `reply.status == 'success'`
- `reply.status == 'failed'`
- `self._closing.is_set()`
- `any((outcome.code == 'DAEMON_OFFLINE' for outcome in outcomes))` (with an `else` branch)
- `not daemon_alive` (with an `else` branch)
- `outcome.code == COMMAND_TIMEOUT_CODE`
- `exc.kind is ErrorKind.POLICY`
- `exc.code == 'PROCESS_START_FAILED'`
- `reply.errno` (with an `else` branch)
- `outcome.code == COMMAND_TIMEOUT_CODE` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `target_uuid in plan.target_uuids (comprehension)`
- `outcome in outcomes (comprehension)`
- `outcome in outcomes (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 198) handles: CollectionSuperseded.
- `try` block (line 211) handles: no typed handler.
- `try` block (line 264) handles: TypeError, Exception.
- `try` block (line 327) handles: AppError, Exception.
- `try` block (line 245) handles: Exception.
- `try` block (line 267) handles: Exception.

Explicitly raised exception expressions: `AppError(ErrorKind.POLICY, 'operation coordinator is shutting down')`, `AppError(ErrorKind.POLICY, 'operation plan is stale or does not match current targets')`, `AppError(ErrorKind.POLICY, 'inventory changed or expired immediately before dispatch; review a new p`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.collection`, `pvm_control_engine.application.ports`, `pvm_control_engine.config`, `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.policies`, `pvm_control_engine.domain.redaction`, `pvm_control_engine.infrastructure.sbell.commands.desktop.common`, `.bulk`, `.planner`, `.results`.
- **Standard-library/third-party imports:** `__future__`, `logging`, `threading`, `uuid`, `collections.abc`, `datetime`.

Related module documentation:

- [`pvm_control_engine.application.collection`](../../../../application/collection/__init__.md)
- [`pvm_control_engine.application.ports`](../../../../application/ports.md)
- [`pvm_control_engine.config`](../../../../config.md)
- [`pvm_control_engine.domain.desktops`](../../../../domain/desktops.md)
- [`pvm_control_engine.domain.errors`](../../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.domain.policies`](../../../../domain/policies.md)
- [`pvm_control_engine.domain.redaction`](../../../../domain/redaction.md)
- [`pvm_control_engine.infrastructure.sbell.commands.desktop.common`](../desktop/common.md)

## 11. Real-world scenario

Bounded-parallel lifecycle dispatch with inventory and outcome safeguards.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`common.py` is part of `pvm_control_engine`. Bounded-parallel lifecycle dispatch with inventory and outcome safeguards. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

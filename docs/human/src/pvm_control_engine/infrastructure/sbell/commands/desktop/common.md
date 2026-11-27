# Human-readable documentation for `common.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/desktop/common.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Bounded-parallel execution workflow for virtual-desktop lifecycle actions.

## 2. Functional summary

Bounded-parallel execution workflow for virtual-desktop lifecycle actions.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `PlanFactory.__call__(self, action: Action, targets: tuple[VirtualDesktop, ...], section: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `DesktopOperationExecutor.__init__(self, collection: CollectionCoordinator, lane: LockType, closing: threading.Event, create_plan: PlanFactory, dispatch_one: DispatchOne, max_concurrency: int=3) -> None`

Calls `ValueError`. Reads or updates `self._collection`, `self._lane`, `self._closing`, `self._create_plan`, `self._dispatch_one`, `self._max_concurrency`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('max_concurrency must be positive')`.

### `DesktopOperationExecutor.execute(self, token: str, action: Action, targets: tuple[VirtualDesktop, ...], section: SectionSnapshot[object], *, is_bulk: bool, plan: OperationPlan, dispatch: Dispatch, on_progress: ProgressSink | None=None) -> OperationResult`

Calls `self._closing.is_set`, `AppError`, `self._create_plan`, `datetime.now`, `aggregate_state`. Reads or updates `current`, `started`, `stop_reason`, `state`, `outcomes`. Explicit return value(s): `OperationResult(operation_id=str(uuidlib.uuid4()), action=action, state=state, targets=tuple(outcome`. Can raise `AppError(ErrorKind.POLICY, 'operation coordinator is shutting down')`, `AppError(ErrorKind.POLICY, 'Desktop plan changed after review')`, `AppError(ErrorKind.POLICY, 'Desktop inventory changed before dispatch')`.

## 6. Classes and data structures

### `PlanFactory`

- **Bases:** Protocol.
- **Description:** Class declared with bases: Protocol.
- **Methods:** `__call__`.

### `DesktopOperationExecutor`

- **Bases:** no explicit base class.
- **Description:** Run Desktop batches in a bounded pool behind the shared lifecycle lane.
- **Methods:** `__init__`, `execute`.

### Module-level values

- `Dispatch` = `Callable[[str, str], object]`
- `DispatchOne` = `Callable[..., TargetOutcome]`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `max_concurrency < 1`
- `self._closing.is_set()`
- `self._closing.is_set()`
- `plan.action is not current.action or plan.target_uuids != current.target_uuids or plan.inventory_generation != current.inventory_generation or (plan.inventory_succeeded_at != current.inventory_succeeded_at) or (plan.is_bulk != current.is_bu`
- `stop_reason != DAEMON_OFFLINE_REASON`
- `any((outcome.code == 'DAEMON_OFFLINE' for outcome in outcomes))` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `outcome in outcomes (comprehension)`
- `outcome in outcomes (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 100) handles: CollectionSuperseded.
- `try` block (line 112) handles: no typed handler.
- `try` block (line 143) handles: Exception.

Explicitly raised exception expressions: `ValueError('max_concurrency must be positive')`, `AppError(ErrorKind.POLICY, 'operation coordinator is shutting down')`, `AppError(ErrorKind.POLICY, 'Desktop plan changed after review')`, `AppError(ErrorKind.POLICY, 'Desktop inventory changed before dispatch')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.collection`, `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.policies`, `pvm_control_engine.infrastructure.sbell.commands.vm.bulk`, `pvm_control_engine.infrastructure.sbell.commands.vm.results`.
- **Standard-library/third-party imports:** `__future__`, `threading`, `uuid`, `_thread`, `collections.abc`, `datetime`, `typing`.

Related module documentation:

- [`pvm_control_engine.application.collection`](../../../../application/collection/__init__.md)
- [`pvm_control_engine.domain.desktops`](../../../../domain/desktops.md)
- [`pvm_control_engine.domain.errors`](../../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.domain.policies`](../../../../domain/policies.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.bulk`](../vm/bulk.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.results`](../vm/results.md)

## 11. Real-world scenario

Bounded-parallel execution workflow for virtual-desktop lifecycle actions.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`common.py` is part of `pvm_control_engine`. Bounded-parallel execution workflow for virtual-desktop lifecycle actions. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

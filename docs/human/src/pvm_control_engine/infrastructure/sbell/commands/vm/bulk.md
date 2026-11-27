# Human-readable documentation for `bulk.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/vm/bulk.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Bounded rolling dispatch for one mutation batch. The caller owns the operation-level mutation barrier. This module only schedules per-target work inside that barrier and reports targets that were never started.

## 2. Functional summary

Bounded rolling dispatch for one mutation batch. The caller owns the operation-level mutation barrier. This module only schedules per-target work inside that barrier and reports targets that were never started.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `execute_bounded_batch(targets: Sequence[T], dispatch: Callable[[T], TargetOutcome], *, max_concurrency: int, is_bulk: bool, must_stop: Callable[[TargetOutcome], bool], stop_reason_for: Callable[[TargetOutcome], str], on_progress: ProgressSink | None=None) -> tuple[TargetOutcome, ...]`

Dispatch a batch using a bounded rolling window. Results are returned in the original target order. A worker that observes a batch-stopping result raises a shared stop event immediately; the supervisor cancels work that has not started, waits for work already in flight, and records only undispatched targets as ``NOT_STARTED``.

### `HasUuid.uuid(self) -> str`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### Lexically nested definitions

#### `execute_bounded_batch.request_stop(reason: str) -> None`

Calls `stop_event.set`. Reads or updates `stop_reason[0]`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

#### `execute_bounded_batch.current_stop_reason() -> str | None`

Explicit return value(s): `stop_reason[0]`.

#### `execute_bounded_batch.run_one(target: T) -> TargetOutcome`

Calls `dispatch`, `TargetOutcome`, `must_stop`, `request_stop`, `stop_reason_for`. Reads or updates `outcome`, `reason`, `stop_reason[0]`. Explicit return value(s): `outcome`.

#### `execute_bounded_batch.fill_window(pool: ThreadPoolExecutor) -> None`

Calls `len`, `stop_event.is_set`, `pool.submit`. Reads or updates `target`, `next_index`, `future_targets[pool.submit(run_one, target)]`. Explicit return value(s): `None`.

## 6. Classes and data structures

### `HasUuid`

- **Bases:** Protocol.
- **Description:** Class declared with bases: Protocol.
- **Methods:** `uuid`.

### Module-level values

- `T` = `TypeVar('T', bound=HasUuid)`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `max_concurrency < 1`
- `not targets`
- `len(target_order) != len(target_ids)`
- `is_bulk and reason is not None`
- `is_bulk`
- `outcome is None`
- `outcome.state is OperationState.NOT_STARTED`
- `stop_reason[0] is None or reason == DAEMON_OFFLINE_REASON`
- `stop_event.is_set()`
- `target.uuid not in ordered_outcomes`
- `is_bulk`
- `must_stop(outcome)`
- `stop_event.is_set()`
- `stop_reason[0] is None or reason == DAEMON_OFFLINE_REASON`
- `future.cancel()`
- `reason == DAEMON_OFFLINE_REASON` (with an `else` branch)
- `is_bulk`
- `reason == DAEMON_OFFLINE_REASON` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `target in targets`
- `while next_index < len(targets) and len(future_targets) < worker_count`
- `while future_targets`
- `target in targets`
- `(index, target_uuid) in enumerate(target_ids) (comprehension)`
- `future in completed_ordered`
- `target in targets (comprehension)`
- `(future, target) in tuple(future_targets.items())`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 72) handles: Exception.
- `try` block (line 125) handles: Exception.

Explicitly raised exception expressions: `ValueError('max_concurrency must be positive')`, `ValueError('bulk dispatch targets must have unique UUIDs')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.models`, `pvm_control_engine.domain.policies`, `.results`.
- **Standard-library/third-party imports:** `__future__`, `threading`, `collections.abc`, `concurrent.futures`, `typing`.

Related module documentation:

- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.domain.policies`](../../../../domain/policies.md)

## 11. Real-world scenario

Bounded rolling dispatch for one mutation batch. The caller owns the operation-level mutation barrier. This module only schedules per-target work inside that barrier and reports targets that were never started.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`bulk.py` is part of `pvm_control_engine`. Bounded rolling dispatch for one mutation batch. The caller owns the operation-level mutation barrier. This module only schedules per-target work inside that barrier and reports targets that were never started. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

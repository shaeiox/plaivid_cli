# Human-readable documentation for `tasks.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/models/tasks.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Task identity and lifecycle value objects for background operation tracking. These are presentation-agnostic values: no Textual import, no I/O, no locking. They are shared by the application-layer ``TaskManager`` (which owns admission and deduplication) and by the Textual task footer (which only renders them). Keeping them in the domain layer lets a presentation component import a task record without importing the application layer, which the repository's architecture boundary test enforces.

## 2. Functional summary

Task identity and lifecycle value objects for background operation tracking. These are presentation-agnostic values: no Textual import, no I/O, no locking. They are shared by the application-layer ``TaskManager`` (which owns admission and deduplication) and by the Textual task footer (which only renders them). Keeping them in the domain layer lets a presentation component import a task record without importing the application layer, which the repository's architecture boundary test enforces.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `task_status_for(state: OperationState) -> TaskStatus`

Collapse a dispatch outcome onto the operator-visible task vocabulary. Uncertain states map to ``UNKNOWN`` rather than to a definite result, so the footer never under- or over-states what the PVM boundary established.

### `TaskStatus.is_terminal(self) -> bool`

Explicit return value(s): `self not in {TaskStatus.QUEUED, TaskStatus.RUNNING}`.

### `TargetRef.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `TargetRef.short(self) -> str`

Stable, unambiguous suffix used when a label is too long to show.

### `TaskKey.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `TaskRecord.is_terminal(self) -> bool`

Explicit return value(s): `self.status.is_terminal`.

### `TaskRecord.elapsed_seconds(self, *, now: datetime | None=None) -> float`

Calls `max`, `datetime.now`, `(end - self.started_at).total_seconds`. Reads or updates `end`. Explicit return value(s): `max(0.0, (end - self.started_at).total_seconds())`, `0.0`.

### `TaskRecord.copy(self, **changes: object) -> TaskRecord`

Return a shallow copy so published snapshots are never mutated in place.

## 6. Classes and data structures

### `TaskStatus`

- **Bases:** StrEnum.
- **Description:** Operator-visible task state. The vocabulary deliberately separates ``FAILED`` from ``UNKNOWN``: a command whose outcome was never established must not be presented as a definite failure, because that would invite an unsupported retry.
- **Methods:** `is_terminal`.

### `TargetRef`

- **Bases:** no explicit base class.
- **Description:** One operation target: identity is the canonical UUID, never the label.
- **Annotated fields:**
  - `uuid: str`
  - `label: str` (default: `''`)
  - `kind: str` (default: `'vm'`)
- **Methods:** `__post_init__`, `short`.

### `TaskKey`

- **Bases:** no explicit base class.
- **Description:** Deduplication identity: the same action on the same target.
- **Annotated fields:**
  - `action: Action`
  - `target_uuid: str`
- **Methods:** `__post_init__`.

### `TaskRecord`

- **Bases:** no explicit base class.
- **Description:** One live or historical task row. ``message`` is expected to be redacted by whoever sets it; the footer still redacts defensively before display.
- **Annotated fields:**
  - `key: TaskKey`
  - `target: TargetRef`
  - `operation_id: str`
  - `task_id: str` (default: `field(default_factory=lambda: str(uuidlib.uuid4()))`)
  - `status: TaskStatus` (default: `TaskStatus.QUEUED`)
  - `message: str` (default: `''`)
  - `submitted_at: datetime` (default: `field(default_factory=lambda: datetime.now(UTC))`)
  - `started_at: datetime | None` (default: `None`)
  - `finished_at: datetime | None` (default: `None`)
- **Methods:** `is_terminal`, `elapsed_seconds`, `copy`.

### `TaskEvent`

- **Bases:** no explicit base class.
- **Description:** Immutable notification published by the TaskManager to its listener. Carries only values and primitives: never a widget, so a background thread cannot leak a Textual object into its own queue.
- **Annotated fields:**
  - `kind: str`
  - `record: TaskRecord | None` (default: `None`)
  - `operation_id: str` (default: `''`)
  - `action: Action | None` (default: `None`)
  - `targets: tuple[TargetRef, ...]` (default: `()`)
  - `reason: str` (default: `''`)
  - `message: str` (default: `''`)

### Module-level values

- `_TERMINAL_STATUS` = `{OperationState.SUCCEEDED: TaskStatus.SUCCEEDED, OperationState.COMMAND_ACCEPTED_UNCONFIRMED: TaskStatus.SUCCEEDED, OperationState.OUTCOME_UNKNOWN: TaskStatus.UNKNOWN, OperationSta`
- `_ACTIVE_STATUS` = `{OperationState.QUEUED: TaskStatus.QUEUED, OperationState.DISPATCHING: TaskStatus.RUNNING, OperationState.RUNNING: TaskStatus.RUNNING}`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `self.started_at is None`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 66) handles: KeyError.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `.enums`.
- **Standard-library/third-party imports:** `__future__`, `uuid`, `dataclasses`, `datetime`, `enum`.

## 11. Real-world scenario

Task identity and lifecycle value objects for background operation tracking. These are presentation-agnostic values: no Textual import, no I/O, no locking. They are shared by the application-layer ``TaskManager`` (which owns admission and deduplication) and by the Textual task footer (which only renders them). Keeping them in the domain layer lets a presentation component import a task record without importing the application layer, which the repository's architecture boundary test enforces.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`tasks.py` is part of `pvm_control_engine`. Task identity and lifecycle value objects for background operation tracking. These are presentation-agnostic values: no Textual import, no I/O, no locking. They are shared by the application-layer ``TaskManager`` (which owns admission and deduplication) and by the Textual task footer (which only renders them). Keeping them in the domain layer lets a presentation component import a task record without importing the application layer, which the repository's architecture boundary test enforces. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

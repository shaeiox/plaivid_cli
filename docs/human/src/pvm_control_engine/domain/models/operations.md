# Human-readable documentation for `operations.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/models/operations.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Lifecycle intent, outcome, and policy value objects.

## 2. Functional summary

Lifecycle intent, outcome, and policy value objects.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `OperationResult.succeeded_count(self) -> int`

Calls `sum`. Explicit return value(s): `sum((target.state is OperationState.SUCCEEDED for target in self.targets))`.

### `OperationResult.unknown_count(self) -> int`

Calls `sum`. Explicit return value(s): `sum((target.state is OperationState.OUTCOME_UNKNOWN for target in self.targets))`.

## 6. Classes and data structures

### `ActionPolicy`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `action: Action`
  - `risk: RiskLevel`

### `PvmReply`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `status: str`
  - `action_id: str | None` (default: `None`)
  - `errno: str | None` (default: `None`)
  - `message: str | None` (default: `None`)
  - `returncode: int` (default: `0`)

### `OperationPlan`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `action: Action`
  - `target_uuids: tuple[str, ...]`
  - `inventory_generation: int`
  - `inventory_succeeded_at: datetime`
  - `is_bulk: bool`
  - `freshness_limit_seconds: float`
  - `created_at: datetime`

### `TargetOutcome`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `uuid: str`
  - `state: OperationState`
  - `message: str` (default: `''`)
  - `dispatched: bool` (default: `False`)
  - `errno: str | None` (default: `None`)
  - `code: str | None` (default: `None`)

### `OperationResult`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `operation_id: str`
  - `action: Action`
  - `state: OperationState`
  - `targets: tuple[TargetOutcome, ...]`
  - `started_at: datetime`
  - `finished_at: datetime | None` (default: `None`)
  - `message: str` (default: `''`)
- **Methods:** `succeeded_count`, `unknown_count`.

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `target in self.targets (comprehension)`
- `target in self.targets (comprehension)`

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `.enums`.
- **Standard-library/third-party imports:** `__future__`, `dataclasses`, `datetime`.

## 11. Real-world scenario

Lifecycle intent, outcome, and policy value objects.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`operations.py` is part of `pvm_control_engine`. Lifecycle intent, outcome, and policy value objects. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

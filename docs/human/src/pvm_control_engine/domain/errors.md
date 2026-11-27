# Human-readable documentation for `errors.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/errors.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Typed application errors with user-safe messages.

## 2. Functional summary

Typed application errors with user-safe messages.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `AppError.__init__(self, kind: ErrorKind, message: str, *, code: str | None=None, retryable: bool=False, errno: str | None=None) -> None`

Calls `super().__init__`, `kind.value.upper`, `super`. Reads or updates `self.kind`, `self.code`, `self.retryable`, `self.errno`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

## 6. Classes and data structures

### `AppError`

- **Bases:** RuntimeError.
- **Description:** An expected failure with stable classification and safe display text. ``errno`` carries the ``sbell``/sabadd error number when the failure came from a PVM response, so callers can classify *who* the error belongs to (one target vs. the whole session) without parsing the message text.
- **Methods:** `__init__`.

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`.

Related module documentation:

- [`pvm_control_engine.domain.models`](models/__init__.md)

## 11. Real-world scenario

Typed application errors with user-safe messages.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`errors.py` is part of `pvm_control_engine`. Typed application errors with user-safe messages. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

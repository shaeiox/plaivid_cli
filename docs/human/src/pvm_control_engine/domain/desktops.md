# Human-readable documentation for `desktops.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/desktops.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Distinct read-only Lite Desktop identity and observed states.

## 2. Functional summary

Distinct read-only Lite Desktop identity and observed states.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `VirtualDesktop.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`, `self.name.strip`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

## 6. Classes and data structures

### `VirtualDesktop`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `uuid: str`
  - `name: str`
  - `enabled: str | None` (default: `None`)
  - `local_status: str | None` (default: `None`)
  - `cluster_status: str | None` (default: `None`)
  - `os_type: str | None` (default: `None`)
  - `os_version: str | None` (default: `None`)
  - `vcpu: int | None` (default: `None`)
  - `memory_size_raw: str | None` (default: `None`)
  - `parent_id: str | None` (default: `None`)
- **Methods:** `__post_init__`.

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`, `dataclasses`.

Related module documentation:

- [`pvm_control_engine.domain.models`](models/__init__.md)

## 11. Real-world scenario

Distinct read-only Lite Desktop identity and observed states.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`desktops.py` is part of `pvm_control_engine`. Distinct read-only Lite Desktop identity and observed states. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

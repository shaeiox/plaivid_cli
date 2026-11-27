# Human-readable documentation for `vm_resolver.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/targets/vm_resolver.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Resolve canonical VM UUID inputs against the current Engine inventory.

## 2. Functional summary

Resolve canonical VM UUID inputs against the current Engine inventory.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `VMResolver.__init__(self, application: PlaividApplication) -> None`

Reads or updates `self._application`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `VMResolver.resolve_many(self, vm_inputs: Sequence[str], token: str) -> tuple[tuple[VMRecord, ...], SectionSnapshot[object]]`

Calls `tuple`, `self._application.inventory`, `any`, `AppError`, `len`. Reads or updates `keys`, `(_, section)`, `by_uuid`. Explicit return value(s): `(tuple((by_uuid[key] for key in keys)), section)`. Can raise `AppError(ErrorKind.POLICY, 'at least one VM UUID is required', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'operation target limit exceeded', code='INVALID_TARGET_COUNT')`, `AppError(ErrorKind.POLICY, 'VM UUIDs must be unique', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'current VM inventory is required', code='INVENTORY_UNAVAILABLE')`.

### `VMResolver.resolve(vm_input: str) -> str`

Calls `canonical_uuid`, `AppError`. Reads or updates `key`. Explicit return value(s): `key`. Can raise `AppError(ErrorKind.POLICY, 'VM identifier must be a canonical UUID', code='INVALID_UUID')`.

## 6. Classes and data structures

### `VMResolver`

- **Bases:** no explicit base class.
- **Description:** Validate UUID spelling and bind targets to one current inventory snapshot.
- **Methods:** `__init__`, `resolve_many`, `resolve`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not vm_inputs`
- `len(vm_inputs) > 100`
- `len(set(keys)) != len(keys)`
- `not isinstance(section.value, InventoryData)`
- `any((key not in by_uuid for key in keys))`
- `key != vm_input`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `record in section.value.records (comprehension)`
- `value in vm_inputs (comprehension)`
- `key in keys (comprehension)`
- `key in keys (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 53) handles: (ValueError, TypeError).

Explicitly raised exception expressions: `AppError(ErrorKind.POLICY, 'at least one VM UUID is required', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'operation target limit exceeded', code='INVALID_TARGET_COUNT')`, `AppError(ErrorKind.POLICY, 'VM UUIDs must be unique', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'current VM inventory is required', code='INVENTORY_UNAVAILABLE')`, `AppError(ErrorKind.POLICY, 'VM is not present in current inventory', code='VM_NOT_FOUND')`, `AppError(ErrorKind.POLICY, 'VM identifier must be a canonical UUID', code='INVALID_UUID')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.services`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`, `collections.abc`.

Related module documentation:

- [`pvm_control_engine.application.services`](../application/services.md)
- [`pvm_control_engine.domain.errors`](../domain/errors.md)
- [`pvm_control_engine.domain.models`](../domain/models/__init__.md)

## 11. Real-world scenario

Resolve canonical VM UUID inputs against the current Engine inventory.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`vm_resolver.py` is part of `pvm_control_engine`. Resolve canonical VM UUID inputs against the current Engine inventory. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

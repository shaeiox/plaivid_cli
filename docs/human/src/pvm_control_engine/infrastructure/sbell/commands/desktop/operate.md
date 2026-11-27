# Human-readable documentation for `operate.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/desktop/operate.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Allowlisted Desktop lifecycle command using the shared mutation safety lane.

## 2. Functional summary

Allowlisted Desktop lifecycle command using the shared mutation safety lane.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `VMDispatchCommand.dispatch(self, token: str, vm_uuid: str) -> PvmReply`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `DesktopOperate.__init__(self, auth: AuthProvider, application: PlaividApplication, operations: VMOperationCoordinator, vm_actions: Mapping[Action, VMDispatchCommand]) -> None`

Calls `dict`. Reads or updates `self._auth`, `self._application`, `self._operations`, `self._vm_actions`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `DesktopOperate.execute(self, action: str, uuids: tuple[str, ...]) -> OperationResult`

Calls `tuple`, `self._auth.token`, `self._application.refresh(token, sections=('desktops',)).section`, `any`, `self._operations.create_desktop_plan`. Reads or updates `keys`, `token`, `section`, `by_uuid`, `targets`, `is_bulk`. Explicit return value(s): `self._operations.execute_desktop(token, fixed_action, targets, section, is_bulk=is_bulk, plan=plan, `. Can raise `AppError(ErrorKind.POLICY, 'Desktop UUID list must be non-empty and unique', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'current Desktop inventory is required', code='INVENTORY_UNAVAILABLE')`, `AppError(ErrorKind.POLICY, 'Desktop is not present in current inventory', code='DESKTOP_NOT_FOUND')`, `AppError(ErrorKind.POLICY, 'unsupported Desktop action', code='INVALID_ACTION')`.

### `DesktopOperate._canonical_uuid(value: str) -> str`

Calls `canonical_uuid`, `AppError`. Reads or updates `key`. Explicit return value(s): `key`. Can raise `AppError(ErrorKind.POLICY, 'Desktop identifier must be a canonical UUID', code='INVALID_UUID')`.

## 6. Classes and data structures

### `VMDispatchCommand`

- **Bases:** Protocol.
- **Description:** Class declared with bases: Protocol.
- **Methods:** `dispatch`.

### `DesktopOperate`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Methods:** `__init__`, `execute`, `_canonical_uuid`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not keys or len(set(keys)) != len(keys) or len(keys) > 100`
- `section is None or not isinstance(section.value, tuple)`
- `any((key not in by_uuid for key in keys))`
- `key != value`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `item in section.value (comprehension)`
- `value in uuids (comprehension)`
- `key in keys (comprehension)`
- `key in keys (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 40) handles: ValueError.
- `try` block (line 85) handles: (ValueError, TypeError).

Explicitly raised exception expressions: `AppError(ErrorKind.POLICY, 'Desktop UUID list must be non-empty and unique', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'current Desktop inventory is required', code='INVENTORY_UNAVAILABLE')`, `AppError(ErrorKind.POLICY, 'Desktop is not present in current inventory', code='DESKTOP_NOT_FOUND')`, `AppError(ErrorKind.POLICY, 'Desktop identifier must be a canonical UUID', code='INVALID_UUID')`, `AppError(ErrorKind.POLICY, 'unsupported Desktop action', code='INVALID_ACTION')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.services`, `pvm_control_engine.auth.provider`, `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.infrastructure.sbell.commands.vm.common`.
- **Standard-library/third-party imports:** `__future__`, `collections.abc`, `typing`.

Related module documentation:

- [`pvm_control_engine.application.services`](../../../../application/services.md)
- [`pvm_control_engine.auth.provider`](../../../../auth/provider.md)
- [`pvm_control_engine.domain.desktops`](../../../../domain/desktops.md)
- [`pvm_control_engine.domain.errors`](../../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.common`](../vm/common.md)

## 11. Real-world scenario

Allowlisted Desktop lifecycle command using the shared mutation safety lane.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`operate.py` is part of `pvm_control_engine`. Allowlisted Desktop lifecycle command using the shared mutation safety lane. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

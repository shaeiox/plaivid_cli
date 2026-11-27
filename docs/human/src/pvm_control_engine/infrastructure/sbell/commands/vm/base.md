# Human-readable documentation for `base.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/vm/base.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Small execution base for fixed, action-owned VM sbell commands.

## 2. Functional summary

Small execution base for fixed, action-owned VM sbell commands.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `VMActionCommand.__init__(self, auth: AuthProvider, resolver: VMResolver, operations: VMOperationCoordinator, sbell: SbellClient, *, action_timeout: float) -> None`

Reads or updates `self._auth`, `self._resolver`, `self._operations`, `self._sbell`, `self._action_timeout`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `VMActionCommand.execute(self, vm_input: str) -> OperationResult`

Calls `self._execute`. Explicit return value(s): `self._execute((vm_input,))`.

### `VMActionCommand.execute_many(self, vm_inputs: tuple[str, ...]) -> OperationResult`

Calls `self._execute`. Explicit return value(s): `self._execute(vm_inputs)`.

### `VMActionCommand._execute(self, vm_inputs: Sequence[str]) -> OperationResult`

Calls `self._auth.token`, `self._resolver.resolve_many`, `self._operations.create_plan`, `self._operations.execute`, `len`. Reads or updates `token`, `(records, section)`, `is_bulk`, `plan`. Explicit return value(s): `self._operations.execute(token, self.ACTION, records, section, is_bulk=is_bulk, plan=plan, dispatch=`.

### `VMActionCommand.dispatch(self, token: str, vm_uuid: str) -> PvmReply`

Execute this class's fixed sbell request; never accepts a command name.

### `VMActionCommand.build_params(self, vm_uuid: str) -> str`

No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `NotImplementedError`.

## 6. Classes and data structures

### `VMActionCommand`

- **Bases:** no explicit base class.
- **Description:** Common token, target, safety-plan and transport wiring; subclasses own command data.
- **Annotated fields:**
  - `ACTION: Action`
  - `COMMAND: str`
- **Methods:** `__init__`, `execute`, `execute_many`, `_execute`, `dispatch`, `build_params`.

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

Explicitly raised exception expressions: `NotImplementedError`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.auth.provider`, `pvm_control_engine.domain.models`, `pvm_control_engine.infrastructure.pvm.sbell`, `pvm_control_engine.infrastructure.sbell.commands.vm.common`, `pvm_control_engine.targets.vm_resolver`.
- **Standard-library/third-party imports:** `__future__`, `collections.abc`.

Related module documentation:

- [`pvm_control_engine.auth.provider`](../../../../auth/provider.md)
- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.infrastructure.pvm.sbell`](../../../pvm/sbell.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.common`](common.md)
- [`pvm_control_engine.targets.vm_resolver`](../../../../targets/vm_resolver.md)

## 11. Real-world scenario

Small execution base for fixed, action-owned VM sbell commands.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`base.py` is part of `pvm_control_engine`. Small execution base for fixed, action-owned VM sbell commands. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

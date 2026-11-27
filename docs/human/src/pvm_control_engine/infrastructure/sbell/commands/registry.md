# Human-readable documentation for `registry.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/registry.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Explicit registration of Engine commands exposed to the JSON-RPC service.

## 2. Functional summary

Explicit registration of Engine commands exposed to the JSON-RPC service.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `build_command_registry(provider: LocalPvmAdapter, application: PlaividApplication, sessions: SessionManager, auth: AuthProvider, audit: ReadOnlyAuditAdapter, operations: VMOperationCoordinator, sbell: SbellClient, *, action_timeout: float) -> CommandRegistry`

Construct and register only the fixed local sbell commands the Engine exposes.

### `CommandRegistry.__init__(self, commands: Mapping[str, Any], vm_actions: Mapping[Action, Any]) -> None`

Calls `any`, `dict`, `set`, `ValueError`. Reads or updates `self._commands`, `self._vm_actions`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('registry must contain every supported VM lifecycle action')`, `ValueError('command registry keys must be explicit dotted names')`.

### `CommandRegistry.commands(self) -> Mapping[str, Any]`

Calls `self._commands.copy`. Explicit return value(s): `self._commands.copy()`.

### `CommandRegistry.get(self, name: str) -> Any`

Calls `AppError`. Explicit return value(s): `self._commands[name]`. Can raise `AppError(ErrorKind.POLICY, 'unsupported Engine command', code='INVALID_COMMAND')`.

### `CommandRegistry.vm_action(self, action: str) -> Any`

Calls `Action`, `AppError`. Reads or updates `fixed_action`. Explicit return value(s): `self._vm_actions[fixed_action]`. Can raise `AppError(ErrorKind.POLICY, 'unsupported VM action', code='INVALID_ACTION')`.

## 6. Classes and data structures

### `CommandRegistry`

- **Bases:** no explicit base class.
- **Description:** Keep command names and VM action classes in one reviewed allowlist.
- **Methods:** `__init__`, `commands`, `get`, `vm_action`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `set(vm_actions) != set(Action)`
- `any((not name or '.' not in name for name in commands))`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `name in commands (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 94) handles: KeyError.
- `try` block (line 102) handles: ValueError.
- `try` block (line 108) handles: KeyError.

Explicitly raised exception expressions: `ValueError('registry must contain every supported VM lifecycle action')`, `ValueError('command registry keys must be explicit dotted names')`, `AppError(ErrorKind.POLICY, 'unsupported Engine command', code='INVALID_COMMAND')`, `AppError(ErrorKind.POLICY, 'unsupported VM action', code='INVALID_ACTION')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.services`, `pvm_control_engine.application.session_manager`, `pvm_control_engine.auth.provider`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.infrastructure.audit`, `pvm_control_engine.infrastructure.local.audit`, `pvm_control_engine.infrastructure.local.host_metrics`, `pvm_control_engine.infrastructure.local.nic_samples`, `pvm_control_engine.infrastructure.pvm.adapter`, `pvm_control_engine.infrastructure.pvm.sbell`, `pvm_control_engine.infrastructure.sbell.commands.desktop.operate`, `pvm_control_engine.infrastructure.sbell.commands.monitoring.metrics`, `pvm_control_engine.infrastructure.sbell.commands.network.nic_list`, `pvm_control_engine.infrastructure.sbell.commands.sball.show`, `pvm_control_engine.infrastructure.sbell.commands.user.login`, `pvm_control_engine.infrastructure.sbell.commands.user.logout`, `pvm_control_engine.infrastructure.sbell.commands.user.objects`, `pvm_control_engine.infrastructure.sbell.commands.user.whoami`, `pvm_control_engine.infrastructure.sbell.commands.vm.common`, `pvm_control_engine.infrastructure.sbell.commands.vm.kill`, `pvm_control_engine.infrastructure.sbell.commands.vm.pause`, `pvm_control_engine.infrastructure.sbell.commands.vm.reset`, `pvm_control_engine.infrastructure.sbell.commands.vm.resume`, `pvm_control_engine.infrastructure.sbell.commands.vm.start`, `pvm_control_engine.infrastructure.sbell.commands.vm.stop`, `pvm_control_engine.targets.vm_resolver`.
- **Standard-library/third-party imports:** `__future__`, `collections.abc`, `typing`.

Related module documentation:

- [`pvm_control_engine.application.services`](../../../application/services.md)
- [`pvm_control_engine.application.session_manager`](../../../application/session_manager.md)
- [`pvm_control_engine.auth.provider`](../../../auth/provider.md)
- [`pvm_control_engine.domain.errors`](../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../domain/models/__init__.md)
- [`pvm_control_engine.infrastructure.audit`](../../audit.md)
- [`pvm_control_engine.infrastructure.local.audit`](../../local/audit.md)
- [`pvm_control_engine.infrastructure.local.host_metrics`](../../local/host_metrics.md)
- [`pvm_control_engine.infrastructure.local.nic_samples`](../../local/nic_samples.md)
- [`pvm_control_engine.infrastructure.pvm.adapter`](../../pvm/adapter/__init__.md)
- [`pvm_control_engine.infrastructure.pvm.sbell`](../../pvm/sbell.md)
- [`pvm_control_engine.infrastructure.sbell.commands.desktop.operate`](desktop/operate.md)
- [`pvm_control_engine.infrastructure.sbell.commands.monitoring.metrics`](monitoring/metrics.md)
- [`pvm_control_engine.infrastructure.sbell.commands.network.nic_list`](network/nic_list.md)
- [`pvm_control_engine.infrastructure.sbell.commands.sball.show`](sball/show.md)
- [`pvm_control_engine.infrastructure.sbell.commands.user.login`](user/login.md)
- [`pvm_control_engine.infrastructure.sbell.commands.user.logout`](user/logout.md)
- [`pvm_control_engine.infrastructure.sbell.commands.user.objects`](user/objects.md)
- [`pvm_control_engine.infrastructure.sbell.commands.user.whoami`](user/whoami.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.common`](vm/common.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.kill`](vm/kill.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.pause`](vm/pause.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.reset`](vm/reset.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.resume`](vm/resume.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.start`](vm/start.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.stop`](vm/stop.md)
- [`pvm_control_engine.targets.vm_resolver`](../../../targets/vm_resolver.md)

## 11. Real-world scenario

Explicit registration of Engine commands exposed to the JSON-RPC service.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`registry.py` is part of `pvm_control_engine`. Explicit registration of Engine commands exposed to the JSON-RPC service. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

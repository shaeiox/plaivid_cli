# Human-readable documentation for `composition.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/composition.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Explicit construction of the Engine runtime dependency graph.

## 2. Functional summary

Explicit construction of the Engine runtime dependency graph.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `build_runtime(settings: Settings, socket_path: str | Path, *, allowed_uids=None, max_workers: int=4, socket_mode: int=384) -> EngineRuntime`

Compose Engine adapters, application services, registry, and RPC transport.

### `EngineRuntime.serve(self) -> None`

Serve requests until the Unix RPC server is asked to stop.

### `EngineRuntime.close(self) -> None`

Close owned resources once, even if an earlier close step raises.

## 6. Classes and data structures

### `EngineRuntime`

- **Bases:** no explicit base class.
- **Description:** Own the serving lifecycle and all long-lived coordinators.
- **Annotated fields:**
  - `service: EngineService`
  - `server: UnixRpcServer`
  - `operations: VMOperationCoordinator`
  - `collection: CollectionCoordinator`
  - `_close_lock: threading.Lock` (default: `field(default_factory=threading.Lock, init=False, repr=False)`)
  - `_closed: bool` (default: `field(default=False, init=False, repr=False)`)
- **Methods:** `serve`, `close`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `self._closed`
- `operations is not None`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 82) handles: BaseException.
- `try` block (line 47) handles: no typed handler.
- `try` block (line 108) handles: no typed handler.
- `try` block (line 50) handles: no typed handler.

Explicitly raised exception expressions: `re-raise`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.collection`, `pvm_control_engine.application.service`, `pvm_control_engine.application.services`, `pvm_control_engine.application.session_manager`, `pvm_control_engine.auth.provider`, `pvm_control_engine.auth.session_store`, `pvm_control_engine.config`, `pvm_control_engine.infrastructure.audit`, `pvm_control_engine.infrastructure.process`, `pvm_control_engine.infrastructure.pvm.adapter`, `pvm_control_engine.infrastructure.pvm.sbell`, `pvm_control_engine.infrastructure.sbell.commands.registry`, `pvm_control_engine.infrastructure.sbell.commands.vm.common`, `pvm_control_engine.ipc.dispatcher`, `pvm_control_engine.ipc.server`.
- **Standard-library/third-party imports:** `__future__`, `threading`, `dataclasses`, `pathlib`.

Related module documentation:

- [`pvm_control_engine.application.collection`](application/collection/__init__.md)
- [`pvm_control_engine.application.service`](application/service.md)
- [`pvm_control_engine.application.services`](application/services.md)
- [`pvm_control_engine.application.session_manager`](application/session_manager.md)
- [`pvm_control_engine.auth.provider`](auth/provider.md)
- [`pvm_control_engine.auth.session_store`](auth/session_store.md)
- [`pvm_control_engine.config`](config.md)
- [`pvm_control_engine.infrastructure.audit`](infrastructure/audit.md)
- [`pvm_control_engine.infrastructure.process`](infrastructure/process.md)
- [`pvm_control_engine.infrastructure.pvm.adapter`](infrastructure/pvm/adapter/__init__.md)
- [`pvm_control_engine.infrastructure.pvm.sbell`](infrastructure/pvm/sbell.md)
- [`pvm_control_engine.infrastructure.sbell.commands.registry`](infrastructure/sbell/commands/registry.md)
- [`pvm_control_engine.infrastructure.sbell.commands.vm.common`](infrastructure/sbell/commands/vm/common.md)
- [`pvm_control_engine.ipc.dispatcher`](ipc/dispatcher.md)
- [`pvm_control_engine.ipc.server`](ipc/server.md)

## 11. Real-world scenario

Explicit construction of the Engine runtime dependency graph.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`composition.py` is part of `pvm_control_engine`. Explicit construction of the Engine runtime dependency graph. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

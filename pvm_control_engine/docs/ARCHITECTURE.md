# PVM Control Engine architecture and IPC contract

The Engine is an independently installable project. Its import package is `pvm_control_engine` under `src/pvm_control_engine/`; UI source, assets, and runtime dependencies are not included. Engine entry point: `pvm-control-engine serve` (and `pvm-control-engine login` for local terminal authentication).

## Responsibilities and runtime

The Engine exclusively owns auth/session state, canonical VM target resolution, local PVM reads, the approved `sbell` integration, process execution, and lifecycle mutation safeguards. The Textual UI connects only through the local Unix-domain JSON-RPC protocol. No HTTP(S), nginx/httpd, `sabad` client, or raw `sballd` protocol is used.

Startup follows one explicit path: `pvm_control_engine.__main__` calls `bootstrap.main`, which parses CLI options, loads configuration, resolves socket/UID policy, and calls `composition.build_runtime`. That shallow composition function creates the adapters, coordinators and application services, then delegates the fixed `sbell` command/action registrations to `commands.registry.build_command_registry`. The returned `EngineRuntime` owns `serve()` and idempotent `close()`. Bootstrap installs a SIGTERM handler that requests server shutdown, preserves the established exit/error policy, restores the prior handler, and closes the runtime in `finally`. If composition fails after coordinator creation, it closes the coordinators before re-raising.

Evidence: `pvm_control_engine/src/pvm_control_engine/__main__.py`, `bootstrap.py::main`, `bootstrap.py::_run_runtime`, `composition.py::build_runtime`, `composition.py::EngineRuntime`, `infrastructure/sbell/commands/registry.py::build_command_registry`; startup/lifecycle regressions are covered in `pvm_control_engine/tests/unit/test_pvm_control_engine.py`.

Run the Engine under the local account authorized for PVM access. The socket defaults to `$XDG_RUNTIME_DIR/pvm-control-engine.sock` or the Engine state directory, is created with restrictive parent/socket permissions, and accepts only the Engine UID by default. `--allow-uid` and group-writable mode are opt-in and share the same Engine session; do not use them for mutually untrusted users.

## IPC contract: `plaivid.engine.v1`

Transport is one UTF-8 JSON-RPC 2.0 object, newline-terminated, per AF_UNIX stream connection. Request and response frames are limited to 1 MiB; the server worker pool is bounded. Batches and notifications are not supported. Linux `SO_PEERCRED` UID checks apply where available. The explicit allowlist is defined in `src/pvm_control_engine/ipc/dispatcher.py`.

Methods include health, snapshot collection, VM list/detail, host and network sections, Desktop inventory/actions, audit, logout, and allowlisted VM actions. Callers cannot choose an arbitrary sbell module/command or provide raw XML, argv, passwords, or tokens. `vm.operate` accepts one action and one canonical UUID or a bounded UUID list. The Engine verifies every target against current inventory. Error envelopes suppress internal exception content and redact suspicious details.

The UI-side contract and allowed method mapping are documented in [`../../UI/docs/IPC.md`](../../UI/docs/IPC.md). UI wire DTOs live in `UI/tui/src/plaivid_ui/engine_client/dto.py`; that is a protocol adaptation layer, not a shared runtime package.

## Authentication and credential policy

`pvm-control-engine login` prompts on a terminal using no-echo password input and persists only the Engine-owned session cache. The password and cached token are not sent over IPC or logged. The resulting local `sbell` login remains subject to `PLAIVID_ALLOW_CREDENTIAL_ARGV`; default-deny behavior is unchanged because credentials may be visible in process arguments. The UI can only connect to a pre-established Engine session. There is deliberately no password/token-bearing RPC method.

## VM action command path

Concrete VM commands live in `src/pvm_control_engine/infrastructure/sbell/commands/vm/`. Each action owns its fixed command identifiers and action-specific parameters. For StartVM the trace is `RpcDispatcher.dispatch` → `EngineService.operate` → `CommandRegistry.vm_action` → `StartVM.execute` → `AuthProvider.token` → `VMResolver.resolve_many` → `VMOperationCoordinator.execute` → `StartVM.dispatch` → `SbellClient.call` → `ProcessRunner.run`.

The operation coordinator preserves inventory freshness, UUID validation, mutation barriers, bounded bulk execution, per-target/session failure classification, timeout/liveness uncertainty, redaction, and reconciliation. StartVM retains its established XML order and values, including `host=auto`, disabled versioning, an empty version key, and `exit_from_replicate=yes`. No automatic retry converts an uncertain outcome into success.

## Data and validation boundary

Authenticated read queries still share `LocalPvmAdapter`; command ownership is explicit for operations and primary RPC operations, while read query request construction is not yet fully migrated into per-query command modules. Real host response semantics remain unverified. No destructive real-host tests are part of the automated suite.

See [`REAL_PVM_VALIDATION.md`](REAL_PVM_VALIDATION.md), [`SBELL-SABAD.md`](SBELL-SABAD.md), and [`PVM_REFERENCE.md`](PVM_REFERENCE.md) for host validation and protocol references.

# PVM Control Engine (separation work in progress)

The repository now has an Engine-owned Python package at `pvm_control_engine/` and a TUI source package at `tui/src/plaivid_cli/`. The Engine exposes a local Unix socket and the independent `pvm-control-engine` console script. The `plaivid-tui` project exposes `plaivid`; its current one-shot commands use the RPC client. **The Textual dashboard is not yet connected to that client**, and portions of the prior application/infrastructure code are still present in the TUI source tree. This is not yet a complete application separation or a compatible replacement for the previous full CLI/TUI workflow.

## Build and run

From the repository root, with Python 3.12 or later:

```sh
python -m venv /tmp/pvm-engine-env
/tmp/pvm-engine-env/bin/pip install ./pvm_control_engine
/tmp/pvm-engine-env/bin/pvm-control-engine serve

python -m venv /tmp/plaivid-tui-env
/tmp/plaivid-tui-env/bin/pip install ./tui
/tmp/plaivid-tui-env/bin/plaivid health
```

The default socket is `$XDG_RUNTIME_DIR/pvm-control-engine.sock`, or the Engine state directory if `XDG_RUNTIME_DIR` is unset. Override it consistently with `PLAIVID_CONTROL_SOCKET`. The parent directory is created mode `0700`; the socket defaults to `0600`. `--socket-mode 0660` is opt-in and requires explicit `--allow-uid UID` entries for peer UIDs. The TUI client uses the same environment variable. Passwords are not accepted by the JSON-RPC contract. Consequently `plaivid login` is intentionally unavailable until a trusted Engine-side authentication workflow is implemented; the CLI does not prompt for or forward a password. No password or Engine session token is included in responses.

The Engine requires local Linux, `sbell`, `pvm-running-vms`, and (depending on deployment) sudo configuration. Credential-bearing argv remains default-deny: `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` is an explicit acknowledgement of the existing `sbell` argv exposure, not a secure credential transport. No real PVM host was tested. Do not enable this setting without assessing local process visibility and `sbell` behavior.

## Socket contract: `plaivid.engine.v1`

Transport is one UTF-8 JSON-RPC 2.0 object, newline-terminated, per AF_UNIX stream connection. The maximum request/response payload is 1 MiB; at most 16 workers are configurable (default 4), with excess work rejected. Notifications and batches are not supported. The server applies Linux `SO_PEERCRED` UID checks where available and socket filesystem permissions. Responses are bounded, and internal exceptions are not serialized.

Allowlisted methods currently implemented:

- `engine.health`, `snapshot.collect` (`sections` from a fixed section allowlist)
- `vm.list`, `vm.get(uuid)`, `vm.tap_mapping`, `vm.operate(action, uuid | uuids)`
- `desktop.list`, `desktop.operate(action, uuids)`
- `host.status`, `host.metrics`, `host.local`, `network.nic_list`, `network.nic_samples`, `overview.dashboard`
- `audit.recent(limit)`, `session.logout` (login is deliberately not an IPC method)

No method accepts raw XML, module/command names, arbitrary argv, passwords, or session tokens. An existing locally stored Engine session is required for authenticated reads and mutations; there is not yet a supported login flow. Mutating VM/desktop methods require canonical UUIDs, enforce a maximum of 100 unique targets, verify targets against current Engine-side inventory, and pass through freshness, mutation barriers, bulk admission, and reconciliation. Unknown PVM outcomes remain unknown in the returned operation result. The JSON-RPC error envelope is `error: {code, message, data?}`; internal exception strings are intentionally omitted. Credentials are never included in success results.

## Engine command path

VM lifecycle commands are concrete classes under `pvm_control_engine/infrastructure/sbell/commands/vm/`; the generic action-parameter switch and `application/operations/` package are removed. `StartVM` owns the fixed `vm/start` identifiers and builds its XML using ElementTree. The command takes a VM UUID (or a tuple of UUIDs for bulk), obtains the token through injected `AuthProvider`, resolves the input through `VMResolver`, and runs the shared mutation/freshness/bulk/reconciliation lane before its fixed `SbellClient.call`.

The single-target start path is:

`RpcDispatcher.dispatch` (`pvm_control_engine/ipc/dispatcher.py`) → `EngineService.operate` (`pvm_control_engine/application/service.py`) → `CommandRegistry.vm_action` (`pvm_control_engine/infrastructure/sbell/commands/registry.py`) → `StartVM.execute` (`pvm_control_engine/infrastructure/sbell/commands/vm/start.py`) → `AuthProvider.token` (`pvm_control_engine/auth/provider.py`) → `VMResolver.resolve_many` (`pvm_control_engine/targets/vm_resolver.py`) → `VMOperationCoordinator.execute` (`pvm_control_engine/infrastructure/sbell/commands/vm/common.py`) → `StartVM.dispatch` → `SbellClient.call` (`pvm_control_engine/infrastructure/pvm/sbell.py`) → `ProcessRunner.run` (`pvm_control_engine/infrastructure/process.py`). The start payload preserves the established `<vm_start>` field order and values, including `host=auto`, disabled versioning, an empty version key, and `exit_from_replicate=yes`.

`VMOperationCoordinator` and its planner/bulk/result helpers retain the existing freshness admission, per-target inventory checks, mutation barrier, bounded dispatch, target/session failure scope, timeout/liveness classification, and post-action reconciliation. The Desktop command shares the same operation lane and dispatches only through the fixed VM action classes selected by the explicit registry. No raw module, command, XML, or argv is supplied by an RPC caller.

Authenticated collection reads still enter through `PlaividApplication` and `LocalPvmAdapter`; this refactor makes VM lifecycle dispatch command-centered but does not yet move every read query's request construction out of that shared read adapter. The existing socket API and response shapes are unchanged.

### Multi-UID behavior

The normal configuration admits only the Engine process UID and uses a `0600` socket. If an operator opts into additional UIDs, they currently share the Engine's one configured session store and authenticated PVM session; any admitted UID can perform every allowlisted operation and logout that session. This is intentionally called out rather than presented as per-user isolation. Do not use multi-UID mode for mutually untrusted users. Per-peer session isolation and ownership mapping are not implemented.

## Known gaps

- The Textual dashboard still has direct application/domain/session/operation coupling and is not an Engine RPC client. The current `plaivid` `tui` command reports this limitation rather than starting an in-process Engine.
- Some prior runtime modules remain duplicated in the TUI distribution. A static source grep and independent wheel installation are still required before claiming a strict runtime boundary.
- `snapshot.collect` and local monitoring/audit RPCs have basic endpoint coverage, but end-to-end UI capability parity is not established.
- The Engine and TUI wheels built and were installed into separate temporary Python 3.11 venvs with `--ignore-requires-python` (the project metadata requires Python 3.12, which is unavailable in this workspace). Installed imports/entrypoints passed, but normal supported-version installation has not been exercised.
- Fake Unix-socket tests and the full test suite pass, but a complete security review remains outstanding.
- `sbell` credential transport behavior and all PVM command semantics remain unverified against a real host; none was used during this work.

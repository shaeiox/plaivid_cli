# PVM Control Engine

PVM Control Engine is a separate, local process that exposes selected reads and lifecycle
requests through JSON-RPC 2.0 on a Unix-domain socket. It uses the existing bounded
`ProcessRunner`, `SbellClient`, `LocalPvmAdapter`, parsers, session manager, and operation
coordinator. It does not replace or connect to `plaivid` or its TUI.

## Run

Install the project (or its wheel), then start:

```sh
pvm-control-engine serve
# or
python -m pvm_control_engine serve --socket /run/user/1000/pvm-control.sock
```

The default socket is `$XDG_RUNTIME_DIR/pvm-control-engine.sock` when `XDG_RUNTIME_DIR` is
set. Otherwise it is `<PLAIVID_STATE_DIR or XDG_STATE_HOME/plaivid>/pvm-control-engine.sock`.
Override with `--socket PATH` or `PLAIVID_CONTROL_SOCKET`. Socket mode is `0600` by default;
`--socket-mode 0660` is available for deployments where authorized users share the socket's
containing directory/group. Modes granting world access are not supported. Peer UID checks still
apply. The server removes only its own socket inode on orderly shutdown. A stale, owned socket is removed at
startup; a live listener or an existing non-socket/unowned path is rejected.

`--allow-uid UID` can add a Linux UID to the default current-user allowlist (repeatable); for
that user to reach the socket, configure a shared group/directory and `--socket-mode 0660`.
`--max-workers N` bounds concurrent RPC workers (1–16, default 4). The socket is additionally
authorized using Linux `SO_PEERCRED` where available. Calls from unauthorized peers do not
reach method dispatch.

The Engine uses existing settings such as `PLAIVID_SBELL`, `PLAIVID_CMD_TIMEOUT`,
`PLAIVID_ACTION_TIMEOUT`, `PLAIVID_MAX_OUTPUT_BYTES`, `PLAIVID_STATE_DIR`, and
`PLAIVID_ALLOW_CREDENTIAL_ARGV`; refer to `docs/ENVIRONMENT.md`. In particular, credential
argv exposure remains **default-deny**. Login and token-bearing PVM commands fail before
starting `sbell` unless `PLAIVID_ALLOW_CREDENTIAL_ARGV` is explicitly enabled. This existing
risk is not mitigated by the socket.

## IPC contract

Each client opens a Unix stream socket, sends one UTF-8 JSON-RPC 2.0 object followed by `\n`,
reads one newline-terminated response, and closes the connection. A connection carries one
request only. Maximum request and response frame size is 1 MiB. `params` must be a JSON object;
unknown request or method parameter fields are rejected. Notifications are unsupported. No
raw XML, arbitrary module/command, arbitrary argv, token, or selector is accepted.

Permitted methods:

| Method | Parameters | Result |
|---|---|---|
| `engine.health` | `{}` | Engine process health |
| `vm.list` | `{}` | Inventory data and collection metadata |
| `vm.get` | `{"uuid":"canonical-lowercase-uuid"}` | Detail data and collection metadata |
| `host.status` | `{}` | `sball/show` status and collection metadata |
| `host.metrics` | `{}` | `monitoring/metrics` values and collection metadata |
| `desktop.list` | `{}` | Existing restricted Lite Desktop object query |
| `overview.dashboard` | `{}` | Existing dashboard object query and collection metadata |
| `vm.tap_mapping` | `{}` | Existing restricted VM tap/NIC mapping query |
| `network.nic_list` | `{}` | `network/nic-list` values and collection metadata |
| `session.login` | `{"username":"...","password":"..."}` | Authentication state and username only; never the token |
| `session.logout` | `{}` | Authentication state |
| `vm.operate` | `{"uuid":"canonical-lowercase-uuid","action":"start|stop|kill|reset|pause|resume"}` | Existing structured operation outcome |

RPC errors use standard JSON-RPC error objects. Application errors contain a stable code and
safe message; unexpected failures do not return exception strings, raw XML, or tracebacks.
Credentials are accepted only for the explicit `session.login` method and are not logged or
returned. Do not enable debug logging that records RPC payloads.

Mutations accept one canonical UUID and one enumerated `Action`, never names, indices, group
selectors, or bulk requests. The Engine refreshes inventory and invokes the existing planner and
coordinator; exact current-record membership, freshness, state quality, and the mutation barrier
are rechecked under existing policy immediately before dispatch. The operation response does not
claim VM completion; unknown outcomes remain unknown.

## PVM calls used

The Engine reuses the canonical local adapter's XML builders and parsers for:

- `user login`, `user whoami`, `user logout`
- `user objects` with only the existing VM inventory, UUID-specific detail, VM tap mapping, Lite Desktop, and dashboard queries
- `sball show`
- `monitoring metrics`
- `network nic-list`
- `vm start`, `vm stop`, `vm kill`, `vm reset`, `vm pause`, `vm resume`
- `pvm-running-vms` local process evidence for inventory (not an `sbell` module)

No other command catalog, `sabad`, HTTP service, or raw `sballd` protocol is used.

## Verification boundary

Engine tests use fake providers/process runners and temporary Unix sockets; they never start
`sbell`, contact PVM, or verify host permissions. PVM response semantics, supported object
fields, action acceptance/completion, process-list output, credential exposure on the deployed
host, and `SO_PEERCRED` deployment behavior still require authorized manual validation. See
`docs/REAL_PVM_VALIDATION.md`.

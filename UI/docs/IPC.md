# UI ↔ PVM Control Engine IPC

The UI owns only presentation, formatting, UI task-board state, a Unix-socket JSON-RPC client, and wire DTOs. It imports no `pvm_control_engine` module and does not execute `sbell`, `pvm-running-vms`, or arbitrary child processes. All authenticated capabilities travel through the existing `plaivid.engine.v1` AF_UNIX protocol.

## Transport

Each request is one UTF-8 JSON-RPC 2.0 object terminated by newline over a private Unix-domain socket. The UI client sends a single request per connection, caps a frame at 1 MiB, checks response IDs and envelope shape, and maps unavailable/malformed replies to safe UI errors. Socket selection is `PLAIVID_CONTROL_SOCKET`, then `$XDG_RUNTIME_DIR/pvm-control-engine.sock`, then the Engine state directory.

## UI method usage

| UI capability | RPC method | Parameters |
|---|---|---|
| Connect/status | `engine.health`, then `vm.list` to validate the pre-existing Engine session | none |
| VM inventory and monitoring | `snapshot.collect` | a list from the fixed section set: `inventory`, `dashboard`, `host_status`, `host_metrics`, `local_host`, `physical_nics`, `nic_samples`, `desktops` |
| VM detail | `vm.get` | canonical `uuid` |
| Desktop inventory | `desktop.list` (or the `desktops` snapshot section) | none |
| Audit table | `audit.recent` | bounded `limit` |
| VM action | `vm.operate` | `action` plus exactly one canonical `uuid` or a `uuids` list |
| Desktop action | `desktop.operate` | `action`, `uuids` |
| Logout | `session.logout` | none |

The UI sends no module/command name, XML, argv, password, PVM token, or Engine session token. The Engine validates action allowlists, inventory binding, freshness, authorization, concurrency, bulk limits, timeout outcomes, redaction, and reconciliation. A caller timeout or transport loss is not reported as success; operation responses preserve `OUTCOME_UNKNOWN` where the Engine cannot establish an outcome.

## Authentication

Passwords and tokens are not JSON-RPC values. The UI therefore provides a Connect action, not a password form. Authenticate at the Engine-owned terminal using `pvm-control-engine login`; that command reads the password with terminal echo disabled and uses the existing default-deny `PLAIVID_ALLOW_CREDENTIAL_ARGV` policy for the local `sbell` call. The UI then validates the Engine session using `vm.list`. The UI never loads the Engine session file and never receives its token.

The Engine login CLI is a local Engine entry point, not a UI-to-Engine capability call. The existing wire contract intentionally has no login method. If the Engine has no cached session, authenticated RPC reads and actions fail safely and the UI directs the operator to authenticate locally.

## DTO compatibility

`UI/tui/src/plaivid_ui/engine_client/dto.py` owns the UI's parsing of JSON values. It does not import Engine types. DTO decoding is strict about required response containers and converts enumerated strings into UI-owned string enums. Unknown optional section values remain absent rather than being guessed. The Engine protocol remains authoritative; a wire change must update the Engine service contract, this document, the UI DTO decoder, and cross-project contract tests together.

# UI ↔ Engine API contracts

The internal product API is the versioned `plaivid.engine.v1` JSON-RPC 2.0 protocol over a private local AF_UNIX socket. There is no HTTP endpoint. Engine-owned allowlist and parameter validation are canonical in `pvm_control_engine/src/pvm_control_engine/ipc/dispatcher.py`.

Transport uses one newline-terminated UTF-8 JSON request/response per connection and a 1 MiB frame bound. The Engine applies socket ownership/permissions, peer checks where available, a bounded worker pool, fixed method dispatch, strict parameter key validation, safe error envelopes and action-specific target checks. UI client implementation is `UI/tui/src/plaivid_ui/engine_client/client.py`; UI parsing and view-facing DTOs are in `dto.py`.

| Method | Allowed parameters | UI purpose |
|---|---|---|
| `engine.health` | none | Engine availability/contract metadata |
| `snapshot.collect` | `sections` | bounded batched page data; Engine validates the fixed section set |
| `vm.list` | none | authenticated session validation and inventory |
| `vm.get` | `uuid` | selected VM detail |
| `host.status`, `host.metrics`, `host.local` | none | host and local monitoring reads |
| `network.nic_list`, `network.nic_samples` | none | NIC display |
| `overview.dashboard` | none | dashboard snapshot |
| `desktop.list` | none | Desktop inventory |
| `audit.recent` | optional bounded `limit` | read-only audit display |
| `vm.tap_mapping` | none | VM console display mapping |
| `vm.operate` | `action` and exactly one `uuid` or `uuids` | Engine-validated VM lifecycle operation |
| `desktop.operate` | `action`, `uuids` | Engine-validated Desktop operation |
| `session.logout` | none | clear Engine-owned session |

The UI never sends arbitrary module/command names, XML, argv, password, or session token. `login` is intentionally local to the Engine terminal and not an RPC method. Errors and lost connections are not success; operations preserve `OUTCOME_UNKNOWN` where completion cannot be established. For exact fields, UI methods and authentication guidance, see [`../../../UI/docs/IPC.md`](../../../UI/docs/IPC.md) and [`../../../pvm_control_engine/docs/ARCHITECTURE.md`](../../../pvm_control_engine/docs/ARCHITECTURE.md).

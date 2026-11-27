# Module index

| Project/module | Status | Owns |
|---|---|---|
| `pvm_control_engine/src/pvm_control_engine/bootstrap.py` | **CANONICAL Engine composition/CLI** | Engine CLI, `serve`, local `login`, runtime wiring |
| `pvm_control_engine/src/pvm_control_engine/application/` | **CANONICAL Engine** | Collection, application service, operation-level orchestration |
| `pvm_control_engine/src/pvm_control_engine/domain/` | **CANONICAL Engine** | PVM values, validation, result and safety policies |
| `pvm_control_engine/src/pvm_control_engine/auth/` | **CANONICAL Engine** | Engine-owned session persistence/provider |
| `pvm_control_engine/src/pvm_control_engine/infrastructure/` | **CANONICAL Engine** | Local process, PVM, sbell, monitoring and audit adapters |
| `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/` | **CANONICAL Engine** | Fixed RPC command registry and action-owned identifiers/XML |
| `pvm_control_engine/src/pvm_control_engine/ipc/dispatcher.py` | **CANONICAL Engine contract** | Explicit JSON-RPC method allowlist and parameter validation |
| `pvm_control_engine/src/pvm_control_engine/ipc/server.py` | **CANONICAL Engine transport** | Private AF_UNIX server, framing and peer checks |
| `UI/tui/src/plaivid_ui/bootstrap.py` | **CANONICAL UI entry point** | Interactive TUI startup |
| `UI/tui/src/plaivid_ui/engine_client/cli.py` | **CANONICAL UI CLI** | `plaivid` commands mapped to fixed Engine RPC calls |
| `UI/tui/src/plaivid_ui/engine_client/client.py` | **CANONICAL UI IPC client** | Local socket framing, IDs, errors, limits |
| `UI/tui/src/plaivid_ui/engine_client/dto.py` | **CANONICAL UI wire DTOs** | UI-owned JSON response parsing and presentation records |
| `UI/tui/src/plaivid_ui/engine_client/gateway.py` | **CANONICAL UI Engine adapter** | Presentation-friendly gateway over the local client |
| `UI/tui/src/plaivid_ui/presentation/` | **CANONICAL UI presentation** | Textual application, pages, styling, display-only helpers |

The retired combined-project tests remain archived as source under `UI/docs/migration/legacy-tests/`; they are not runtime modules or active tests. They directly coupled TUI tests to the former application and session implementation, contrary to the current IPC boundary. No compatibility runtime is retained.

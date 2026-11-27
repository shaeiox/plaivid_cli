# Two-project runtime boundary

```text
plaivid-ui (plaivid_ui)
Textual views + UI DTOs + AF_UNIX client
               │ plaivid.engine.v1 JSON-RPC
               ▼
pvm-control-engine (pvm_control_engine)
auth/session + UUID validation + PVM/sbell/process work + policy
```

The projects install independently from `UI/` and `pvm_control_engine/`. The UI may depend on Textual/Rich and its own local IPC client; it may not import Engine internals, the removed `plaivid_cli` package, or process-launch APIs. It must not execute sbell, call `pvm-running-vms`, read sessions, or implement PVM operations. UI behavior over Engine capabilities uses the fixed Engine allowlist only.

The Engine exclusively owns credential/session handling, canonical target resolution, local PVM and monitoring reads, command identifiers and XML, process execution, audit data, mutation authorization/freshness/concurrency/bulk protections, redaction and uncertain-result semantics. RPC rejects unknown method names and unexpected parameters. There is no HTTP(S), nginx/httpd, sabad, or raw sballd protocol.

The UI-owned client and DTO layer lives in `UI/tui/src/plaivid_ui/engine_client/`; Engine transport and dispatch live in `pvm_control_engine/src/pvm_control_engine/ipc/`. `UI/docs/IPC.md` documents transport and methods. Static AST boundary tests run in `UI/tests/unit/test_ipc_boundary.py`; Engine method dispatch and socket contracts are exercised in `pvm_control_engine/tests/unit/test_pvm_control_engine.py`.

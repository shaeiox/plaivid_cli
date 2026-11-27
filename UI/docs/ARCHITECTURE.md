# UI architecture

`plaivid-ui` is a presentation-only Python project. Its installable package is `plaivid_ui` under `tui/src/plaivid_ui/`; the Textual application, styles, charts, assets, UI task-state model, locally implemented IPC client, wire DTOs, docs, and active tests are contained in this project. `plaivid` is the UI entry point and launches the TUI by default; UI one-shot commands are also available. There is no root-level product package or UI dependency on the Engine distribution.

## Runtime boundary

```text
Operator terminal
      │
      ▼
plaivid-ui: Textual presentation + UI-owned DTOs/client
      │ AF_UNIX / plaivid.engine.v1 JSON-RPC
      ▼
pvm-control-engine: auth/session + policy + PVM + sbell + process execution
      │ fixed allowlisted local argv; no shell
      ▼
local sbell and pvm-running-vms
```

UI source must not import `pvm_control_engine`, the retired `plaivid_cli` package, or `subprocess`; it has no PVM/session implementation and no direct sbell/PVM command path. The UI does not receive a password or PVM token. See [IPC.md](IPC.md) for transport, methods, authentication, DTO and safety details.

## UI-owned responsibilities

- Textual pages, tables, charts, key bindings, palette, layout, and responsive display behavior.
- Parsing JSON-RPC values into UI-owned DTOs, safely representing unknown or stale information, formatting, and local selection state.
- UI task-progress presentation; the Engine remains authoritative for admission, target resolution, freshness, concurrency, mutation safeguards, and final operation results.
- The bounded local socket client and UI command-line mapping to the fixed Engine method set.

## Engine-owned responsibilities

Authentication and cached session, canonical UUID resolution, PVM reads, local host probes, sbell command construction, process execution, audit reads, action authorization and dispatch, freshness and concurrency barriers, bulk protections, redaction, and uncertain outcomes are exclusively implemented by `pvm_control_engine`.

## Independent development

Install/build/test the Engine from `pvm_control_engine/` and the UI from `UI/`. The UI requires an already running Engine and an Engine-owned authenticated session. Authenticate locally using `pvm-control-engine login`; then launch `plaivid` and connect. These are separate distributions, not extras in one package. The former combined UI/Engine tests are retained as historical source under `docs/migration/legacy-tests/`; active UI tests use UI-owned DTOs, presentation helpers, fake RPC and boundary assertions without installing or importing the Engine.

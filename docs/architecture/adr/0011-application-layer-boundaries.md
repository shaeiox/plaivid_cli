# ADR 0011 — Application Layer and Dependency Boundaries

- **Status:** Accepted (modular-monolith and layer constraints); detailed modules remain proposed
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Product/architecture owner; maintainers enforce import direction.

## Context and evidence

- **Approved constraint:** modular monolith with clear architectural boundaries.
- **Required direction:** Presentation → Application → Domain; Infrastructure implements Application ports; Bootstrap is the sole composition root.
- **Repository fact:** current `orchestrator.App` combines lifecycle, collection, terminal input/render, dispatch and mutation behavior; it does not yet satisfy this boundary.

## Decision

Use one `application/` package. There is no parallel `app/` package, second use-case/service tree, event bus, scheduler package, snapshot-store port, or generic plugin framework.

```text
Presentation ──> Application ──> Domain
                      ▲
                      │ implements Application ports
                Infrastructure
                      ▲
                      │ constructed and wired only by
                  Bootstrap
```

- **Domain:** provider-neutral VM/node/cluster facts, immutable values and pure policies. No Textual, terminal, PVM protocol, subprocess, or filesystem imports.
- **Application:** use cases and two lifecycle owners: one `CollectionCoordinator` and one `OperationCoordinator`. It owns collection policy and mutation admission/orchestration, not PVM transport implementation or terminal widgets.
- **Infrastructure:** implements narrow Application ports. It owns PVM communication/parsing, local command invocation, OS subprocess lifetime and optional external data-source access. No screen imports it directly.
- **Presentation:** CLI and TUI call Application use cases and render returned values. It owns UI navigation, focus, selection, formatting, and user interaction. It never invokes PVM commands or parses PVM XML.
- **Bootstrap:** the only composition root. It validates trusted configuration, constructs the provider, coordinators, use cases and presentation, passes dependencies inward, and starts/stops the application-owned work exactly once. No other module wires concrete implementations.

### Single-owner table

| Concern | Sole owner | Boundary / collaboration |
|---|---|---|
| Refresh cadence and active-view demand | `Application.CollectionCoordinator` (`application/collection.py`) | Textual may request a refresh or provide a timer tick; it does not own a second timer policy. CLI read commands request one bounded collection. |
| Single-flight request admission/coalescing | `Application.CollectionCoordinator` | Uses logical request identity defined by ADR 0004; no independent admission in widgets/providers. |
| Last-good section snapshot publication | `Application.CollectionCoordinator` | Uses its simple concrete in-memory section state from ADR 0005; no snapshot-store interface/port. |
| Read-worker lifetime | `Application.CollectionCoordinator` | One bounded app-lifetime read lane; screens do not own persistent workers. |
| Mutation admission, serialization and operation lifecycle | `Application.OperationCoordinator` (`application/operations.py`) | Owns target/confirmation binding, mutation state and per-target results (ADR 0012/0013). |
| Mutation-worker lifetime | `Application.OperationCoordinator` | App-lifetime-owned; navigation/modal destruction cannot cancel already-dispatched operation tracking. |
| OS child-process lifetime | Infrastructure process runner | Owns argv/environment, deadline, pipe draining/closure, wait/reap and tested descendant cleanup; does not decide application scheduling or mutation policy (ADR 0007). |
| Whole-process composition/start/stop | Bootstrap | Sole root constructs and closes coordinators/provider/presentation in order. It delegates, not a second scheduler/operation owner. |

No separate scheduler package is introduced: refresh timing is behavior of `CollectionCoordinator`. No event bus is introduced: coordinators return/complete typed results to Application; the TUI bridges these to its own UI-thread messages. No generic provider plugin framework is introduced; only the current local PVM provider is needed.

## Consequences

- The current code must be reorganized before it conforms; this ADR is a target boundary, not a claim that implementation already has it.
- The same Application use cases can serve CLI and TUI; Infrastructure can be replaced by a fake in tests.
- The concrete in-memory section state is intentionally not substitutable; do not add a store port without a second justified implementation.
- Ownership is explicit, but the modules can remain small and colocated until actual size warrants more files.

## Validation / enforcement

Use import-direction tests/static checks: Domain imports no outer layer; Application imports no Presentation or concrete PVM Infrastructure; Presentation imports no PVM adapter/process/parser; Infrastructure imports no Textual. Verify one bootstrap composition path and one instance each of `CollectionCoordinator` and `OperationCoordinator`. Fake-provider/process tests exercise their public contracts. Package layout can vary without changing these rules.

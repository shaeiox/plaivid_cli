# ADR 0011 — Application Layer and Dependency Boundaries

- **Status:** Accepted (architectural constraints); package decomposition remains proposed
- **Date:** 2026-10-30
- **Decision owner:** Product/architecture owner; maintainers validate dependency rules.

## Context and evidence

- **Approved constraint:** modular monolith with clear architectural boundaries.
- **Required architecture rule:** Presentation → Application → Domain; Infrastructure implements Application ports; bootstrap/composition root wires components.
- **Repository fact:** current `orchestrator.App` combines session/data refresh/input/render/dispatch, commands import PVM/renderer modules directly, and `transport.py` is a local subprocess boundary. The current code does **not** yet comply with the target layering.

## Decision

The application remains one deployable **modular monolith**, organized around these dependency rules:

```text
Presentation ──> Application ──> Domain
                      ▲
                      │ implements ports declared inward
                Infrastructure
                      ▲
                      │ constructed/wired by
                 Bootstrap
```

- **Domain:** provider-neutral concepts, validated state/value semantics, and policies that do not require terminal, PVM, subprocess, or infrastructure imports. It must not depend on Textual, Rich, Typer, or PVM protocol details.
- **Application:** use cases, orchestration, collection policy, operation lifecycle, application-level semantic change detection, and the ports it needs. It may depend on Domain, not concrete sbell process/XML implementations or Textual widgets.
- **Presentation:** Typer process-level CLI and Textual screens/widgets. It calls Application use cases and presents their results; it must not invoke PVM commands, access XML, or depend on concrete infrastructure implementations.
- **Infrastructure:** implements Application ports and owns local process invocation, PVM communication, protocol parsing/normalization, filesystem/audit-source adapters, and process cleanup. It depends on inward contracts/domain models, not on Presentation.
- **Bootstrap/composition root:** constructs the local provider, collector/state store, use cases, and UI/CLI and wires concrete infrastructure to declared ports.

Use explicit Python packages/modules and narrow interfaces. Do not introduce microservices, distributed messaging, a generic plugin framework, or a speculative remote-node implementation. A later remote provider is deferred and must not alter this phase's local-only product scope (ADR 0009).

## Consequences

- Current source requires architectural migration; this ADR is not a statement that present boundaries already conform.
- Fake ports can test application/use cases without host access, and domain behavior can be tested without Textual or PVM.
- Over-abstraction is a risk: introduce ports for real boundaries (local PVM provider and state store), not for every function.

## Validation / enforcement

Define import-direction checks in tests or static tooling; test that Domain has no forbidden imports, Presentation cannot import PVM infrastructure, and infrastructure never imports Textual. Review composition in one bootstrap path. Exact package layout is not locked by this ADR.

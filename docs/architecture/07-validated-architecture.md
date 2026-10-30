# 07 — Validated Architecture Proposal

**Project:** plaivid_CLI<br>
**Phase:** 1.1 technology/architecture validation and independent-review corrections<br>
**Status:** Historical planning baseline. The existing `implement-complete-plaivid-cli` OpenSpec Change now describes the implementation scope; this proposal is not the as-built record or a release qualification. See `docs/ARCHITECTURE.md` and `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` for current local evidence. No real-PVM validation is claimed.

## Executive summary and evidence

Approved product constraints are Linux, local PVM only, Python 3.12+, modular monolith, and remote-node connectivity deferred. Existing code invokes local `sbell`/`pvm-running-vms`; no target host was available for new captures. Repository examples are not target-host evidence. Preserve `sball_state=quorate` as the valid indication that **Sball reports Quorate**; it does not establish complete membership or universal node health/reachability.

The implementation now uses one `application/` package, one CollectionCoordinator, one OperationCoordinator, one Bootstrap composition root, and Textual. The active Change is `openspec/changes/implement-complete-plaivid-cli/`; unlike this historical proposal, that Change includes lifecycle code. Credential argv exposure remains default-deny and blocked pending an owner/security decision. Do not infer target behavior from local tests.

## Repository facts captured when this proposal was written

The following bullets are historical proposal-time observations, not current repository status. Current implementation details and audit statuses are maintained in the as-built architecture and final implementation audit.

- One `user/objects` all-VM query is followed by a separate `pvm-running-vms` process observation. Current code can overwrite object state from process presence and has a `/proc` uptime fallback. See `04-pvm-interface-analysis.md` and ADR 0004 for exact source facts and corrected semantics.
- Current read calls are synchronous; overview repeats collection. There is no collection coordinator, last-good snapshot lifecycle, Textual application, package metadata, or unit-test suite.
- Current `transport.py` passes login XML/token as subprocess arguments and does not establish PVM exit/completion semantics. Do not claim credential safety or command completion.

## Proposed project structure

One package per architectural layer; no duplicate `app/` use-case tree, scheduler package, snapshot-store port, event bus or generic plugin framework.

```text
plaivid_cli/
  __main__.py                  process entry
  bootstrap.py                 sole composition root; construct/start/stop once
  config.py                    trusted, validated configuration
  domain/
    models.py                  VM/node/cluster/source facts and result values
    policies.py                pure target/risk/outcome policies
  application/
    ports.py                   narrow local PVM read/action contracts only
    use_cases.py               read-only use cases shared by CLI and TUI
    collection.py              one CollectionCoordinator + concrete in-memory section state
    operations.py              one OperationCoordinator and mutation lifecycle (future scope)
  infrastructure/
    pvm/
      adapter.py               local provider facade
      process.py                child argv/environment/deadline/drain/reap
      sbell.py                  response/XML protocol adapter
      parsers.py                pure object/helper/metrics normalization
      audit.py                  optional read-only PVM audit adapter, if approved
  presentation/
    cli.py                     Typer/CLI parsing, one-shot output and exit mapping
    tui.py                     Textual app/screens/widgets and visible interactions
  tests/
    unit/  integration/  ui/  host/  # host tests separately authorized/gated
```

Only Bootstrap wires concrete Infrastructure into Application ports and supplies Application to Presentation. Exact file splits can be smaller; these names express ownership, not a requirement to create one file for every concern.

## Dependency direction and sole ownership

```text
Presentation ──> Application ──> Domain
                      ▲
                      │ Infrastructure implements Application ports
                Infrastructure
                      ▲
                      │ constructed/wired only by
                  Bootstrap
```

- **Domain:** provider-neutral immutable facts and pure rules; no Textual, subprocess, filesystem, XML or PVM dependencies.
- **Application:** shared use cases and the two owners below; no direct terminal rendering or concrete PVM imports.
- **Infrastructure:** local PVM communication/parsing and OS process lifecycle; no UI calls.
- **Presentation:** CLI/TUI invokes use cases and renders typed results; never invokes PVM commands directly.
- **Bootstrap:** sole composition root, and sole owner of whole-application start/stop ordering.

| Responsibility | Sole owner | Clarification |
|---|---|---|
| Refresh cadence / active-view demand | `Application.CollectionCoordinator` | A visible TUI timer only requests work; CLI issues one bounded request. No screen-specific scheduler. |
| Single-flight read admission/coalescing | `Application.CollectionCoordinator` | Uses logical identity from ADR 0004; one active result is shared, obsolete timer ticks are dropped. |
| Last-good section snapshot publication | `Application.CollectionCoordinator` | Holds simple concrete in-memory section values. No SnapshotStore port or second state-store service (ADR 0005). |
| Read-worker lifetime | `Application.CollectionCoordinator` | Bounded, app-lifetime-owned read work; screens do not own provider processes. |
| Mutation admission and lifecycle | `Application.OperationCoordinator` | Owns confirmation binding, serial mutation order, per-target results and mutation-worker lifetime (ADRs 0007/0012/0013). |
| OS process lifetime | Infrastructure process runner | Owns spawn, bounded output/deadline, pipe cleanup, wait/reap and tested descendant policy; not application scheduling or confirmation (ADR 0007). |
| Composition and shutdown | `Bootstrap` | Solely constructs and closes provider/coordinators/UI. It does not duplicate their policies. |

ADR 0011 owns layer/dependency rules. ADR 0004 owns source/batch/request identity. ADR 0014 owns freshness thresholds and scheduling policy as implemented by the single CollectionCoordinator. This explicit split does not create another package/service.

## PVM data and snapshot contract

The object inventory and running-process listing are independently sourced evidence. The all-VM object query remains the logical batch; the process listing is merged only by validated canonical UUID. Preserve source values and timestamps, disagreements, partial/invalid/duplicate/unmatched records, and independent failure/freshness. A failed running-list/enrichment result cannot invalidate a successful object inventory. No N+1 detail queries; detail is on demand. `/proc` scanning is a current source-code fallback, excluded from default/periodic collection unless separately approved and measured. Do not reuse tap/NIC fields unless supported version fixtures demonstrate them.

Each section has its own last-good value, last-attempt/last-success timestamps, freshness/partial/unavailable status and safe diagnostics. CollectionCoordinator publishes successful sections independently. Empty, failed, unsupported, stale, partial and malformed are distinct. See ADR 0004/0005 and `05-data-and-state-architecture.md`; no target-host facts are implied.

## Collection and presentation behavior

The active TUI view requests only the sections it displays. One coordinator controls cadence and single-flight. UI redraw, resize, sorting, filtering, or focus does not fetch. Reads for UUIDs affected by a mutation cannot publish an older generation after the mutation barrier; operation/read ordering and reconciliation are owned by OperationCoordinator/CollectionCoordinator under ADR 0007/0012/0013.

If Textual is accepted after the ADR 0001 prototype, it owns terminal-cell differential rendering. Application semantic comparison can suppress unchanged data updates but is not a second renderer (ADR 0006). Use stable UUID row identity and preserve selection. Benchmark table scale; do not assume virtualization or build a custom dirty-cell engine.

## CLI and TUI responsibilities

- **CLI:** Typer (still a candidate) owns process-level help/options and explicit one-shot read commands, plain output, and stable exit categories from ADR 0013. It calls Application use cases; it does not host TUI navigation.
- **TUI:** Textual (conditional) is launched only when the required input/output streams are TTYs. It owns navigation, focus, selection, filters/sort presentation, visible progress and confirmation UX; collection remains Application-owned.
- **Non-TTY:** never launch a headless TUI, sleep for a second sample, or start hidden polling. Each read command performs one bounded collection and exits. Help/version/config-only commands do not collect. A non-TTY overview is one snapshot, not an implicit live loop. No mutation command is part of the first Change; any later non-TTY mutation is rejected unless a separately approved explicit approval is bound to action/UUIDs/freshness (ADR 0012).
- **Foreground polling:** only an active, visible monitoring view may request scheduled refreshes, with visible freshness/refresh state and approved cadence. No polling survives leaving the relevant view or process.
- A PVM login may create a PVM session; it is not a VM-state read. The first Change must not automatically evict an existing session or log out a user's session. Any target validation session side effect requires explicit authorization and is gated by the credential blocker below.

## Existing OpenSpec Change — `implement-complete-plaivid-cli`

The existing Change supersedes this proposal's old read-only-only scope. It includes local inventory/monitoring, CLI/TUI, lifecycle operations, session/security controls, packaging, docs, and fake-based validation. Its task checkboxes now distinguish locally verified work from incomplete Python 3.12 package verification and owner-run PVM checks. Strict OpenSpec validation is recorded in the final implementation audit.

Local implementation does not authorize a production operation. No PVM host was accessed. Credential argv remains default-deny and owner/security review is blocked; after dispatch, unverified response semantics remain `OUTCOME_UNKNOWN`. All host-dependent behavior remains **PENDING MANUAL PVM VALIDATION**. See [`docs/REAL_PVM_VALIDATION.md`](../REAL_PVM_VALIDATION.md) and the final audit for detailed boundaries.

The historical proposal below describes its original design choices and validation gates; do not read its first-Change or implementation-gate language as the current project plan.

## Technology/runtime summary

This paragraph records the technology candidates considered during planning: the shipped runtime currently uses Textual and argparse, not Typer/Pydantic; packaging metadata targets Python >=3.12 and setuptools/wheel. The workspace lacks Python 3.12, so no Python 3.12 install/smoke or Rocky Linux ABI compatibility is claimed. PyInstaller remains unselected. Do not modify system Python.

## Decisions now vs validation gates

**Can be specified now:** local-only scope; modular-monolith layers; one application package and named owners; no store port/event bus/scheduler package/plugin framework; source separation and partial-data policy; no default `/proc`; read-only first Change; one-shot non-TTY behavior; fail-closed mutation safety; no blind mutation retries; and host validation as a gate.

**Requires target/vendor evidence before corresponding acceptance:** sbell credential channel/process exposure (release blocker); PVM response/exit/acceptance/completion semantics; schema/field support and state disagreement behavior; source permissions and membership coverage; command/process descendants and concurrency; host distribution/architecture/glibc and packaged child environment; supported terminal/VM scale; PVM overhead/freshness budgets; and signing/offline-update/rollback operations.

**Implementation status:** local implementation and fake-based tests are tracked in the active Change and final audit. That is not a release qualification or authorization to test a PVM host.

**Release/host gate:** credential argv risk resolved or explicitly security-accepted; supported host matrix and vendor local-interface contracts verified; Python 3.12+ package install tested; failure/partial/freshness behavior tested; performance/terminal budgets passed; and deployment/rollback reviewed. Lifecycle response semantics remain **PENDING MANUAL PVM VALIDATION**. Do not run production or real-host lifecycle tests without a separate explicit owner procedure.

## Verification and unresolved evidence

No PVM host or new command capture was available. Repository reference examples remain documentation evidence. Before target acceptance, obtain redacted supported-version captures and PVM-owner confirmation for source fields, exit/error/command-completion semantics, Sball Quorate meaning/scope, credentials and privileges. Collect host distribution, architecture, glibc, executable/mount constraints; measure supported inventory scale, command latency/CPU and freshness; test Textual and the package on the actual terminal/ABI matrix. Do not state these as verified until evidence exists.

See [`adr/README.md`](adr/README.md) for the ADR index, ownership, M1–M4 change summary, overlap report and unresolved questions. This proposal remains a planning document, not Architecture Baseline v1.0.

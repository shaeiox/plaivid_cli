# 07 — Validated Architecture Proposal

**Project:** plaivid_CLI  
**Phase:** 1.1 — Technology & Architecture Validation  
**Audit date:** 2026-10-30  
**Status:** Proposal, not implementation approval. Decisions below are explicitly **proposed**, **conditional**, or **open**. No code or target configuration was changed.

## Executive summary

The repository is a local-host Python CLI/TUI. It already has useful PVM command knowledge, an inventory merge, six actions, a session lifecycle, host metrics parsing, and terminal screens. It is not currently a remote client, typed application, snapshot system, packaged application, or tested enterprise product.

The approved product boundary—Linux, local PVM only, cluster-aware only to the extent local interfaces expose information, remote nodes deferred—is compatible with a **modular monolith**. The proposed stack is plausible but should be introduced selectively:

- Prototype **Textual** for the interactive application; let Textual own widget state and terminal diff rendering. Use **Rich** through Textual and add a direct dependency only when imported directly.
- Use **Typer** for process-level CLI options/help/one-shot entry, not as a second navigation framework inside the TUI.
- Validate local PVM XML/text at a narrow adapter boundary; use **Pydantic** selectively for normalized snapshots/configuration. Benchmark with real inventory sizes.
- Keep host access behind a local PVM provider and use immutable, last-good in-memory snapshots. No application database is currently justified; stdlib `sqlite3` is sufficient if a concrete small persistence need emerges.
- Use **uv**, pytest, Ruff, and Pyright in development/CI. Keep development tools off the PVM runtime.
- Investigate a Python 3.12+ **PyInstaller one-directory bundle** as the first deployment prototype, conditional on actual PVM glibc/architecture and host-tool compatibility. Do not replace system Python.
- Resolve destructive/noninteractive confirmation, partial bulk targeting, credential argv exposure, subprocess timeout cleanup, and test coverage before operational expansion.

## 1. Proposed project structure

This is a boundary proposal, not a required directory rename. It should be adapted only after architecture approval and migration planning.

```text
plaivid_cli/
  __main__.py                     process entry
  cli.py                           Typer command grammar and startup modes
  app/
    bootstrap.py                   construct adapters, services, state, UI
    use_cases.py                   refresh, inspect, list, run action orchestration
    operations.py                  serialized mutation lifecycle/results
  domain/
    models.py                      immutable Host/Node/VM/Cluster/Snapshot types
    changes.py                     semantic snapshot changes (not terminal cells)
    policies.py                    action capability/safety policy
  application/
    ports.py                       local provider and snapshot-store protocols
    collector.py                   scheduling, coalescing, freshness, partial failure
    services.py                    use-case implementations
  infrastructure/
    pvm/
      adapter.py                   local PVM provider facade
      sbell.py                     argv, process lifecycle, response envelope
      xml_normalizer.py            supported XML-to-model parsing
      running_vms.py               local text parser for documented helper output
    persistence.py                 only if approved durable state is required
    diagnostics.py                 redacted diagnostics/logging
  presentation/
    textual_app.py                 Textual lifecycle, navigation, bindings
    screens/                       dashboard, VM details, health, audit
    widgets/                       inventory table, status, progress, notifications
  tests/
    unit/                           pure domain, normalization, policy tests
    integration/                    fake executable and subprocess tests
    ui/                              Textual pilot/screen tests
    host/                            explicitly authorized PVM integration checks
  docs/architecture/               this proposal and ADRs
```

Do not create an abstraction merely to anticipate remote nodes. The one local provider interface is justified by separating PVM protocol from application/domain code; the remote implementation remains out of scope.

## 2. Module responsibilities

- **CLI bootstrap:** parse top-level options, version, help, and explicit one-shot commands; construct app dependencies; preserve exit codes. Typer is not a replacement for TUI navigation.
- **Application/use cases:** express operations such as refresh dashboard, select/inspect VM, health view, audit view, and perform a requested action. It coordinates services and returns typed outcomes; it does not parse XML or write terminal escape codes.
- **Domain:** stable typed local-host, cluster and VM concepts; action intent and safety policy; immutable normalized snapshot and semantic changes. Do not represent unavailable data as fabricated zero/healthy.
- **PVM infrastructure adapter:** own `sbell`, `pvm-running-vms`, XML/text parsing, timeout/exit/error mapping, and supported command parameters. Keep local execution explicit.
- **Collector/state:** own collection cadence, in-flight request coalescing, last-good snapshots, staleness metadata, and bounded metric history. Do not let individual screens spawn duplicate polling loops.
- **Textual presentation:** own screens, widgets, focus, keyboard navigation, resize, accessibility, notifications, and terminal rendering. It consumes application state/events and never executes PVM commands directly.
- **Diagnostics:** application logs and PVM audit-reader policy remain distinct. Redact credentials at creation boundaries, not as a best-effort final filter.

## 3. Proposed dependency graph

```text
cli ───────────────> application/use cases ─────────> domain
                         │                               ▲
Textual presentation ────┘                               │
                         ▼                               │
infrastructure/local_pvm ── implements provider port ───┘
                         │
              local sbell + pvm-running-vms

collector/state ──> provider port + domain snapshots
Textual view ─────> application read models/events; no infrastructure imports
```

Allowed dependencies point inward: domain imports no UI, subprocess, Pydantic settings, or PVM-specific modules. Application depends on domain and provider/store ports. Infrastructure implements those ports. Presentation calls application use cases; it does not bypass them to access the provider. Bootstrap is the composition root. Runtime dependency direction should be tested/linted where practical.

## 4. Recommended libraries and versions

Point-in-time PyPI results and `Requires-Python` are recorded in `03-technology-evaluation.md`. All versions below are **compatibility baselines to evaluate**, not final pins. A lockfile and actual platform build/test matrix are required before release.

| Area | Proposal | Status |
|---|---|---|
| TUI | Textual 8.2.8 candidate; Rich 15.0.0 via Textual, direct only if used | Conditional adopt after actual-screen/performance/package prototype |
| CLI | Typer 0.27.3 candidate | Adopt process-level command surface after grammar/design spike |
| Boundary validation | Pydantic 2.14.2 candidate, selectively | Adopt only at untrusted XML/settings boundaries, benchmark bulk payloads |
| Local metrics | psutil 7.2.2 candidate | Defer; PVM metrics already include many local metrics; identify missing approved fields first |
| Persistence | stdlib sqlite3; SQLAlchemy 2.1.6 and Alembic 1.20.1 deferred | No app DB justified; avoid ORM/migration dependencies before durable state need |
| Dependency/runtime management | uv 0.13.6 for development/build | Adopt in developer/CI process; keep off target unless runtime distribution requires it |
| Tests | pytest 9.2.0 | Adopt for offline test suite |
| Async tests | pytest-asyncio 1.4.1 | Optional only if direct asyncio tests need it; Textual Pilot may cover UI tests |
| Generated tests | Hypothesis 6.170.14 | Optional after pure parser/selector contracts are stable |
| Static quality | Ruff 0.17.3, Pyright 1.1.414 | Adopt as development/CI tools with configuration spike |
| Logging | stdlib `logging`; structlog 26.1.0 deferred | Start with redacted contextual stdlib logs; revisit if structured sink requirements justify it |
| Retries | no general retry library; tenacity 9.2.1 deferred | Require idempotency policy first; never blindly retry mutation |
| Paths/settings | stdlib XDG/env handling; platformdirs 4.14.0 and pydantic-settings 2.16.2 deferred | Linux-only and short current env config do not justify these yet |
| HTTP | HTTPX 0.28.1 deferred | No HTTP transport selected; remote provider explicitly deferred |
| Packaging | PyInstaller 6.22.3 candidate | Prototype one-directory only after PVM OS/libc discovery |

The number/version set is not a recommendation to add every package. Dependency rationale, overhead, Python metadata and standard-library alternatives are in `03-technology-evaluation.md`.

## 5. Runtime and packaging strategy

- Product target Python 3.12+; do not depend on or replace an unknown PVM system interpreter.
- First profile target PVM Linux distribution, architecture, glibc, executable filesystem policy, permissions, and local CLI versions without modifying it.
- Prototype Python 3.12+ PyInstaller one-directory builds on the oldest supported Linux baseline. Test the bundle on representative target systems. Keep vendor `sbell` and `pvm-running-vms` as explicit host dependencies.
- Build and publish per architecture/base compatibility group; sign/checksum artifacts and include update/rollback ownership in operations design.
- If PyInstaller is incompatible with vendor policy or host libc, evaluate a privately managed standalone interpreter environment. Do not assume uv is required to run the product.
- Avoid one-file extraction until target `/tmp`/noexec and cold-start behavior are tested.

See `02-python-runtime.md`; this is conditional pending target facts.

## 6. Data collection design

- Local `LocalPvmProvider` exposes a small, typed interface for batch inventory, host/cluster/local-node status, detailed metrics, on-demand VM details, and explicitly approved auxiliary reads.
- Inventory uses the existing single `user/objects` VM query plus the separate `pvm-running-vms` enrichment source. Merge on normalized UUID. Do not fetch detail one VM at a time for the inventory screen.
- Host metrics and `sball/show` status are separate in current source. Collect only when requested by active views; consolidate repeated calls by sharing one collection result across consumers.
- Keep detail and license retrieval on demand. Establish independent cadence only for data that needs periodic refresh.
- Start with sequential bounded read-only collection; measure sbell daemon safety and latency before concurrent collection. Serialize mutations and never use generic retry on an ambiguous action outcome.
- Every source result records collected-at, source, success/error, and supported/missing fields. A provider adapter must report partial failures rather than flattening them into empty healthy data.

Specific PVM uncertainties and facts are in `04-pvm-interface-analysis.md`.

## 7. State management and snapshots

- Publish an immutable normalized `LocalSnapshot` containing only currently known domains, section timestamps, and freshness/error metadata.
- Keep the last successful value **per section** in a bounded in-memory store. On a failed poll, retain the last good data and mark its age/staleness; on first failure show unavailable. Never turn collection failure into empty inventory or healthy zero metrics.
- Use a single refresh scheduler per app, with in-flight request coalescing and no unbounded queued polls. Pause/reduce collection for views that do not require continuous updates.
- Keep a short bounded history for rate/trend calculations only. Persist state only for a confirmed requirement; the current UI does not need an ORM database to render a current snapshot.
- Pydantic may validate/normalize adapter output; benchmark object and memory overhead on actual list sizes. Use one published representation, not redundant mutable dictionaries plus copies.

## 8. Rendering strategy

- Textual owns terminal redraw and terminal-cell diff rendering. Domain change detection can suppress unchanged application events, but no custom cell-level dirty tracking is proposed.
- Maintain stable table/screen widget identity and update only relevant rows/sections where Textual API supports it. On inventory refresh, preserve selection by VM UUID rather than list index.
- Use the built-in resize/layout system, focus/navigation, notifications, progress, and DataTable primitives. Define narrow-terminal layout, accessibility and error persistence explicitly.
- Benchmark representative and upper-bound inventories and measure memory/CPU. If table size is too large, add pagination/windowing based on evidence rather than preemptively building a custom table.
- A responsive UI does not imply parallel PVM calls: long blocking `sbell` calls must run in workers so the UI remains responsive, while collection concurrency remains controlled.

## 9. Action execution architecture

- Represent each user request as an explicit operation intent with action, resolved immutable target set, authorization/confirmation result, operation ID, and per-target outcome.
- Resolve and display all targets before mutation. Reject mixed valid/invalid selector input by default. Preserve PVM errno and safe diagnostic detail for every failed target.
- Unattended destructive operations must fail closed by default; if approved automation requires them, use a deliberate explicit flag/policy with auditability rather than implicit non-TTY acceptance.
- Serialize mutating operations initially. Show progress/result in Textual; do not block the event loop. Apply state applicability only as local guidance/guard according to agreed policy; PVM remains final authority.
- Treat timeout after a mutation as ambiguous completion. Refresh current state before offering a retry. No automatic mutation retry without a documented idempotency token/contract.

## 10. Security recommendations

- Resolve supported credential transport with PVM maintainers. Current command-line password/token exposure must be treated as unresolved/high risk; do not invent a safer sbell argument mode.
- Keep minimum privilege scoped to invoking the documented PVM client. Validate executable path, owner, environment and sudo rules; never use `shell=True` for command composition.
- Serialize XML safely and validate identifiers. Keep secrets out of exception text, logs, traces, test data and generated reports.
- Secure session material at creation (directory/file permissions, ownership, atomic write, no symlink surprises) and make persistence failures visible without printing token data.
- Enforce explicit destructive confirmation/automation policy; reject partial target resolution; report per-target results; distinguish definitive failure from timeout/unknown outcome.
- Bound output, process duration and concurrent requests. Reap/terminate subprocesses correctly. Keep PVM audit reading read-only and separate from application diagnostics.

Prioritized source findings and verification tasks are in `06-security-and-reliability.md`.

## 11. Testing strategy

1. **Domain unit tests:** state mapping, immutable snapshot equality, stale/partial status, action policy, selector grammar, counter-delta edge cases.
2. **Adapter/parser tests:** captured, redacted XML and table fixtures; malformed/truncated XML; unknown fields; missing/unsupported fields; PVM version fixtures.
3. **Process integration tests:** fake executable scripts for argv contract, no-shell handling, timeout, output/exit-code combinations, descendant cleanup, and error mapping. Never use real credentials.
4. **Application tests:** fake provider and deterministic clocks to test request coalescing, cadence, last-good retention, partial failure, mutation serialization, cancellation, and per-target results.
5. **Textual tests:** Textual Pilot for navigation, focus, selection preservation, notifications, resize/layout and worker responsiveness; supplement with terminal matrix checks.
6. **Property-based tests (optional):** Hypothesis for XML-derived numeric/state data, selector parsing, and snapshot diff invariants after contracts stabilize.
7. **Authorized host integration:** read-only checks against explicitly supported PVM versions; separate opt-in destructive tests on disposable VMs only. Smoke tests must document session/credential side effects.
8. **Quality gates:** pytest, Ruff, Pyright and locked dependency sync in CI; build and launch PyInstaller artifact in Linux compatibility jobs. Record test coverage goals after baseline.

## 12. Future Multi-Node extension points (deferred)

The current domain should describe a node by stable identity and facts, not by how it was reached. The application collector depends on a `NodeDataProvider`/provider port returning the same normalized snapshot types. `LocalPvmProvider` is the only implementation in this phase. A later `RemoteNodeProvider` could return those same normalized node snapshots through an approved remote transport.

Application use cases operate on provider-neutral Node/Cluster/VM snapshots and freshness/errors. Screens render those snapshots and should not branch on local-vs-remote transport. Composition/bootstrap may later register multiple provider instances and explicit node identity, but no remote protocol, connection pool, credentials, retries, or multi-node scheduler is to be implemented now.

Do not promise that local PVM interfaces can provide data for every remote node. Each provider may expose only verified capability/data coverage; the domain must represent partial or unsupported fields without pretending they are available.

## 13. Architecture Decision Records

The ADR index at [`adr/README.md`](adr/README.md) is authoritative for titles, decision ownership, statuses, change summary, unresolved evidence, and consistency review. ADR statuses are mixed: some record accepted product constraints; technology and implementation choices remain conditional, proposed, or deferred. None authorizes implementation by itself.

The set is:

- `0001-tui-framework.md` — conditional Textual + Rich prototype
- `0002-python-runtime.md` — accepted Python 3.12+ target; runtime delivery remains open
- `0003-dependency-management.md` — accepted workflow/tool choices; dependency groups and pins
- `0004-data-collection.md` — logical batching, UUID merge, no N+1 and read coalescing
- `0005-snapshot-state-store.md` — independent section lifecycle and last-good snapshots
- `0006-diff-rendering.md` — semantic change detection vs terminal-cell diff rendering
- `0007-async-execution.md` — bounded workers, subprocess lifecycle and ambiguous outcomes
- `0008-persistence.md` — separate session credential storage from app persistence
- `0009-pvm-adapter-boundary.md` — local provider contract and bounded cluster claims
- `0010-packaging.md` — conditional artifact, offline deployment, signing and rollback
- `0011-application-layer-boundaries.md` — accepted modular-monolith dependency rules
- `0012-security-and-mutation-safety.md` — proposed secret and mutation policy
- `0013-error-taxonomy-and-operation-outcomes.md` — proposed typed failures/outcomes
- `0014-collection-scheduling-and-freshness-policy.md` — proposed cadence/freshness ownership

## 14. Unresolved decisions and risks

1. Actual supported PVM versions, Linux distribution, architecture, glibc baseline, host Python availability and filesystem/installation constraints.
2. PVM owner confirmation of `sbell` supported command/error/exit contract and safe credential delivery; full cluster membership/quorum contract is unknown.
3. Target upper-bound VM count, refresh latency, acceptable stale time, local host overhead budget and Textual memory/CPU measurements.
4. Whether application persistence is required at all, and exactly what should be persisted.
5. Exact CLI command grammar, scripted/destructive action policy, role/authorization model, audit retention and user model.
6. PyInstaller vendor-policy acceptability, native library support, offline installation, artifact signing/update/rollback ownership.
7. Whether psutil fills a confirmed monitoring gap; whether direct Rich, Hypothesis, pytest-asyncio, platformdirs, HTTPX, structlog, tenacity, SQLAlchemy/Alembic are justified.
8. Whether the local PVM interface exposes enough verified cluster/member data for the promised cluster-aware views. Preserve `sball_state=quorate` as the valid indication that Sball reports the cluster as Quorate; do not interpret it as proof that every node is healthy/reachable or that complete membership data is available.
9. Whether Textual DataTable meets actual inventory scale and terminal constraints.

## Recommended next phase

Before implementation or OpenSpec, obtain target-PVM facts and PVM-owner protocol confirmation, resolve the high-impact safety/security policies, then run small isolated prototypes: (a) Textual table/worker/diff behavior against a synthetic large inventory, (b) local adapter subprocess contract using fake binaries and redacted host captures, and (c) Python 3.12+ PyInstaller one-directory compatibility on the oldest supported Linux baseline. Bring measured results and unanswered questions back for explicit architecture approval.

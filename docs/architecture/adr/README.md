# Architecture Decision Record Index and Review Summary

**Project:** plaivid_CLI  
**Review:** ADR revision after first architecture review  
**Date:** 2026-10-30  
**Status:** Decision proposals and explicit scope constraints; this is **not Architecture Baseline v1.0**.

## Status definitions

- **Accepted:** an explicitly established product/architecture constraint is recorded. Acceptance is limited to the stated scope; it does not approve untested implementation details.
- **Proposed:** a design direction awaits explicit architecture/product approval and required evidence.
- **Conditional:** a candidate may proceed to prototype, but cannot be accepted unless listed criteria/evidence pass.
- **Deferred:** intentionally not selected for current scope; reconsider only after the listed trigger/requirement.

No ADR in this set authorizes application implementation. `Accepted` entries record supplied constraints/boundaries, not proof that current source conforms.

## ADR index

| ADR | Title | Status | Decision ownership / scope |
|---|---|---|---|
| [0001](0001-tui-framework.md) | TUI Framework | **Conditional** | Product/architecture owner selects framework after UI/performance/package prototype; UI technical lead supplies results. |
| [0002](0002-python-runtime.md) | Python Runtime Target | **Accepted** (Python 3.12+ constraint); delivery open | Product/platform owner sets target; release engineering validates supported runtime matrix. Packaging format is ADR 0010. |
| [0003](0003-dependency-management.md) | Dependency Groups and Tooling | **Accepted** (uv/pytest/Ruff/Pyright workflow choices); exact pins/runtime set conditional | Engineering owner sets dependency groups and lock policy; release engineering validates shipped set. |
| [0004](0004-data-collection.md) | Logical Batch Collection and Inventory Merge | **Proposed** | Application/data owner defines logical collection contract; PVM maintainer confirms source behavior. |
| [0005](0005-snapshot-state-store.md) | Section Snapshots and In-Memory State Store | **Proposed** | Application/domain owner defines section lifecycle, last-good retention and bounded history. |
| [0006](0006-diff-rendering.md) | Semantic Change Detection and Terminal Rendering | **Conditional** | Application owner owns semantic data-change rules; TUI owner owns terminal-cell rendering strategy. |
| [0007](0007-async-execution.md) | Bounded Worker and Subprocess Lifecycle | **Proposed** | Application/platform owner chooses worker/process model; PVM owner validates process semantics. |
| [0008](0008-persistence.md) | Session Credential Storage vs Application Persistence | **Deferred** (application DB); session storage unresolved | Security/product owner decides session lifecycle/storage; application owner decides non-secret persistence. |
| [0009](0009-pvm-adapter-boundary.md) | Local PVM Provider Boundary and Future Providers | **Conditional** | Domain/application owner defines narrow local port; PVM owner validates command/schema and cluster coverage. |
| [0010](0010-packaging.md) | Linux Packaging and Offline Deployment | **Conditional** | Release/platform owner chooses artifact lifecycle; security approves trust/signing; PVM operations/vendor approves compatibility. |
| [0011](0011-application-layer-boundaries.md) | Application Layer and Dependency Boundaries | **Accepted** (modular monolith/layer rules); package decomposition proposed | Product/architecture owner owns layering constraints; maintainers enforce import direction. |
| [0012](0012-security-and-mutation-safety.md) | Security and Mutation Safety Policy | **Proposed** | Product/security owner decides credential and unattended-operation policy; PVM admin confirms auth/privilege behavior. |
| [0013](0013-error-taxonomy-and-operation-outcomes.md) | Error Taxonomy and Operation Outcomes | **Proposed** | Application owner defines typed categories/outcomes; operations/support owner approves diagnostics. |
| [0014](0014-collection-scheduling-and-freshness-policy.md) | Collection Scheduling and Freshness Policy | **Proposed** | Product/application owner defines cadence/freshness; PVM operations owner approves overhead/load budgets. |

## Change summary

### Revised ADRs 0001–0010

- **0001:** Added explicit prototype acceptance criteria across responsiveness, state correctness, diff/flicker, table scale, terminal behavior, operation feedback and packaged runtime. Numeric performance budgets must be approved before test results can pass; Textual remains conditional.
- **0002:** Separated Python runtime requirement from packaging. Python 3.12+ is recorded as an accepted target constraint; runtime delivery is open. Added target distribution, architecture, glibc, permissions, mount and vendor-policy evidence requirements.
- **0003:** Split runtime, development/build and optional test dependencies; distinguished approved workflow tools from conditional runtime candidates and exact version pins.
- **0004:** Defined logical inventory batching as one all-VM `user/objects` query plus separate running-VM enrichment, UUID-based merge, on-demand detail, no N+1 VM queries, and in-flight logical request sharing.
- **0005:** Defined independent section lifecycle, wall/monotonic time, status/age, last-good retention, valid-empty vs unavailable, partial publication, and bounded in-memory history.
- **0006:** Separated semantic application/domain change detection from Textual terminal-cell differential rendering; Textual owns terminal diff if accepted.
- **0007:** Added bounded worker/pending work, single-flight reads, serialized mutations, shutdown/process cleanup, cancellation limitations, and ambiguous post-dispatch mutation outcomes.
- **0008:** Separated session-token/credential storage from app-owned preferences/telemetry and from the externally owned read-only PVM audit DB. Current JSON cache is not treated as approved secure storage.
- **0009:** Narrowed the local provider contract and assigned process/protocol work to Infrastructure. Preserved `sball_state=quorate` as the valid signal that Sball reports Quorate while explicitly not equating it with all-node health/reachability or complete membership.
- **0010:** Separated package artifact lifecycle from runtime choice; added offline delivery, integrity/signing trust, staged updates, prior-version retention and rollback ownership. PyInstaller remains conditional.

### Added ADRs 0011–0014

- **0011 — Application Layer and Dependency Boundaries:** records required Presentation → Application → Domain dependencies, Infrastructure port implementations, and bootstrap composition root; explicitly states current source does not yet conform. No microservices or generic plugin system.
- **0012 — Security and Mutation Safety Policy:** owns secret/least-privilege requirements and proposes fail-closed non-TTY mutation, all-or-nothing target resolution, explicit confirmation, serialized mutation and no blind retry.
- **0013 — Error Taxonomy and Operation Outcomes:** distinguishes process, protocol, PVM, auth, collection, policy and operation errors; defines per-target definite/partial/unknown outcomes and redacted diagnostics.
- **0014 — Collection Scheduling and Freshness Policy:** owns demand/cadence/stale thresholds and active-view policy; explicitly delegates batch shape, state representation and worker execution to ADRs 0004, 0005 and 0007.

## Unresolved decisions and required evidence

1. **PVM target matrix:** supported PVM versions, Linux base distributions, architectures, glibc/native library baseline, executable paths/permissions/mount policy, and vendor support for a separately packaged CLI. Required by ADRs 0002/0010.
2. **Local interface contract:** redacted real outputs, field/schema compatibility, permissions, exit/stderr behavior, command timing, and PVM owner confirmation of `user/objects`, `pvm-running-vms`, `sball/show`, and `monitoring/metrics`. Required by ADRs 0004/0009/0013.
3. **Cluster facts:** confirm source/time for Sball's `quorate` status and determine whether any supported local output exposes complete membership/per-node health. Preserve “Sball reports Quorate”; do not infer all-node health. Required by ADR 0009.
4. **Credentials and privileges:** verify a supported safer credential-input path or acceptably mitigated process-argument exposure; define token cache policy, sudo/executable allowlist, process visibility and least privilege. Required by ADRs 0008/0012.
5. **Mutation policy:** approve interactive confirmation details, noninteractive automation semantics, all-or-nothing selectors, per-target continuation, and timeout/unknown outcomes. Required by ADRs 0012/0013.
6. **TUI/profiling:** supported terminal matrix, inventory size envelope, quantitative latency/CPU/RSS budgets, resize/flicker results, and responsiveness under slow local calls. Required by ADRs 0001/0006/0007.
7. **Collection SLAs:** per-section freshness targets, polling intervals, idle/background policy, backoff behavior, and measured host/PVM overhead. Required by ADRs 0004/0005/0014.
8. **Persistence:** whether session reuse is needed and how to protect tokens; whether any non-secret preferences/history/operation journal must persist; retention/backup/schema lifecycle. Required by ADR 0008.
9. **Dependency/runtime policy:** final runtime dependencies, supported versions, lock update cadence, target wheel availability, PyInstaller compatibility, artifact signing key/trust, offline transfer/update/rollback operator ownership. Required by ADRs 0002/0003/0010.
10. **Testing/release controls:** CI/platform matrix, host-test authorization, acceptable destructive integration test policy, coverage target, SBOM/signing requirements and incident/update ownership.

## Consistency report

### Boundaries

ADR 0011 is the single owner of layer dependency direction. ADR 0009 owns the provider port's PVM scope and capability semantics; it explicitly defers to ADR 0011 for dependency direction. ADR 0004 owns logical batch composition, UUID merging, no N+1 and read coalescing identity. ADR 0014 owns when data is due and freshness/cadence policy. ADR 0005 owns section result/state shape and last-good retention. ADR 0007 owns worker and subprocess lifecycle. These are complementary responsibilities, not competing refresh implementations.

### Rendering and change detection

ADR 0006 separates semantic state comparison from terminal-cell rendering. ADR 0005 defines data snapshots; ADR 0011 prohibits Domain/PVM/UI coupling; ADR 0001 conditionally selects Textual. There is no second custom dirty-cell rendering decision.

### Runtime and packaging

ADR 0002 owns Python 3.12+ target and runtime compatibility requirements. ADR 0010 owns artifact form, offline installation, signing/checksum trust, updates and rollback. ADR 0003 owns dependency groups/lock workflow. PyInstaller remains a conditional packaging candidate, not a runtime decision already accepted.

### Persistence and secrets

ADR 0008 owns separation of session storage, application persistence and PVM audit data. ADR 0012 owns secret protection and mutation safety requirements, not database technology. Application SQLite/SQLAlchemy/Alembic remain deferred absent a concrete use case.

### Quorum and cluster health

ADR 0009 accurately preserves `sball_state=quorate` as Sball's valid Quorate indication, with source/time. It does not claim complete membership or all-node health/reachability. ADR 0013/0014 require errors/freshness for unavailable or stale evidence. No contradiction remains between quorum signal and cluster completeness.

### Status and evidence

Accepted entries are limited to explicit supplied constraints/tool choices and required layer rules. Textual, worker model, provider schema, collection intervals, and packaging remain Conditional or Proposed because target behavior/performance is not verified. Deferred persistence is not described as rejected permanently. No ADR claims target-host validation occurred.

### Deliberate cross-references

- **0001 ↔ 0006/0007/0010:** UI acceptance depends on semantic update behavior, worker responsiveness and package tests; each ADR owns its respective area.
- **0002 ↔ 0010:** runtime version/compatibility versus package artifact lifecycle.
- **0004 ↔ 0005 ↔ 0014 ↔ 0007:** batch/request identity versus section model/retention versus scheduling/freshness versus execution lifecycle.
- **0008 ↔ 0012:** storage separation versus secret protection.
- **0009 ↔ 0011:** provider capability/contract versus dependency direction.
- **0012 ↔ 0013 ↔ 0007:** safety policy versus outcome taxonomy versus worker/cancellation mechanics.

No Architecture Baseline v1.0 is created by this revision. Implementation and OpenSpec remain pending explicit approval.

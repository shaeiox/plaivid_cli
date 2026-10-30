# Architecture Decision Record Index

**Project:** plaivid_CLI  
**Reviewed:** 2026-10-30  
**Implementation status:** See [`FINAL_IMPLEMENTATION_AUDIT.md`](../FINAL_IMPLEMENTATION_AUDIT.md) for local remediation and test evidence. This index records design intent; it is not proof of PVM-host behavior or a release approval.

## Status meanings

- **Accepted:** an owner decision or project constraint recorded within the listed scope.
- **Implemented locally:** the active code follows the recorded policy to the extent observable with fake-based tests.
- **Conditional / Proposed:** a design choice or host-dependent behavior still needs owner approval or evidence.
- **Deferred:** intentionally not selected for the current scope.

No ADR authorizes production access. The existing OpenSpec Change is `implement-complete-plaivid-cli`; it includes read, CLI/TUI, and lifecycle implementation. All real-PVM behavior remains pending manual validation. Credential argv exposure is default-deny and remains a separate blocked owner decision.

## ADR index

| ADR | Title | Status in this implementation | Remaining decision/evidence |
|---|---|---|---|
| [0001](0001-tui-framework.md) | TUI Framework | Conditional | Textual terminal/platform compatibility and owner approval. |
| [0002](0002-python-runtime.md) | Python Runtime Target | Accepted: Python >=3.12 | Python 3.12 verification is blocked in this workspace; keep system Python unchanged. |
| [0003](0003-dependency-management.md) | Dependency Groups and Tooling | Implemented locally | Release dependency lock/pinning and supported environment matrix. |
| [0004](0004-data-collection.md) | Logical Batch Collection and Inventory Contract | Implemented locally | PVM query/schema/source semantics require owner evidence. |
| [0005](0005-snapshot-state-store.md) | Section Snapshots and In-Memory State | Implemented locally | Host load/freshness budgets remain unmeasured. |
| [0006](0006-diff-rendering.md) | Semantic Change Detection and Terminal Rendering | Conditional | Product need and terminal behavior. |
| [0007](0007-async-execution.md) | Bounded Worker and Subprocess Lifecycle | Implemented locally | POSIX fake process-tree test passes; actual wrapper/sudo behavior is pending. |
| [0008](0008-persistence.md) | Session Credential Storage vs Application Persistence | Deferred (application DB); session cache implemented | Owner security decision on plaintext token cache and credential argv. |
| [0009](0009-pvm-adapter-boundary.md) | Local PVM Provider Boundary and Future Providers | Implemented locally | Exact target command/schema contracts remain pending. |
| [0010](0010-packaging.md) | Linux Packaging and Offline Deployment | Partially implemented | Wheel build is locally testable; Python 3.12 and target ABI/install validation remain pending. |
| [0011](0011-application-layer-boundaries.md) | Single Application Package and Layer Boundaries | Implemented locally | Audit/test evidence is in the final audit report. |
| [0012](0012-security-and-mutation-safety.md) | Security and Mutation Safety Policy | Implemented locally; credential transport blocked | Credential argv threat-model acceptance; PVM action/authorization semantics. |
| [0013](0013-error-taxonomy-and-operation-outcomes.md) | Error Taxonomy and Operation Outcomes | Implemented locally | Positive/negative response semantics remain pending PVM evidence. |
| [0014](0014-collection-scheduling-and-freshness-policy.md) | Collection Scheduling and Freshness Policy | Implemented locally | Product-approved freshness/cadence budgets and host load evidence. |

## Ownership and implementation notes

Bootstrap is the single composition root. `CollectionCoordinator` owns read admission, collection, section status/last-good publication, and freshness. `OperationCoordinator` owns mutation admission, serialized dispatch, and outcomes. Infrastructure owns bounded child execution. CLI and TUI are presentations; pure secret redaction is in the domain layer. The retired `actions/`, `commands/`, and root-level legacy runtime modules remain checkout-only and are excluded from the built distribution.

Inventory object state and process observations remain separate. Truncated process-helper output is partial; a partial process list is not negative evidence for absence. `sball_state=quorate` means only that Sball reports Quorate. No broader health or membership guarantee is inferred.

After dispatch, the current repository has no verified PVM contract proving acceptance or completion. Therefore every returned response is `OUTCOME_UNKNOWN`, bulk execution stops, later targets are `NOT_STARTED`, and no automatic retry occurs. `COMMAND_ACCEPTED_UNCONFIRMED` remains a representable outcome for a future evidence-backed mapping, not a claim about current responses.

Credential/password/token arguments remain a sensitive exposure. `PLAIVID_ALLOW_CREDENTIAL_ARGV` is disabled by default; the explicit opt-in acknowledges risk but does not mitigate it. No undocumented stdin/environment/file-descriptor transport is invented. Owner/security review is required before authenticated PVM validation.

## Validation boundary

Unit, parser, subprocess, CLI, TUI, and package tests use fake commands/providers, fixtures, and temporary files. They do not prove PVM response semantics, host permissions, Sball behavior, vendor support, or Linux distribution compatibility. Those checks remain **PENDING MANUAL PVM VALIDATION** in [`docs/REAL_PVM_VALIDATION.md`](../../REAL_PVM_VALIDATION.md). Do not access production hosts or run lifecycle tests outside the separately approved owner procedure.

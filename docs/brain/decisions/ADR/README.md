# Architecture Decision Records — index

**Purpose:** one place to find architectural decisions without duplicating their content.
Navigation: [`../../README.md`](../../README.md) ·
[`../../architecture/ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md) ·
[`../../maintenance/DOCUMENTATION_AUDIT.md`](../../maintenance/DOCUMENTATION_AUDIT.md).

## Status meanings (from the existing ADR index)

- **Accepted:** an owner decision or project constraint recorded within the listed scope.
- **Implemented locally:** the active code follows the recorded policy to the extent observable
  with fake-based tests.
- **Conditional / Proposed:** a design choice or host-dependent behavior still needs owner
  approval or evidence.
- **Deferred:** intentionally not selected for the current scope.

Existing index and ownership notes: `docs/architecture/adr/README.md`. Its own warning applies
here: "This index records design intent; it is not proof of PVM-host behavior or a release
approval." Real-PVM behavior remains PENDING MANUAL PVM VALIDATION in
`docs/REAL_PVM_VALIDATION.md`.

## Existing ADRs (authoritative, pre-existing)

These files are **not** duplicated into `docs/brain/`. Read them at their original paths.

| ADR | Title | Status in existing index |
|---|---|---|
| [`0001`](../../../architecture/adr/0001-tui-framework.md) | TUI Framework | Conditional |
| [`0002`](../../../architecture/adr/0002-python-runtime.md) | Python Runtime Target | Accepted: Python >=3.12 |
| [`0003`](../../../architecture/adr/0003-dependency-management.md) | Dependency Groups and Tooling | Implemented locally |
| [`0004`](../../../architecture/adr/0004-data-collection.md) | Logical Batch Collection and Inventory Contract | Implemented locally |
| [`0005`](../../../architecture/adr/0005-snapshot-state-store.md) | Section Snapshots and In-Memory State | Implemented locally |
| [`0006`](../../../architecture/adr/0006-diff-rendering.md) | Semantic Change Detection and Terminal Rendering | Conditional |
| [`0007`](../../../architecture/adr/0007-async-execution.md) | Bounded Worker and Subprocess Lifecycle | Implemented locally |
| [`0008`](../../../architecture/adr/0008-persistence.md) | Session Credential Storage vs Application Persistence | Deferred (application DB); session cache implemented |
| [`0009`](../../../architecture/adr/0009-pvm-adapter-boundary.md) | Local PVM Provider Boundary and Future Providers | Implemented locally |
| [`0010`](../../../architecture/adr/0010-packaging.md) | Linux Packaging and Offline Deployment | Partially implemented |
| [`0011`](../../../architecture/adr/0011-application-layer-boundaries.md) | Single Application Package and Layer Boundaries | Implemented locally |
| [`0012`](../../../architecture/adr/0012-security-and-mutation-safety.md) | Security and Mutation Safety Policy | Implemented locally; credential transport blocked |
| [`0013`](../../../architecture/adr/0013-error-taxonomy-and-operation-outcomes.md) | Error Taxonomy and Operation Outcomes | Implemented locally |
| [`0014`](../../../architecture/adr/0014-collection-scheduling-and-freshness-policy.md) | Collection Scheduling and Freshness Policy | Implemented locally |

**Known conflict:** `docs/architecture/adr/0010-packaging.md` proposes a conditional
PyInstaller one-directory artifact, while the implemented build is a setuptools wheel
(`pyproject.toml`, `setup.py`, `README.md`). See
[`../../workflows/BUILD.md`](../../workflows/BUILD.md) and
[`../../maintenance/DOCUMENTATION_AUDIT.md`](../../maintenance/DOCUMENTATION_AUDIT.md).

## Brain-local ADRs

| ADR | Subject | Status |
|---|---|---|
| [`0001-strict-wall-clock-chart-window.md`](0001-strict-wall-clock-chart-window.md) | Strict 60-second wall-clock chart window and dynamic Y scale | **Implementation-observed**, documented 2026-11-08; not a recorded owner decision |
| [`0002-brain-as-agent-entry-point.md`](0002-brain-as-agent-entry-point.md) | Model-independent `docs/brain/` knowledge base as the agent entry point | **Implemented**, documented 2026-11-08 as part of the knowledge-base task |

## Recorded decisions vs newly documented observations

- Rows in the "Existing ADRs" table are **decisions actually recorded** by the project before
  this knowledge base was created. Their statuses come verbatim from
  `docs/architecture/adr/README.md`.
- Brain-local ADR 0001 is an **observation of current implementation** with test evidence; it
  explicitly does not claim an owner decision was made.
- Brain-local ADR 0002 documents the decision embodied by this task's deliverables
  (`AGENTS.md`, `docs/brain/`, `.agents/skills/`, `scripts/validate_brain.py`), not a historical
  architecture decision.
- No ADR here authorizes production PVM access, credential transport changes, or a release.

## Adding an ADR

Use the structure: Title · Status · Context · Decision · Alternatives · Consequences · Related
modules · Date (only when verifiable). Cite source paths and symbols as evidence. Do not
reconstruct historical intent without a document or commit that supports it; label such entries
"implementation-observed" instead. Update this index and the brain README navigation.

---
name: architecture-analysis
description: Analyze plaivid_cli architecture, layers, boundaries, state ownership, and dependency direction from the knowledge base. Use before proposing structural changes, new modules, or new cross-layer dependencies.
---

# Architecture analysis

## Purpose

Determine whether a proposed change fits the existing architecture and which invariants it would
affect, using verified documentation plus targeted source verification.

## When to use

- Adding a module, package, port, worker, or new cross-layer dependency.
- Evaluating a refactor, an import-direction change, or a state-ownership change.
- Reviewing whether a design keeps the presentation/application/domain/infrastructure split.

## Required knowledge documents

- `docs/brain/architecture/SYSTEM_OVERVIEW.md` (capabilities, lifecycle, constraints)
- `docs/brain/architecture/ARCHITECTURE.md` (layers, communication, state, verified vs inferred)
- `docs/brain/architecture/COMPONENTS.md` (component responsibilities and interfaces)
- `docs/brain/architecture/DEPENDENCY_GRAPH.md` (boundaries, high-coupling modules, cycles)
- `docs/brain/architecture/DATA_FLOW.md` (runtime flows)
- `docs/brain/contracts/MODULE_CONTRACTS.md` (boundary contracts)
- `docs/brain/decisions/ADR/README.md` (existing decisions)
- `docs/brain/diagrams/component-architecture.mmd`, `docs/brain/diagrams/dependency-overview.mmd`

## Step-by-step procedure

1. Read `docs/brain/architecture/ARCHITECTURE.md` and identify the affected layers and their
   "must not import" rules.
2. Locate the owning component in `docs/brain/architecture/COMPONENTS.md`; note its public
   interface, dependencies, consumers, and tests.
3. Check `docs/brain/architecture/DEPENDENCY_GRAPH.md` for the fan-in/fan-out of any module you
   plan to touch and for the known type-only cycle in `presentation/charts/`.
4. Trace the runtime path in `docs/brain/architecture/DATA_FLOW.md`; identify state owners and
   concurrency lanes.
5. Verify the concrete boundary in `docs/brain/contracts/MODULE_CONTRACTS.md` and the enforced
   checks in `tests/unit/test_architecture_boundaries.py`.
6. Check `docs/brain/decisions/ADR/README.md` and the existing ADRs for a relevant recorded
   decision; distinguish a recorded decision from an implementation-observed behavior.
7. Confirm claims in the actual source files and tests; label anything unverified.

## Expected output

An architecture note: affected layers/components · dependency direction before/after · state
owner and concurrency impact · contracts and ADRs involved · invariants at risk · tests that
must run · explicit "Verified" / "Inferred" / "Unverified" labels.

## Validation criteria

- No proposed import violates the tested layer matrix.
- `bootstrap.py` remains the only universal wiring point unless the task explicitly changes it.
- New interfaces are expressed through `application/ports.py` `Protocol`s.
- Affected diagrams/documents are listed for update.
- `python scripts/validate_brain.py` and `python -m pytest -q tests/unit/test_architecture_boundaries.py`
  are the stated verification commands.

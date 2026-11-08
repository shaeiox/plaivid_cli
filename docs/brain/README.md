# Project brain — plaivid_cli

**Primary knowledge entry point for AI coding agents.** Read this after `AGENTS.md`.

## What the project does

`plaivid_cli` is a **Linux-local** command-line and [Textual](https://github.com/Textualize/textual)
TUI client for Plaivid PVM virtual machines. One-shot CLI commands and an interactive dashboard
read host/VM facts and submit six VM lifecycle actions. All PVM I/O goes through the configured
local `sbell` argv (and the `pvm-running-vms` process-evidence helper) via a bounded
`ProcessRunner`; there is no SSH client, remote collector, application-owned telemetry database,
or guessed PVM API. Missing measurements stay `None`/`N/A`, object-store VM state and local
process observations stay separate, and mutation outcomes are never claimed as completion
without evidence. Real-host behavior is **PENDING MANUAL PVM VALIDATION** in
`docs/REAL_PVM_VALIDATION.md`.

Verified entry point: `plaivid_cli/bootstrap.py::main`; composition root:
`plaivid_cli/bootstrap.py::build_runtime`. Start with
[`architecture/SYSTEM_OVERVIEW.md`](architecture/SYSTEM_OVERVIEW.md).

## How the knowledge base is organized

| Directory | Purpose | Key documents |
|---|---|---|
| [`architecture/`](architecture/ARCHITECTURE.md) | What the system is and how its layers behave | `SYSTEM_OVERVIEW.md`, `ARCHITECTURE.md`, `COMPONENTS.md`, `DATA_FLOW.md`, `DEPENDENCY_GRAPH.md` |
| [`codebase/`](codebase/REPOSITORY_MAP.md) | Where code lives | `REPOSITORY_MAP.md`, `FILE_CATALOG.md`, `MODULE_INDEX.md`, `ENTRYPOINTS.md`, `FEATURE_TO_FILE_MAP.md` |
| [`contracts/`](contracts/MODULE_CONTRACTS.md) | Boundaries, protocols, models | `MODULE_CONTRACTS.md`, `API_CONTRACTS.md`, `DATA_MODELS.md` |
| [`workflows/`](workflows/DEVELOPMENT.md) | How to work, build, test, release | `DEVELOPMENT.md`, `BUILD.md`, `TESTING.md`, `RELEASE.md` |
| [`decisions/ADR/`](decisions/ADR/README.md) | Recorded and observed architectural decisions | `README.md` (index into existing ADRs) |
| [`maintenance/`](maintenance/DOCUMENTATION_POLICY.md) | Keeping this brain accurate | `DOCUMENTATION_POLICY.md`, `DOCUMENTATION_AUDIT.md` |
| [`diagrams/`](diagrams/system-context.mmd) | Canonical Mermaid sources | `system-context.mmd`, `component-architecture.mmd`, `dependency-overview.mmd` |

Supporting, pre-existing knowledge (not duplicated here): `README.md`, `docs/ARCHITECTURE.md`,
`docs/REFERENCE.md`, `docs/ENVIRONMENT.md`, `docs/MONITORING_DASHBOARD.md`,
`docs/architecture/adr/`, `openspec/changes/`, `docs/REAL_PVM_VALIDATION.md`.

## Where an agent should start

1. Read `AGENTS.md` (the mandatory 11-step workflow). 2. Read this file. 3. Use the task
category table below. 4. Follow the remaining AGENTS.md steps in order: feature/architecture
docs → canonical files → targeted source and dependencies → tests and contracts → written
impact analysis → implementation → verification → brain updates. Do not substitute a shorter
checklist.

## Task-oriented navigation

| Task type | Read in this order |
|---|---|
| Implement or extend a user-visible feature | [`codebase/FEATURE_TO_FILE_MAP.md`](codebase/FEATURE_TO_FILE_MAP.md) → [`codebase/MODULE_INDEX.md`](codebase/MODULE_INDEX.md) → [`contracts/MODULE_CONTRACTS.md`](contracts/MODULE_CONTRACTS.md) → [`workflows/TESTING.md`](workflows/TESTING.md) |
| Fix a bug in a known area | `FEATURE_TO_FILE_MAP.md` → [`codebase/FILE_CATALOG.md`](codebase/FILE_CATALOG.md) → `TESTING.md` → affected contract |
| Understand overall design | [`architecture/SYSTEM_OVERVIEW.md`](architecture/SYSTEM_OVERVIEW.md) → [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) → [`architecture/COMPONENTS.md`](architecture/COMPONENTS.md) |
| Trace runtime behavior / debug a flow | [`architecture/DATA_FLOW.md`](architecture/DATA_FLOW.md) → [`codebase/ENTRYPOINTS.md`](codebase/ENTRYPOINTS.md) |
| Change an interface or dependency | [`architecture/DEPENDENCY_GRAPH.md`](architecture/DEPENDENCY_GRAPH.md) → [`contracts/MODULE_CONTRACTS.md`](contracts/MODULE_CONTRACTS.md) → `tests/unit/test_architecture_boundaries.py` |
| CLI/protocol/JSON/session question | [`contracts/API_CONTRACTS.md`](contracts/API_CONTRACTS.md) → [`codebase/ENTRYPOINTS.md`](codebase/ENTRYPOINTS.md) |
| Add or interpret a data field | [`contracts/DATA_MODELS.md`](contracts/DATA_MODELS.md) → `codebase/FILE_CATALOG.md` |
| Set up / run locally | [`workflows/DEVELOPMENT.md`](workflows/DEVELOPMENT.md) |
| Build a wheel / inspect packaging | [`workflows/BUILD.md`](workflows/BUILD.md) → [`workflows/RELEASE.md`](workflows/RELEASE.md) |
| Decide canonical vs legacy | [`codebase/MODULE_INDEX.md`](codebase/MODULE_INDEX.md) → [`codebase/REPOSITORY_MAP.md`](codebase/REPOSITORY_MAP.md) |
| Update or verify this brain | [`maintenance/DOCUMENTATION_POLICY.md`](maintenance/DOCUMENTATION_POLICY.md) → [`maintenance/DOCUMENTATION_AUDIT.md`](maintenance/DOCUMENTATION_AUDIT.md) |

## How to locate a feature

`codebase/FEATURE_TO_FILE_MAP.md` is the feature index. Each feature block lists its entry point,
main implementation, supporting modules, shared dependencies, data models, tests, contracts,
impact areas, protected files, and documentation references. Every path in that document is
verified by `scripts/validate_brain.py`. Use its feature headings as the search key; do not
grep the whole repository first.

## How to identify the relevant source files

- Prefer the **canonical** row in `codebase/MODULE_INDEX.md`. Active runtime lives in
  `plaivid_cli/presentation/`, `plaivid_cli/application/`, `plaivid_cli/domain/`,
  `plaivid_cli/infrastructure/` plus `plaivid_cli/bootstrap.py::build_runtime` and `plaivid_cli/config.py::load_settings`.
- A path under `plaivid_cli/legacy/` is retired, checkout-only, excluded from wheels, and must
  not be edited for runtime work (exception: explicit legacy task).
- `__init__.py` files with `__all__` are re-export facades; change the implementation module,
  not the facade. `plaivid_cli/presentation/tui/pages/overview/__init__.py::__getattr__` is a
  lazy compatibility facade.
- Import direction is enforced: domain → nothing internal; application → domain; infrastructure
  → domain; presentation → application/domain; `bootstrap.py` wires concrete adapters. See
  `architecture/DEPENDENCY_GRAPH.md`.

## Evidence conventions

- Paths are repository-relative, written in backticks. A token like
  `plaivid_cli/application/services.py::PlaividApplication` means "file and symbol" and is
  checked against the AST by the audit script. Dotted suffixes denote class members.
- Important claims carry an **Evidence:** line with source paths/symbols or test paths.
  "Verified" means derived from source/config/tests; "Inferred" or "Unverified" is labelled.
- Diagrams are Mermaid. Canonical `.mmd` sources are in `diagrams/`; flow-specific sequence
  diagrams are inline in `architecture/DATA_FLOW.md`.

## How to verify documentation freshness

```bash
python scripts/validate_brain.py                       # read-only; stdlib only
python scripts/validate_brain.py --verbose             # per-check detail
```

The audit checks the required tree, Markdown links, referenced paths, `path.py::Symbol`
evidence tokens, feature mappings, entry points, standalone and inline Mermaid diagrams, skill
definitions, `AGENTS.md`, legacy labels, and active→legacy imports. Add the dependency-stats
flag to recompute the AST-derived numbers in `architecture/DEPENDENCY_GRAPH.md`. Its results
and the last audit date are recorded in
`maintenance/DOCUMENTATION_AUDIT.md`. Also compare `git log --oneline -- plaivid_cli` with
`git log --oneline -- docs/brain` after source changes. If the code changed and no brain
document did, run the `documentation-maintenance` skill.

## Validation boundary

Local unit tests use synthetic fixtures, fake providers/process runners, temporary SQLite
files, and Textual Pilot. They do not prove PVM response semantics, host permissions, Sball
behavior, or Python 3.12 platform compatibility. See `docs/REAL_PVM_VALIDATION.md` and
`docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`.

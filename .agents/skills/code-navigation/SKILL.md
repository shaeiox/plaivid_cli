---
name: code-navigation
description: Locate the exact plaivid_cli module, symbol, test, or entry point for a task using the knowledge base, and resolve canonical vs legacy paths. Use for "where is X defined / who calls X" questions.
---

# Code navigation

## Purpose

Answer "where does this live?" with a verified repository-relative path and symbol, without a
repository-wide search.

## When to use

- A symbol, widget id, CLI command, section name, or environment variable needs an owner.
- A bug report names a UI label or command but not a file.
- You need the test or contract associated with a known module.

## Required knowledge documents

- `docs/brain/codebase/FILE_CATALOG.md` (path → symbols, inputs/outputs, deps, tests)
- `docs/brain/codebase/MODULE_INDEX.md` (canonical vs facade vs shim vs legacy)
- `docs/brain/codebase/ENTRYPOINTS.md` (commands, workers, handlers, timers)
- `docs/brain/codebase/FEATURE_TO_FILE_MAP.md` (feature perspective)
- `docs/brain/contracts/API_CONTRACTS.md` (CLI grammar, selectors, section names, JSON)
- `docs/brain/architecture/DEPENDENCY_GRAPH.md` (who depends on a module)

## Step-by-step procedure

1. Decide the lookup key: symbol name, CLI command, widget id, section name, feature, or
   error code.
2. For symbols/files: search `docs/brain/codebase/FILE_CATALOG.md`; note the key symbols,
   dependencies, and related tests. Confirm the path exists.
3. For commands/flags/exit codes/selectors/section names: use
   `docs/brain/codebase/ENTRYPOINTS.md` and `docs/brain/contracts/API_CONTRACTS.md`.
4. For startup/workers/handlers: use `docs/brain/codebase/ENTRYPOINTS.md`; for runtime order use
   `docs/brain/architecture/DATA_FLOW.md`.
5. For a feature-based question: use `docs/brain/codebase/FEATURE_TO_FILE_MAP.md`.
6. Resolve any result that is a FACADE or SHIM to its implementation module through
   `docs/brain/codebase/MODULE_INDEX.md`. Reject `plaivid_cli/legacy/` results for runtime work.
7. Only then open the specific source file and verify the symbol with a targeted search. If it
   is missing, record a documentation discrepancy.

## Expected output

`key → exact path (+ symbol) → responsibility → canonical/legacy status → consumers → related
tests → related contract`. For a missing symbol: a discrepancy note and the evidence checked.

## Validation criteria

- The returned path exists and the symbol resolves (use `path.py::Symbol` convention).
- A single canonical implementation is identified even when facades/duplicates exist.
- No legacy path is proposed for a runtime change.
- The answer cites the brain document used, not a blind grep.

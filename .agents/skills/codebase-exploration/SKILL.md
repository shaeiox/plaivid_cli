---
name: codebase-exploration
description: Explore the plaivid_cli repository in a documentation-first, bounded way. Use at the start of any task that requires finding where behavior lives, before reading source files broadly. Produces a scoped file list with canonical/legacy classification and evidence.
---

# Codebase exploration

## Purpose

Replace broad repository grepping with a deterministic, bounded exploration that starts from
`docs/brain/` and ends with a short list of files an agent actually needs to read.

## When to use

- A new task in an unfamiliar area of this repository.
- Before answering "where is X implemented?".
- Any time you are tempted to run a repository-wide search without a concrete symbol.

## Required knowledge documents

- `AGENTS.md` (mandatory workflow)
- `docs/brain/README.md` (navigation + task table)
- `docs/brain/codebase/REPOSITORY_MAP.md` (directory meaning)
- `docs/brain/codebase/MODULE_INDEX.md` (canonical vs legacy)
- `docs/brain/codebase/FEATURE_TO_FILE_MAP.md` (feature lookup)
- `docs/brain/codebase/FILE_CATALOG.md` (file details and related tests)

## Step-by-step procedure

1. Read `AGENTS.md`, then `docs/brain/README.md`; classify the task with its navigation table.
2. Identify the feature or capability. Look up its block in
   `docs/brain/codebase/FEATURE_TO_FILE_MAP.md`; copy its entry point, main implementation,
   supporting modules, and tests.
3. Check `docs/brain/codebase/MODULE_INDEX.md` for every candidate path: confirm it is
   CANONICAL. If it is LEGACY, FACADE, or SHIM, substitute the named canonical implementation.
4. Use `docs/brain/codebase/REPOSITORY_MAP.md` to confirm the directory's architectural role and
   `docs/brain/codebase/FILE_CATALOG.md` to get symbols, inputs/outputs, and dependencies.
5. Read only those source files plus the specific dependencies they import. Do not read
   unrelated packages or `plaivid_cli/legacy/`.
6. Read the named tests and the relevant contract in `docs/brain/contracts/`.
7. If a documented path is missing or a symbol does not exist, stop and record the
   discrepancy; do not guess an alternative.

## Expected output

A short report: task category · feature block used · canonical files to inspect · files
deliberately excluded (with reason, e.g. legacy/facade) · related tests · related contracts ·
any discrepancy found. Paths must be repository-relative.

## Validation criteria

- Every listed file exists (`python scripts/validate_brain.py` passes).
- No `plaivid_cli/legacy/` path appears in the canonical file list.
- At least one test and one contract document are named for the task.
- The number of source files to read is bounded and justified by the feature map.

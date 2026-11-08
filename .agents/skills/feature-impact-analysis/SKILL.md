---
name: feature-impact-analysis
description: Produce a pre-change impact analysis for a plaivid_cli feature, mapping affected canonical files, contracts, tests, protected files, and documentation. Use before editing code for a feature or bug fix.
---

# Feature impact analysis

## Purpose

Make the blast radius of a change explicit **before** implementation, so no contract, test, or
brain document is silently missed.

## When to use

- Any feature change or bug fix that touches more than one file.
- Before step 8 of the `AGENTS.md` workflow.
- When a request could plausibly be satisfied by editing a legacy or facade module.

## Required knowledge documents

- `AGENTS.md` (workflow steps 1–11)
- `docs/brain/codebase/FEATURE_TO_FILE_MAP.md` (primary index)
- `docs/brain/codebase/MODULE_INDEX.md` (canonical/legacy/facade/shim/overlap)
- `docs/brain/contracts/MODULE_CONTRACTS.md`, `docs/brain/contracts/API_CONTRACTS.md`,
  `docs/brain/contracts/DATA_MODELS.md`
- `docs/brain/workflows/TESTING.md` (regression suites)
- `docs/brain/maintenance/DOCUMENTATION_POLICY.md` (which docs to update)

## Step-by-step procedure

1. Find the exact feature block in `docs/brain/codebase/FEATURE_TO_FILE_MAP.md`. If none exists,
   find the closest capability and say so.
2. Enumerate: entry point, main implementation, supporting modules, shared dependencies, data
   models, and tests from that block; verify each path still exists.
3. Read the block's **Related contracts** and **Files that should NOT be modified** fields; keep
   the protected list intact.
4. Check `docs/brain/codebase/MODULE_INDEX.md` for OVERLAP pairs (e.g. `dynamic_top` vs
   `stable_top`, `body` vs `finish`, duplicated `EXIT_PARTIAL`, version constants) that the
   change could desynchronize.
5. Add cross-cutting checks: redaction for new output, section-name validity for new collection
   demand, layer import rules, and `tests/unit/test_architecture_boundaries.py` /
   `tests/unit/test_distribution.py` when imports or packages change.
6. List the brain documents that must be updated per
   `docs/brain/maintenance/DOCUMENTATION_POLICY.md`.
7. Write the impact analysis, then implement only the listed canonical files.

## Expected output

A table: change → affected canonical files → contracts touched → data models → tests to run →
protected files → brain documents to update → risks/unknowns. End with a go/no-go statement.

## Validation criteria

- Every path is verified and canonical; protected files are explicitly listed.
- At least one relevant test file and one contract document are named.
- Documentation updates are enumerated, not implied.
- No application source file is modified before the impact analysis exists.
- After implementation, `python scripts/validate_brain.py` and the named pytest targets pass.

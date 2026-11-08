---
name: documentation-maintenance
description: Update docs/brain/ after a plaivid_cli source change so architecture, feature maps, contracts, and indexes stay synchronized. Use whenever architecture, responsibilities, interfaces, dependencies, or feature mappings change.
---

# Documentation maintenance

## Purpose

Keep the model-independent knowledge base accurate and non-redundant after code changes, as
required by step 11 of the `AGENTS.md` workflow.

## When to use

- After implementing any change that touches a canonical module, public interface, CLI surface,
  data model, dependency direction, entry point, or feature.
- After discovering a discrepancy between documentation and code.
- When adding a new ADR or a new skill.

## Required knowledge documents

- `docs/brain/maintenance/DOCUMENTATION_POLICY.md` (authoritative rules)
- `docs/brain/maintenance/DOCUMENTATION_AUDIT.md` (drift checks and results)
- `docs/brain/README.md` (navigation table)
- `AGENTS.md` (workflow and rules)
- The specific documents named in the policy's "Update rules" table.

## Step-by-step procedure

1. Re-read `docs/brain/maintenance/DOCUMENTATION_POLICY.md` and classify the change.
2. From its update-rules table, list the **minimum** set of documents needing edits. Do not
   copy the same paragraph into multiple files; put detail in the most specific document and
   link from others.
3. Verify the canonical/legacy labels in `docs/brain/codebase/MODULE_INDEX.md` still match
   `setup.py` and `tests/unit/test_distribution.py`.
4. Update `docs/brain/codebase/FEATURE_TO_FILE_MAP.md` blocks (entry point, main implementation,
   tests, contracts, protected files) and `docs/brain/codebase/FILE_CATALOG.md` rows.
5. Update contracts (`docs/brain/contracts/`) and workflows (`docs/brain/workflows/`) only if
   interfaces, commands, models, build, or test procedures actually changed.
6. Update Mermaid diagrams in `docs/brain/diagrams/` if component/dependency structure changed.
7. Use repository-relative paths in backticks and `path.py::Symbol` evidence tokens only when
   the symbol exists. Preserve existing documentation; record discrepancies instead of
   rewriting history.
8. Run `python scripts/validate_brain.py` and fix all reported drift.
9. Record the audit result and date in `docs/brain/maintenance/DOCUMENTATION_AUDIT.md`.

## Expected output

A change list: documents edited · reason per document · links added/updated · evidence tokens
added · audit result. Confirm that no application source file was modified by the documentation
work itself.

## Validation criteria

- `python scripts/validate_brain.py` exits 0.
- No broken Markdown links, missing paths, or unresolved `::` symbols.
- No duplicated paragraphs across brain documents.
- Canonical/legacy labels remain consistent with packaging.
- `docs/brain/maintenance/DOCUMENTATION_AUDIT.md` has a fresh run result and date.

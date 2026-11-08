---
name: documentation-audit
description: Detect drift in the plaivid_cli knowledge base by running the read-only validator and reviewing documentation against code. Use periodically, before finishing a change, or when a documented path/symbol is suspect.
---

# Documentation audit

## Purpose

Verify that `docs/brain/` still points at real files, real symbols, real entry points, real
features, valid diagrams, and consistent legacy labels — and that the six skills and
`AGENTS.md` are intact.

## When to use

- Before declaring any code or documentation task complete.
- After a source change that might invalidate paths or symbols.
- When an agent reports "documentation conflicts with code".

## Required knowledge documents

- `docs/brain/maintenance/DOCUMENTATION_AUDIT.md` (workflow, checks, known discrepancies)
- `docs/brain/maintenance/DOCUMENTATION_POLICY.md` (evidence rules)
- `AGENTS.md` (entry point rules)
- `scripts/validate_brain.py` (read-only validator)

## Step-by-step procedure

1. Run `python scripts/validate_brain.py` from the repository root; use `--verbose` for
   per-check detail. The script is stdlib-only and read-only.
2. Review each failure category: required tree, Markdown links, referenced paths,
   `path.py::Symbol` evidence, feature mappings, entry points, Mermaid files, skill
   definitions, `AGENTS.md` references, and legacy labels.
3. For any missing path or symbol, decide whether the code moved or the documentation is stale;
   verify with a targeted source inspection. Never silently invent a replacement path.
4. Check that `docs/brain/codebase/MODULE_INDEX.md` legacy labels agree with `setup.py`,
   `pyproject.toml`, and `tests/unit/test_distribution.py`.
5. Compare `git log --oneline -- plaivid_cli` with `git log --oneline -- docs/brain` to detect
   source changes with no documentation update.
6. Record results, date, tool/command, and any new discrepancies in
   `docs/brain/maintenance/DOCUMENTATION_AUDIT.md`. Escalate unresolved conflicts instead of
   rewriting historical documents.
7. If only documentation changed, confirm with `git status --short` that no
   `plaivid_cli/**/*.py` file is modified.

## Expected output

An audit record: command and exit code · checks passed/failed · exact discrepancies with paths ·
corrective actions taken · remaining known gaps · date. A failing audit is a blocking result.

## Validation criteria

- `python scripts/validate_brain.py` exits 0 (or every failure is documented with an owner).
- All six skills have `SKILL.md` with `name`/`description` frontmatter and reference
  `docs/brain/`.
- `AGENTS.md` still points to `docs/brain/README.md` and all 11 workflow steps.
- Every newly discovered discrepancy is added to
  `docs/brain/maintenance/DOCUMENTATION_AUDIT.md`.
- Application source code was not modified by the audit.

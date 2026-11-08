# AGENTS.md — mandatory entry point for AI coding agents

This repository is `plaivid_cli`, a Linux-local CLI/Textual TUI for inspecting and operating
Plaivid PVM virtual machines through the configured local `sbell` and `pvm-running-vms`
commands. Read this file first, then work from the project brain in `docs/brain/`.
The brain is model-independent: it is plain Markdown plus Mermaid, with no vendor service.

## Mandatory exploration workflow

1. Read `AGENTS.md` (this file).
2. Read `docs/brain/README.md`.
3. Classify the task (feature, bug fix, architecture question, docs, build/release, data model).
4. Consult the relevant architecture and feature documents via the navigation table in the brain README.
5. Identify the **canonical** implementation files (`docs/brain/codebase/MODULE_INDEX.md`,
   `docs/brain/codebase/FEATURE_TO_FILE_MAP.md`). Never start from `plaivid_cli/legacy/`.
6. Inspect only those source files and the dependencies they actually need.
7. Inspect related tests (`docs/brain/workflows/TESTING.md`) and contracts
   (`docs/brain/contracts/MODULE_CONTRACTS.md`).
8. Write an impact analysis before editing: affected files, contracts, tests, and docs.
9. Implement changes without violating documented contracts.
10. Run the appropriate tests (`docs/brain/workflows/TESTING.md`) and the brain audit
    (`python scripts/validate_brain.py`).
11. Update affected `docs/brain/` documents when architecture, responsibilities, interfaces,
    dependencies, or feature mappings change.

## Rules

- Documentation is the **first navigation source**, not an unquestionable source of truth.
  Code, configuration, and tests are authoritative. If documentation conflicts with the
  implementation, verify the code, report the discrepancy in
  `docs/brain/maintenance/DOCUMENTATION_AUDIT.md`, and do not silently "fix" history.
- Never assume a documented file still exists without checking it.
- Never modify legacy or compatibility files when a canonical implementation exists, unless the
  task explicitly requires it. See `docs/brain/codebase/MODULE_INDEX.md`.
- Never perform broad repository exploration without a concrete reason.
- Never silently change architectural contracts. Import boundaries are enforced by
  `tests/unit/test_architecture_boundaries.py`.
- Keep documentation synchronized with source changes; do not duplicate knowledge between
  brain documents (`docs/brain/maintenance/DOCUMENTATION_POLICY.md`).
- The brain is additive: preserve existing `README.md`, `docs/*.md`,
  `docs/architecture/adr/`, `openspec/`, and `.agents/skills/unslop/`.

## Portable skills

Six reusable skills live in `.agents/skills/`: `codebase-exploration`,
`architecture-analysis`, `feature-impact-analysis`, `code-navigation`,
`documentation-maintenance`, `documentation-audit`. Not every agent platform auto-discovers
this directory. To invoke one portably, read its `SKILL.md` explicitly, for example:

```text
read .agents/skills/codebase-exploration/SKILL.md and follow its procedure
```

Skills reference `docs/brain/`; they do not duplicate it. See
`docs/brain/maintenance/DOCUMENTATION_AUDIT.md` for the audit workflow and
`scripts/validate_brain.py` for the read-only validator.

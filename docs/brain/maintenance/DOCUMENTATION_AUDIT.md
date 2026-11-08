# Documentation audit

**Purpose:** detect drift between `docs/brain/`, `AGENTS.md`, the skills, and the actual
repository. Navigation: [`../README.md`](../README.md) ·
[`DOCUMENTATION_POLICY.md`](DOCUMENTATION_POLICY.md) ·
[`../workflows/TESTING.md`](../workflows/TESTING.md).

## Drift detection mechanism

`scripts/validate_brain.py` is a **read-only, stdlib-only** Python script. It never writes to
the repository and never imports application code. Run it from the checkout root:

```bash
python scripts/validate_brain.py                       # pass/fail summary
python scripts/validate_brain.py --verbose             # per-link / per-symbol detail
python scripts/validate_brain.py --dependency-stats   # recompute DEPENDENCY_GRAPH.md numbers
```

Exit code `0` = consistent, `1` = drift found. It is not registered as a pytest test; run it as
a separate documentation check (see [`../workflows/TESTING.md`](../workflows/TESTING.md)).

### Automated checks

| Check | What it verifies |
|---|---|
| Required tree | All 32 required files exist and are non-empty; no empty brain Markdown. |
| Dependency boundaries | An AST scan of all 157 package modules asserts that no active module imports `plaivid_cli/legacy/`. `--dependency-stats` prints the reproducible fan-in/fan-out, layer edge counts, and SCCs quoted in [`../architecture/DEPENDENCY_GRAPH.md`](../architecture/DEPENDENCY_GRAPH.md). |
| Markdown links | Every relative Markdown link in brain docs, `AGENTS.md`, and the six skills resolves (anchors stripped; external URLs skipped). |
| Referenced paths | Every backticked repository-relative path token exists (file **or** directory). Glob patterns quoted from configuration (`*.egg-info/`, `plaivid_cli/legacy/*`) are treated as patterns, not paths. |
| Evidence symbols | Every `path.py::Symbol` token resolves via Python AST to a top-level class/function/assignment, and dotted suffixes to class members. |
| Feature maps | Each `### Feature:` block in `FEATURE_TO_FILE_MAP.md` has all 11 required fields, at least one implementation path and one test path, and no missing paths. |
| Entry points | `ENTRYPOINTS.md` still documents the 7 verified process/build entry-point symbols. |
| Mermaid | `.mmd` files start with a diagram keyword, contain edges, have balanced `subgraph`/`alt`/`loop`/`end` blocks, and are referenced by a brain document; inline `mermaid` fences are validated too; code fences are balanced. |
| Skills | Six SKILL.md files with valid `name`/`description` frontmatter, all six required sections, and a `docs/brain/` reference. |
| AGENTS.md | Points to `docs/brain/README.md`, lists all six skills and the audit script, and keeps the 11-step workflow. |
| Legacy labels | `MODULE_INDEX.md` labels `plaivid_cli/legacy/` as LEGACY; `setup.py` and `pyproject.toml` still exclude it; no brain line labels a legacy path CANONICAL. |

### Manual checks (do before declaring a change complete)

1. `git status --short` — confirm no application source file changed in a documentation task.
2. `git log --oneline -- plaivid_cli` vs `git log --oneline -- docs/brain` — source changes
   without documentation updates indicate drift.
3. Re-read changed claims against the cited source lines; a validator checks existence, not
   semantic accuracy.
4. Verify new diagrams describe real components and that terminology matches
   `DOCUMENTATION_POLICY.md`.
5. Confirm no duplicated paragraphs were introduced.

## Audit log

| Date (UTC) | Command | Result |
|---|---|---|
| 2026-11-08 | `python scripts/validate_brain.py` | **PASS** — exit 0. |
| 2026-11-08 | `python scripts/validate_brain.py --dependency-stats` | **PASS** — exit 0; 157 package modules (128 active / 29 legacy), 388 deduplicated edges, 0 active→legacy edges, 7 legacy→active, 54 legacy internal, 1 multi-node SCC (the charts type-only cycle). |

Final validator result (2026-11-08): **all 11 check groups report OK, exit code 0** —
required tree, Markdown links, referenced paths (including unique-path count), evidence
symbols, feature maps, entry points, Mermaid diagrams, skill definitions, AGENTS.md, and legacy
labels. The script prints live counts on every run; the chat/final report for this change
records them verbatim rather than duplicating counts here (documenting counts inside a
document that the validator itself scans would make them stale on the next edit).

"required tree" checks the 32 required files plus every brain Markdown file for emptiness.
A separate one-off repo-wide Markdown link scan (all tracked `.md` files, including the
pre-existing `docs/` and `openspec/` trees) found **0 broken relative links**.

### Remediation applied during the initial audit

- Added the missing `DOCUMENTATION_AUDIT.md`, `scripts/validate_brain.py`, and five skill files
  that were already referenced by `AGENTS.md` and the brain docs.
- Replaced brace/glob shorthand path groups with explicit repository-relative paths in
  `FILE_CATALOG.md`, `MODULE_INDEX.md`, and `REPOSITORY_MAP.md`; removed stale flat-module
  shorthand and ambiguous globs where they were being used as path references.
- Corrected counts: `FEATURE_TO_FILE_MAP.md` 15 → **16** feature maps; `TESTING.md` and
  `REPOSITORY_MAP.md` 30 → **32** pytest modules; charts facade 24 → **22** names; domain model
  facade 33 → **32** names.
- Aligned every numeric claim in `DEPENDENCY_GRAPH.md` with the reproducible AST scan and
  corrected the legacy boundary description (`version.py` + `config.py`, 7 inbound edges,
  54 internal edges) and the module-count wording (157 package modules, 190 including tests).
- Taught the Mermaid check that `sequenceDiagram` `alt`/`loop` blocks also terminate with `end`;
  fixed `DOCUMENTATION_POLICY.md` links, the `AGENTS.md` relative link, and the `DEVELOPMENT.md`
  `None`/`N/A` table typo.

## Known discrepancies in existing documentation (reported, not corrected)

These pre-existing documents are **preserved**. They are useful historical context but contain
claims that conflict with current code. Always trust code/tests and consult
[`../codebase/MODULE_INDEX.md`](../codebase/MODULE_INDEX.md).

| # | Document | Verified discrepancy |
|---|---|---|
| 1 | `docs/ARCHITECTURE.md` | Refers to flat modules `application/collection.py`, `application/operations.py`, `presentation/cli.py`, `presentation/tui.py`, and `infrastructure/pvm/adapter.py`; the active code uses packages. Also describes two primary TUI pages plus secondary Audit, while `plaivid_cli/presentation/tui/layout.py::LayoutMixin` composes three tabs (`overview`, `fleet`, `desktops`). |
| 2 | `docs/REFERENCE.md` | TUI section lists "Fleet, Host, Audit" tabs; actual tabs are Overview, Virtual Machines, Virtual Desktops. |
| 3 | `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` | States every post-dispatch reply is `OUTCOME_UNKNOWN`; current `plaivid_cli/application/operations/coordinator.py::OperationCoordinator` maps documented `status=success` → `SUCCEEDED` and `status=failed` → `FAILED`, leaving other statuses/transport failures `OUTCOME_UNKNOWN`. |
| 4 | `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` | Records `pyright — 0 errors` under its historical toolchain. A local Pyright 1.1.414 run reports pre-existing mixin attribute-access diagnostics on both the current tree and the HEAD baseline; treat the claim as toolchain-specific history, not a current gate. |
| 5 | `docs/architecture/adr/0010-packaging.md` | Proposes a conditional PyInstaller one-directory artifact; the implemented build is a setuptools wheel (`pyproject.toml`, `setup.py`, [`../workflows/BUILD.md`](../workflows/BUILD.md)). |
| 6 | `pyproject.toml` / `plaivid_cli/version.py` | Build version `0.4.0` vs runtime `__version__ = "1.2.0"`; `--version` uses the latter. No single-source versioning exists. |
| 7 | `plaivid_cli/__init__.py` | Module docstring refers to `orchestrator`, which now lives under `plaivid_cli/legacy/`; the `__version__` export is current. |
| 8 | `README.md` | Architecture bullet says `presentation/tui.py` uses Textual and lists redaction under `infrastructure/`; the actual Textual app is `plaivid_cli/presentation/tui/app.py::PlaividTui` and pure redaction is `plaivid_cli/domain/redaction.py::redact_text`. |
| 9 | `REFACTOR.md`, `TASKS.md`, `tests/smoke.py` | Legacy/historical material. Both notes state the retired implementation lives under `plaivid_cli/legacy/`; `tests/smoke.py` imports it and is excluded from unit runs. Not a conflict, but do not use them as current architecture. |

Historical OpenSpec changes (`openspec/changes/`) are planning records; they describe intent,
not necessarily shipped behavior. `docs/REAL_PVM_VALIDATION.md` is an owner-run plan, not a
validation report.

## Known documentation gaps / unverified areas

- **Real PVM/Sball behavior:** response/acceptance semantics, credentials in argv on the target
  host, lifecycle completion, metric schemas, NIC-list schema, permissions, and vendor support
  remain PENDING MANUAL PVM VALIDATION (`docs/REAL_PVM_VALIDATION.md`).
- **Python 3.12 runtime:** declared in `pyproject.toml` but not verified in the recorded
  workspace (`docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`).
- **Release process:** no CI, tags, changelog, signing, SBOM, deployment automation, or named
  release owner; see [`../workflows/RELEASE.md`](../workflows/RELEASE.md).
- **Terminal environments:** truecolor/256/16/NO_COLOR behavior is implemented and unit-tested
  but not validated on target host terminals.
- **Third-party skill:** `.agents/skills/unslop/` is preserved but is outside this knowledge
  base's audit scope (its own links and references are not validated).
- The validator checks existence and structure, **not** semantic truth. A document can pass
  while describing a behavior incorrectly; the manual review steps above are required.

## Source-code safety statement

This knowledge-base work added `AGENTS.md`, `docs/brain/**`, six `.agents/skills/**/SKILL.md`
files, and `scripts/validate_brain.py`. It did **not** modify any file under `plaivid_cli/`,
`tests/`, `pyproject.toml`, `setup.py`, `scripts/setup.sh`, or existing documentation. Verify
with `git status --short` and `git diff --stat -- plaivid_cli tests`.

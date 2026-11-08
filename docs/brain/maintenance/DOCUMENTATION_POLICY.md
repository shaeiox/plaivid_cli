# Documentation policy

Navigation: [`../README.md`](../README.md) · [`DOCUMENTATION_AUDIT.md`](DOCUMENTATION_AUDIT.md) ·
[`../decisions/ADR/README.md`](../decisions/ADR/README.md).

## Ownership and scope

`docs/brain/` is the **primary navigation source for AI coding agents**. It is owned by whoever
changes the architecture, module responsibilities, interfaces, dependencies, or feature
mappings. Source code, configuration, and tests remain the authoritative truth. Existing
documentation (`README.md`, Markdown files under `docs/`, `docs/architecture/adr/`, `openspec/`,
`.agents/skills/unslop/`) is preserved; this brain integrates and links to it rather than
replacing or copying it.

`AGENTS.md` is deliberately short and operational. It links here; it does not duplicate the
knowledge base.

## Evidence rules

1. Every repository-relative path written in backticks must exist. Run
   `python scripts/validate_brain.py` after any doc change.
2. A `path.py::Symbol` token asserts that the named module-level class, function, or assignment
   exists in that file; a dotted suffix (e.g. `Class.method`) asserts a class member. The audit
   script resolves these with Python's AST. Do not use the convention for invented symbols.
3. Important architectural claims carry an **Evidence:** line with source paths/symbols, test
   paths, or config keys. Verified facts and inferred observations must be distinguished (see
   [`../architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md)).
4. Mermaid diagrams must reflect real components and real relationships. Canonical structural
   diagrams live in [`../diagrams/system-context.mmd`](../diagrams/system-context.mmd); flow diagrams live inline in
   [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md).
5. Unverified information is labelled **Unverified**, **PENDING MANUAL PVM VALIDATION**, or
   "Missing / not present". Never present a proposal as shipped behavior.
6. Do not invent release procedures, deployment mechanisms, or host behavior. If a procedure is
   absent, say so (see [`../workflows/RELEASE.md`](../workflows/RELEASE.md)).

## Update rules — which document changes when

| Source change | Update |
|---|---|
| New/renamed/moved module or package | [`REPOSITORY_MAP.md`](../codebase/REPOSITORY_MAP.md), [`FILE_CATALOG.md`](../codebase/FILE_CATALOG.md), [`MODULE_INDEX.md`](../codebase/MODULE_INDEX.md) |
| New public interface or port method | [`MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`MODULE_INDEX.md`](../codebase/MODULE_INDEX.md), affected [`FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md) block |
| New CLI command / flag / JSON field / exit code | [`API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), [`ENTRYPOINTS.md`](../codebase/ENTRYPOINTS.md), [`FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md) |
| New/changed domain model or settings field | [`DATA_MODELS.md`](../contracts/DATA_MODELS.md) |
| Layer/import boundary change | [`DEPENDENCY_GRAPH.md`](../architecture/DEPENDENCY_GRAPH.md), [`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md), [`dependency-overview.mmd`](../diagrams/dependency-overview.mmd) |
| New user-visible feature or capability | [`FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md) (new block), [`TESTING.md`](../workflows/TESTING.md), [`COMPONENTS.md`](../architecture/COMPONENTS.md) |
| New entry point / worker / timer | [`ENTRYPOINTS.md`](../codebase/ENTRYPOINTS.md), [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) |
| Build, dependency, or release change | [`BUILD.md`](../workflows/BUILD.md), [`DEVELOPMENT.md`](../workflows/DEVELOPMENT.md), [`RELEASE.md`](../workflows/RELEASE.md) |
| New architectural decision | [`ADR/README.md`](../decisions/ADR/README.md) + a new ADR using the required structure |
| New skill | [`AGENTS.md`](../../../AGENTS.md) skill list, this policy, [`DOCUMENTATION_AUDIT.md`](DOCUMENTATION_AUDIT.md) skill check |
| Any of the above | [`DOCUMENTATION_AUDIT.md`](DOCUMENTATION_AUDIT.md) results/date after running the audit |

Update the **minimum number of documents**; cross-link instead of repeating content. If the
same fact naturally belongs in two places, put the detail in the more specific document and
link from the other.

## Terminology (use consistently)

| Term | Meaning here |
|---|---|
| **Canonical** | The active implementation to modify. |
| **Legacy / retired** | `plaivid_cli/legacy/`, checkout-only, not shipped. Do not call it "deprecated" (no deprecation markers exist). |
| **Facade** | `__init__.py` with `__all__` that re-exports implementation modules. |
| **Shim** | Thin compatibility/lazy-import layer; holds no behavior. |
| **Section** | A named collection unit in `SUPPORTED_SECTIONS` (e.g. `inventory`, `host_metrics`). |
| **Snapshot** | Immutable `ApplicationSnapshot` / `SectionSnapshot` / `SourceResult` value. |
| **Outcome / state** | `OperationState` values; acceptance is never equated with completion. |
| **Verified** | Derived from source, config, tests, or an existing document. |
| **Inferred** | An architectural interpretation not directly asserted by code/tests. |

## Review checklist before finishing a change

- [ ] `python scripts/validate_brain.py` passes (paths, links, symbols, features, entry points,
      Mermaid, skills, legacy labels).
- [ ] Every new path is repository-relative and exists; every `::` token resolves.
- [ ] Canonical vs legacy classification in [`MODULE_INDEX.md`](../codebase/MODULE_INDEX.md)
      still matches `setup.py` and `tests/unit/test_distribution.py`.
- [ ] [`FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md) still maps the changed feature to its tests and contracts.
- [ ] No duplicated paragraphs between brain documents.
- [ ] [`DOCUMENTATION_AUDIT.md`](DOCUMENTATION_AUDIT.md) records the audit result and date.
- [ ] Any discrepancy found in existing documentation is reported there, not silently
      "corrected" by rewriting history.

## Skills and portability

The six skills in `.agents/skills/` (`codebase-exploration`, `architecture-analysis`,
`feature-impact-analysis`, `code-navigation`, `documentation-maintenance`,
`documentation-audit`) contain SKILL.md with YAML frontmatter (`name`, `description`) and
procedures that reference `docs/brain/`. They must stay vendor-neutral; no platform-specific
instructions, no duplicated architecture content. `AGENTS.md` documents the portable invocation
pattern because not every agent platform auto-discovers `.agents/skills/`.

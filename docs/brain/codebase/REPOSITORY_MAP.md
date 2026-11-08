# Repository map

This document explains the **architectural meaning** of the directory structure; it is not a
file listing. For individual files see [`FILE_CATALOG.md`](FILE_CATALOG.md); for canonical vs
legacy classification see [`MODULE_INDEX.md`](MODULE_INDEX.md). Navigation:
[`../README.md`](../README.md).

## Root

| Path | Meaning |
|---|---|
| `pyproject.toml` | Build metadata, `requires-python >=3.12`, single runtime dependency `textual>=0.47`, `dev` extra, console script `plaivid = plaivid_cli.bootstrap:main`, pytest/Ruff/Pyright/coverage config. |
| `setup.py` | Build-time package selection; `RuntimeBuildPy` filters the retired `legacy` package from distributions. |
| `plaivid` | Executable checkout launcher (`#!/usr/bin/env python3`) calling `bootstrap.main`. |
| `scripts/setup.sh` | Developer bootstrap: distro detection, Python 3.12+ discovery, project-local `.venv`, editable install with `.[dev]`, `plaivid --help` check. |
| `scripts/validate_brain.py` | Read-only, stdlib-only drift validator for this knowledge base (documentation tooling, not application code). |
| `AGENTS.md` | Mandatory model-independent agent entry point; points here. |
| `README.md` | User-facing install, commands, configuration, security, and code layout. |
| `REFACTOR.md`, `TASKS.md` | Historical notes for the retired command/action registry design. Both explicitly state the implementation now lives under `plaivid_cli/legacy/`. Do not treat them as current architecture. |
| `.gitignore`, `.gitattributes` | Ignore `.venv`, caches, session state, build artifacts; enforce LF for `*.sh`. |
| `assets/plaivid-logo.svg` | Source artwork for the terminal wordmark in `plaivid_cli/presentation/logo.py::logo_text`. |
| `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` | Generated local artifacts; ignored by Git. |

## `plaivid_cli/` — the application package

| Path | Architectural meaning |
|---|---|
| `plaivid_cli/__init__.py`, `plaivid_cli/__main__.py`, `plaivid_cli/version.py` | Package identity, `python -m plaivid_cli` shim, single version constant. `version.py` is the authoritative `__version__`. |
| `plaivid_cli/bootstrap.py` | **Only composition root** and process entry point. |
| `plaivid_cli/config.py` | Validated environment configuration; no global mutable state. |
| `plaivid_cli/domain/` | Provider-independent facts and pure policy. `domain/models/` holds the immutable dataclass/StrEnum definitions; `domain/models/__init__.py` is the stable re-export facade. `inventory.py`, `overview.py`, `desktops.py`, `policies.py`, `redaction.py`, `errors.py` hold pure logic. |
| `plaivid_cli/application/` | Use-case layer. `ports.py` = outbound `Protocol`s; `services.py` = read facade + selector resolution; `session.py` = auth/token cache; `overview.py` = Overview scheduling/history. |
| `plaivid_cli/application/collection/` | The **single read lane**: coordinator, per-section reader, publication policy, freshness, section validation. |
| `plaivid_cli/application/operations/` | The **single mutation lane**: coordinator, admission planner, Desktop executor, outcome aggregation. |
| `plaivid_cli/infrastructure/` | OS/vendor boundary: `process.py` (bounded child), `audit.py` (read-only SQLite), `diagnostics.py` (redacting logs), `local_monitor.py` (local `/proc`/sysfs). |
| `plaivid_cli/infrastructure/pvm/` | PVM integration. `adapter/` = gateway implementation + documented request shapes; `parsers/` = pure XML/text parsers; `sbell.py` = argv client; `overview.py`, `desktops.py`, `uptime.py` = additional pure parsers/derivations. |
| `plaivid_cli/presentation/` | All user-visible surfaces. It never imports `infrastructure/`. |
| `plaivid_cli/presentation/cli/` | One-shot CLI: grammar, dispatch, read handlers, lifecycle handlers, JSON/human serialization. |
| `plaivid_cli/presentation/tui/` | Textual app. `app.py` = concrete `App` combining mixins; `layout.py` = shell/tabs; `session.py`, `refresh.py`, `audit.py` = behavior mixins; `styles.py` = semantic CSS. |
| `plaivid_cli/presentation/tui/pages/` | Three independent page packages (`overview/`, `virtual_machines/`, `virtual_desktops/`), each with `page.py`, `controller.py`/mixins, `components/`, and component-specific `selection.py`, `operations.py`, `policy.py`. Pages must not import sibling pages. |
| `plaivid_cli/presentation/tui/components/` | Reusable, presentation-only widgets shared across pages (cards, checkable table, toolbar, actions, formatting, status). |
| `plaivid_cli/presentation/overview_metrics/` | Pure text formatters, one module per telemetry concern, plus `common.py` primitives and an `__init__.py` facade. |
| `plaivid_cli/presentation/charts/` | Pure chart geometry (`grid.py`), rendering and scaling (`render.py`), and the Textual `Static` wrapper (`widget.py`). `__init__.py` is the facade. |
| `plaivid_cli/presentation/theme.py`, `plaivid_cli/presentation/logo.py` | Terminal palette/color-depth adaptation and wordmark. |
| `plaivid_cli/legacy/` | **Retired** checkout-only implementation: root modules, `actions/` registry, `commands/` registry. Excluded from wheels, Ruff, Pyright, and coverage. Not a dependency of active code. |

## `tests/`

| Path | Meaning |
|---|---|
| `tests/unit/` | 32 pytest modules. Fake providers/process runners, synthetic XML/text fixtures, temporary SQLite files, Textual Pilot. No PVM host access. |
| `tests/fixtures/` | Synthetic parser fixtures plus `tests/fixtures/README.md` stating they are **not** captured PVM output. |
| `tests/smoke.py` | Opt-in, owner-run real-host script that imports `plaivid_cli.legacy`. Excluded from unit runs (`README.md`, `pyproject.toml` Ruff config); never run in CI-like local verification. |

## `docs/`

| Path | Meaning |
|---|---|
| `docs/brain/` | This model-independent knowledge base (navigation, architecture, contracts, workflows, decisions, maintenance, diagrams). |
| `docs/ARCHITECTURE.md`, `docs/REFERENCE.md`, `docs/ENVIRONMENT.md`, `docs/MONITORING_DASHBOARD.md`, `docs/REAL_PVM_VALIDATION.md`, `docs/SBELL-SABAD.md`, `docs/TUI_UNSLOP_PLAN.md` | Existing user/architecture/protocol/validation documentation. Preserved; several contain stale flat-module names — see [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md). |
| `docs/architecture/` | Historical audit notes (`01`–`07`, `FINAL_IMPLEMENTATION_AUDIT.md`) and `docs/architecture/adr/` (14 existing ADRs + index). These are the authoritative historical decision records. |
| `docs/Plaivid CLI & sbell Reference.md`, `docs/Plaivid CLI & sbell Reference.pdf`, `docs/Plaivid CLI & sbell Reference.docx` | Vendor/operator reference in Markdown, PDF, and DOCX forms. |

## `openspec/`

Spec-driven change records. `openspec/config.yaml` plus three changes:
`openspec/changes/implement-complete-plaivid-cli/` (2026-10-30),
`openspec/changes/redesign-monitoring-tui/`,
`openspec/changes/add-virtual-desktop-management/` (2026-11-01). Each has `proposal.md`,
`design.md`, `tasks.md`, and `specs/` capability specs. `openspec/specs/.gitkeep` and
`openspec/changes/archive/.gitkeep` are placeholders. These are planning/spec documents, not
runtime code; treat them as historical context, not current behavior.

## `.agents/skills/`

Portable Agent Skills directory. `.agents/skills/unslop/` is a pre-existing third-party design
skill (CC BY 4.0) — preserve it. Six locally authored, model-independent skills were added for
codebase exploration, architecture analysis, feature impact analysis, code navigation,
documentation maintenance, and documentation audit. Skills reference `docs/brain/` rather than
duplicating it.

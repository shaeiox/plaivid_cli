# Components

Each component below is a responsibility boundary, not a single file. Paths are
repository-relative; symbols are verified by `scripts/validate_brain.py`. Navigation:
[`../README.md`](../README.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) ·
[`../codebase/FILE_CATALOG.md`](../codebase/FILE_CATALOG.md).

---

## 1. Composition root and configuration

- **Location:** `plaivid_cli/bootstrap.py`, `plaivid_cli/config.py`, `plaivid_cli/version.py`, `plaivid` (launcher), `plaivid_cli/__main__.py`.
- **Responsibility:** parse CLI args, validate environment, construct the one provider/coordinator set, dispatch, and guarantee shutdown.
- **Public interface:** `plaivid_cli/bootstrap.py::main`, `plaivid_cli/bootstrap.py::build_runtime`, `plaivid_cli/bootstrap.py::Runtime`, `plaivid_cli/config.py::load_settings`, `plaivid_cli/config.py::Settings`.
- **Dependencies:** all `application/` coordinator packages, `infrastructure/` adapters, `presentation/cli/__init__.py`.
- **Consumers:** console script `plaivid` (`pyproject.toml`), `./plaivid`, `python -m plaivid_cli`, `tests/unit/test_bootstrap.py`, `tests/unit/test_cli_and_tui.py::runtime`.
- **Details:** `help`/`--version`/`config`/`diagnostics` never call `build_runtime`; `finally: runtime.close()` closes both coordinators. Configuration errors exit 2 before PVM work.
- **Tests:** `tests/unit/test_bootstrap.py`, `tests/unit/test_config.py`, `tests/unit/test_cli_and_tui.py`.
- **Docs:** [`../codebase/ENTRYPOINTS.md`](../codebase/ENTRYPOINTS.md), [`../workflows/DEVELOPMENT.md`](../workflows/DEVELOPMENT.md).

## 2. CLI front end

- **Location:** `plaivid_cli/presentation/cli/` (`parser.py`, `dispatch.py`, `reads.py`, `operations.py`, `serialization.py`, `__init__.py`).
- **Responsibility:** argparse grammar, one-shot read/lifecycle handlers, session admission, stable exit codes, human and JSON output with redaction.
- **Public interface:** `plaivid_cli/presentation/cli/parser.py::build_parser`, `plaivid_cli/presentation/cli/dispatch.py::run_command`, `plaivid_cli/presentation/cli/serialization.py::configuration_command`.
- **Dependencies:** `application/services.py`, `application/operations/`, `application/session.py`, `domain/models/`, `domain/redaction.py`, `config.py`.
- **Consumers:** `bootstrap.main`; `tests/unit/test_cli_and_tui.py`.
- **Details:** exit constants live in `plaivid_cli/presentation/cli/operations.py` (`EXIT_OK=0`, `EXIT_FAILURE=1`, `EXIT_REJECTED=2`, `EXIT_PARTIAL=3`, `EXIT_UNKNOWN=4`); `dispatch.EXIT_PARTIAL = 3` re-defines the same value. `--json` uses `_section_payload` + `_redact_json`.
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_bootstrap.py`, `tests/unit/test_redaction.py`.
- **Docs:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).

## 3. Textual TUI shell

- **Location:** `plaivid_cli/presentation/tui/` (`app.py`, `layout.py`, `session.py`, `refresh.py`, `audit.py`, `styles.py`), `plaivid_cli/presentation/theme.py`.
- **Responsibility:** app shell, tab composition, login/logout, timer-driven refresh, Textual workers, event bindings, semantic CSS and palette.
- **Public interface:** `plaivid_cli/presentation/tui/app.py::PlaividTui`, `plaivid_cli/presentation/tui/layout.py::LayoutMixin`, `plaivid_cli/presentation/tui/styles.py::TUI_CSS`, `plaivid_cli/presentation/theme.py::palette_for`.
- **Dependencies:** page packages, `presentation/charts/`, `presentation/tui/components/`, `application/` (services, coordinators, Overview state), `domain/models/`. Never infrastructure.
- **Consumers:** `dispatch.run_command` (TTY only); Textual Pilot tests.
- **Details:** tabs are `overview`, `fleet`, `desktops` (from `TabPane` ids in the three `page.py` files); bindings `1`/`2`/`3`/`r`/`q`/`space`/`a`/`enter`; a 0.5 s interval drives `RefreshMixin._tick`; a separate 1 Hz wall-clock chart redraw prunes the 60 s history.
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_tui_theme.py`, `tests/unit/test_multi_select.py`, `tests/unit/test_background_graphs.py`, `tests/unit/test_overview_monitoring.py`.
- **Docs:** [`../codebase/FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md).

## 4. TUI pages and reusable components

- **Location:** `plaivid_cli/presentation/tui/pages/overview/`, `plaivid_cli/presentation/tui/pages/virtual_machines/`, `plaivid_cli/presentation/tui/pages/virtual_desktops/`, `plaivid_cli/presentation/tui/components/`.
- **Responsibility:** per-page composition, presenters/controllers, selection/search/action behavior, shared cards/tables/toolbars.
- **Public interface:** `plaivid_cli/presentation/tui/pages/overview/page.py::OverviewPage`, `plaivid_cli/presentation/tui/pages/virtual_machines/page.py::VirtualMachinePage`, `plaivid_cli/presentation/tui/pages/virtual_desktops/page.py::VirtualDesktopPage`, `plaivid_cli/presentation/tui/components/card.py::DashboardCard`, `plaivid_cli/presentation/tui/components/checkable_table.py::CheckableTable`.
- **Dependencies:** `presentation/theme.py`, `presentation/charts/`, `presentation/overview_metrics/`, `domain/models/`, `application/overview.py`; page components are presentation-only.
- **Consumers:** `LayoutMixin.compose`; controller mixins on `PlaividTui`.
- **Details:** controllers render supplied snapshot values, never call providers; `presenter.cards` / `presenter.card_statuses` are pure; `CheckableTable` has exactly one definition (asserted by `tests/unit/test_architecture_boundaries.py`); sibling pages must not import each other.
- **Tests:** `tests/unit/test_architecture_boundaries.py`, `tests/unit/test_host_metrics_panels.py`, `tests/unit/test_quorum_status.py`, `tests/unit/test_virtual_desktops.py`, `tests/unit/test_dashboard_chart_refactor.py`.
- **Docs:** `docs/MONITORING_DASHBOARD.md`, `docs/TUI_UNSLOP_PLAN.md`.

## 5. Overview telemetry formatters and charts

- **Location:** `plaivid_cli/presentation/overview_metrics/`, `plaivid_cli/presentation/charts/`, `plaivid_cli/application/overview.py`.
- **Responsibility:** pure text formatting of telemetry sections; pure chart geometry/rendering; 60-second history, scheduling, health labels.
- **Public interface:** `plaivid_cli/presentation/charts/render.py::render_chart`, `plaivid_cli/presentation/charts/render.py::dynamic_top`, `plaivid_cli/presentation/charts/widget.py::ChartView`, `plaivid_cli/presentation/overview_metrics/common.py::body`, `plaivid_cli/application/overview.py::OverviewHistory`, `plaivid_cli/application/overview.py::OverviewSchedule`.
- **Dependencies:** `domain/models/`, `domain/overview.py`, `presentation/theme.py`, Rich `Text`, `textual.widgets.Static` (widget only).
- **Consumers:** `OverviewPage`, `OverviewMixin`, `HostPageMixin`, `RefreshMixin`.
- **Details:** `charts/__init__.py` is a re-export facade with `__all__`; grid dots are a separate dim-gray layer; Braille lines are one dot thick; Y gutter shows dynamic Y-Max/Y-Mid/0; the time axis is a smooth `─`/`┴` rule; `ChartView.__init__` tolerates `palette` and extra kwargs.
- **Tests:** `tests/unit/test_charts.py`, `tests/unit/test_graph_history.py`, `tests/unit/test_background_graphs.py`, `tests/unit/test_dashboard_chart_refactor.py`, `tests/unit/test_host_metrics_panels.py`.
- **Docs:** `docs/MONITORING_DASHBOARD.md`, [`../decisions/ADR/README.md`](../decisions/ADR/README.md).

## 6. Application read facade and target resolution

- **Location:** `plaivid_cli/application/services.py`, `plaivid_cli/application/ports.py`.
- **Responsibility:** stable read use cases, typed section extraction, selector resolution, and the narrow outbound `Protocol`s.
- **Public interface:** `plaivid_cli/application/services.py::PlaividApplication`, `plaivid_cli/application/services.py::TargetSelection`, `plaivid_cli/application/ports.py::PvmGateway`, `plaivid_cli/application/ports.py::MonitoringGateway`, `plaivid_cli/application/ports.py::AuditGateway`.
- **Dependencies:** `application/collection/`, `domain/models/`, `domain/errors.py`, `config.py`.
- **Consumers:** CLI handlers, all TUI controllers/mixins, `bootstrap.build_runtime`.
- **Details:** selectors = canonical UUID, exact name, unique name prefix, 1-based index, `all`, `state:<state>`, `process:present|missing`; `tag:` is explicitly unsupported. `MonitoringGateway` is an optional extension of `PvmGateway` (docstring in `ports.py`).
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_application_operations.py`.
- **Docs:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).

## 7. Collection subsystem

- **Location:** `plaivid_cli/application/collection/` (`coordinator.py`, `reader.py`, `publisher.py`, `freshness.py`, `sections.py`, `__init__.py`).
- **Responsibility:** single serialized read executor, coalescing, one bounded pending intent, independent per-section last-good publication, freshness clocks, mutation generation barriers.
- **Public interface:** `plaivid_cli/application/collection/coordinator.py::CollectionCoordinator`, `plaivid_cli/application/collection/coordinator.py::CollectionSuperseded`, `plaivid_cli/application/collection/sections.py::normalize_sections`, `plaivid_cli/application/collection/freshness.py::section_is_fresh`, `plaivid_cli/application/collection/publisher.py::publish_results`.
- **Dependencies:** `PvmGateway`/`MonitoringGateway`, `domain/models/`, `domain/inventory.py::merge_inventory`, `config.py`.
- **Consumers:** `PlaividApplication`, `OperationCoordinator`, `OperationPlanner`, `RefreshMixin`.
- **Details:** `SUPPORTED_SECTIONS` in `sections.py` enumerates 11 sections plus `detail:<uuid>`; `reader.collect` maps each to a provider call and a source label; publication is suppressed if a mutation changed the epoch. No active module imports legacy.
- **Tests:** `tests/unit/test_collection_coordinator.py`, `tests/unit/test_application_operations.py`, `tests/unit/test_cli_and_tui.py`.
- **Docs:** [`DATA_FLOW.md`](DATA_FLOW.md), [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).

## 8. Operations subsystem

- **Location:** `plaivid_cli/application/operations/` (`coordinator.py`, `planner.py`, `desktop_executor.py`, `results.py`, `__init__.py`).
- **Responsibility:** admission/planning, serialized dispatch, outcome mapping, aggregation, Desktop execution, reconciliation.
- **Public interface:** `plaivid_cli/application/operations/coordinator.py::OperationCoordinator`, `plaivid_cli/application/operations/planner.py::OperationPlanner`, `plaivid_cli/application/operations/results.py::aggregate_state`, `plaivid_cli/application/operations/desktop_executor.py::DesktopOperationExecutor`.
- **Dependencies:** `application/collection/`, `PvmGateway`, `domain/policies.py::bulk_may_dispatch`, `domain/models/`, `config.py`.
- **Consumers:** CLI `_operate`, `VMOperationMixin`, `DesktopMixin`, `bootstrap.build_runtime`.
- **Details:** `_execute_locked` re-creates the plan to detect staleness, erects a mutation barrier, stops bulk after `FAILED`/`REJECTED`/`OUTCOME_UNKNOWN` marking remaining `NOT_STARTED`, and reconciles with `collect_once`. No automatic retry.
- **Tests:** `tests/unit/test_application_operations.py`, `tests/unit/test_operation_policy.py`, `tests/unit/test_virtual_desktops.py`.
- **Docs:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md).

## 9. Session and security

- **Location:** `plaivid_cli/application/session.py`, `plaivid_cli/domain/redaction.py`, `plaivid_cli/domain/policies.py`, `plaivid_cli/infrastructure/diagnostics.py`.
- **Responsibility:** resume/login/logout, restrictive token cache, pure secret redaction, risk policies, redacting log filter.
- **Public interface:** `plaivid_cli/application/session.py::SessionManager`, `plaivid_cli/application/session.py::SessionStore`, `plaivid_cli/domain/redaction.py::redact_text`, `plaivid_cli/domain/policies.py::action_policy`, `plaivid_cli/infrastructure/diagnostics.py::configure_logging`.
- **Dependencies:** `PvmGateway`, `Settings`, `PvmSession`, `AppError`.
- **Consumers:** CLI `_session`/`_operate`, `SessionMixin`, `bootstrap.build_runtime`.
- **Details:** cache is `<state_dir>/session.json`, directory 0700, file 0600, atomic `os.replace`, symlink/ownership checks, `O_NOFOLLOW`; no password is persisted; `PLAIVID_ALLOW_CREDENTIAL_ARGV` gates login and token argv calls.
- **Tests:** `tests/unit/test_session_lifecycle.py`, `tests/unit/test_redaction.py`, `tests/unit/test_operation_policy.py`.
- **Docs:** `docs/ENVIRONMENT.md`, `docs/REAL_PVM_VALIDATION.md`.

## 10. Domain model / policy layer

- **Location:** `plaivid_cli/domain/` (`models/`, `inventory.py`, `overview.py`, `desktops.py`, `errors.py`, `policies.py`, `redaction.py`).
- **Responsibility:** immutable facts, enums, typed errors, pure correlation and policies. No I/O.
- **Public interface:** `plaivid_cli/domain/models/__init__.py` (re-export facade, 32 names in `__all__`), `plaivid_cli/domain/inventory.py::merge_inventory`, `plaivid_cli/domain/models/enums.py::Action`, `plaivid_cli/domain/errors.py::AppError`.
- **Dependencies:** standard library only (plus intra-domain imports).
- **Consumers:** every other layer (53 importing modules).
- **Details:** `SourceResult`/`SectionSnapshot`/`ApplicationSnapshot` are generic frozen slots dataclasses; `CollectionStatus` has six values; `OperationState` has eleven; `canonical_uuid` normalizes UUIDs.
- **Tests:** `tests/unit/test_domain_models.py`, `tests/unit/test_errors.py`, `tests/unit/test_quorum_status.py`.
- **Docs:** [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).

## 11. PVM gateway, parsers, and process execution

- **Location:** `plaivid_cli/infrastructure/pvm/` (`adapter/`, `parsers/`, `sbell.py`, `overview.py`, `desktops.py`, `uptime.py`), `plaivid_cli/infrastructure/process.py`.
- **Responsibility:** repository-evidenced `sbell` request shapes, XML/text parsing, local process-evidence helper, bounded child execution.
- **Public interface:** `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter`, `plaivid_cli/infrastructure/pvm/sbell.py::SbellClient`, `plaivid_cli/infrastructure/process.py::ProcessRunner`, `plaivid_cli/infrastructure/pvm/parsers/inventory.py::parse_object_inventory`, `plaivid_cli/infrastructure/pvm/parsers/host.py::parse_metrics`.
- **Dependencies:** `domain/models/`, `domain/overview.py`, `domain/errors.py`, `infrastructure/local_monitor.py`, `infrastructure/diagnostics.py`.
- **Consumers:** `bootstrap.build_runtime` (only wiring point), the parser/adapter suites under `tests/unit/`.
- **Details:** `SbellClient.call(module, command, params, token)` validates module/command identifiers, rejects truncated/empty/invalid XML, and returns `SbellResponse`; `LocalPvmAdapter` implements both `PvmGateway` and `MonitoringGateway`; parsers fail closed on missing/malformed values.
- **Tests:** `tests/unit/test_pvm_adapter.py`, `tests/unit/test_pvm_parsers.py`, `tests/unit/test_sbell_client.py`, `tests/unit/test_monitoring_metrics_parser.py`, `tests/unit/test_nic_list_parser.py`, `tests/unit/test_process_runner.py`, `tests/unit/test_pvm_uptime.py`.
- **Docs:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), `docs/SBELL-SABAD.md`.

## 12. Local monitoring and read-only audit

- **Location:** `plaivid_cli/infrastructure/local_monitor.py`, `plaivid_cli/infrastructure/audit.py`, `plaivid_cli/infrastructure/pvm/overview.py`.
- **Responsibility:** local `/proc` + sysfs sampling and optional bounded, read-only SQLite audit access.
- **Public interface:** `plaivid_cli/infrastructure/local_monitor.py::LinuxMonitor`, `plaivid_cli/infrastructure/audit.py::ReadOnlyAuditAdapter`, `plaivid_cli/infrastructure/pvm/overview.py::parse_nic_list`.
- **Dependencies:** `domain/models/`, `domain/overview.py`, `domain/errors.py`.
- **Consumers:** `LocalPvmAdapter` (monitoring), `PlaividApplication.recent_audit` → CLI/TUI audit panels.
- **Details:** audit opens `file:...?mode=ro`, checks `_REQUIRED_COLUMNS`, limits rows to 1–500, and filters `Log` messages with a compiled regex; local values describe the machine running the client, not necessarily the PVM host.
- **Tests:** `tests/unit/test_audit_adapter.py`, `tests/unit/test_overview_monitoring.py`, `tests/unit/test_nic_list_parser.py`.
- **Docs:** `docs/MONITORING_DASHBOARD.md`, `docs/ENVIRONMENT.md`.

## 13. Presentation theme and assets

- **Location:** `plaivid_cli/presentation/theme.py`, `plaivid_cli/presentation/logo.py`, `plaivid_cli/presentation/tui/styles.py`, `assets/plaivid-logo.svg`.
- **Responsibility:** terminal-palette detection (truecolor/256/16/NO_COLOR), rich-text helpers, CSS, wordmark.
- **Public interface:** `plaivid_cli/presentation/theme.py::palette_for`, `plaivid_cli/presentation/theme.py::apply_theme`, `plaivid_cli/presentation/theme.py::group_title`, `plaivid_cli/presentation/logo.py::logo_text`, `plaivid_cli/presentation/tui/styles.py::TUI_CSS`.
- **Dependencies:** Rich/Textual, `domain` none.
- **Consumers:** `PlaividTui`, all page components, `ChartView`.
- **Tests:** `tests/unit/test_group_palette.py`, `tests/unit/test_tui_theme.py`, `tests/unit/test_quorum_status.py`.
- **Docs:** `docs/MONITORING_DASHBOARD.md`, `docs/TUI_UNSLOP_PLAN.md`.

## 14. Retired legacy implementation

- **Location:** `plaivid_cli/legacy/` (root modules, `actions/`, `commands/`), `REFACTOR.md`, `TASKS.md`.
- **Responsibility:** historical, checkout-only reference for the retired dynamic command/action registry design.
- **Public interface:** none used by the active runtime; `tests/smoke.py` imports it (opt-in real-host script, excluded from unit runs).
- **Dependencies:** internally self-contained, plus `plaivid_cli/version.py` and `plaivid_cli/config.py`.
- **Consumers:** none in the shipped wheel; `setup.py::RuntimeBuildPy` filters it out.
- **Tests:** `tests/unit/test_distribution.py` asserts exclusion (not behavior).
- **Docs:** [`../codebase/MODULE_INDEX.md`](../codebase/MODULE_INDEX.md), `REFACTOR.md`.

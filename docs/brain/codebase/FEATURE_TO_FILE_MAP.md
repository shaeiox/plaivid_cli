# Feature → file map

**The primary index for locating an implementation.** Find the feature heading, then use its
file list; do not grep the whole repository first. Every path below is verified by
`scripts/validate_brain.py`. Navigation: [`../README.md`](../README.md) ·
[`MODULE_INDEX.md`](MODULE_INDEX.md) · [`FILE_CATALOG.md`](FILE_CATALOG.md) ·
[`ENTRYPOINTS.md`](ENTRYPOINTS.md).

There are **16 feature/capability maps** in this document.

---

### Feature: CLI startup and command dispatch

- **Description:** All process launches converge on one composition root; help/version/config avoid constructing PVM objects.
- **Entry point:** `plaivid_cli/bootstrap.py::main` (reached from `pyproject.toml` console script, `plaivid`, `plaivid_cli/__main__.py`).
- **Main implementation:** `plaivid_cli/bootstrap.py`, `plaivid_cli/presentation/cli/parser.py`, `plaivid_cli/presentation/cli/dispatch.py`.
- **Supporting modules:** `plaivid_cli/config.py`, `plaivid_cli/infrastructure/diagnostics.py`, `plaivid_cli/presentation/cli/serialization.py`.
- **Shared dependencies:** `plaivid_cli/application/services.py`, `plaivid_cli/application/operations/coordinator.py`, `plaivid_cli/application/session.py`.
- **Data models:** `plaivid_cli/config.py::Settings`, `plaivid_cli/domain/models/snapshots.py::ApplicationSnapshot`.
- **Tests:** `tests/unit/test_bootstrap.py`, `tests/unit/test_cli_and_tui.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
- **Potential impact areas:** every command, exit code, shutdown of both coordinators, logging setup.
- **Files that should NOT be modified:** `plaivid_cli/legacy/`, `tests/smoke.py`, `plaivid_cli/presentation/cli/__init__.py` (facade only).
- **Documentation references:** [`ENTRYPOINTS.md`](ENTRYPOINTS.md), [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md), `README.md`, `docs/REFERENCE.md`.

---

### Feature: Validated configuration and diagnostics

- **Description:** Environment-only configuration with validation and a redacted, PVM-free configuration report.
- **Entry point:** `plaivid_cli/config.py::load_settings` from `bootstrap.main`; `config`/`diagnostics` commands.
- **Main implementation:** `plaivid_cli/config.py`, `plaivid_cli/presentation/cli/serialization.py::configuration_command`.
- **Supporting modules:** `plaivid_cli/infrastructure/diagnostics.py`, `plaivid_cli/domain/redaction.py`.
- **Shared dependencies:** `plaivid_cli/bootstrap.py`, `plaivid_cli/application/session.py`, `plaivid_cli/application/operations/planner.py`.
- **Data models:** `plaivid_cli/config.py::Settings`, `plaivid_cli/config.py::ConfigurationError`; session file `<state_dir>/session.json`.
- **Tests:** `tests/unit/test_config.py`, `tests/unit/test_bootstrap.py`, `tests/unit/test_redaction.py`.
- **Related contracts:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).
- **Potential impact areas:** all timeouts, refresh cadence, bulk admission (`PLAIVID_MAX_INVENTORY_AGE_SECONDS`), credential argv gate.
- **Files that should NOT be modified:** `scripts/setup.sh` (same variables but separate setup logic), `docs/ENVIRONMENT.md` (unless correcting).
- **Documentation references:** `docs/ENVIRONMENT.md`, `README.md`, [`../workflows/DEVELOPMENT.md`](../workflows/DEVELOPMENT.md).

---

### Feature: CLI read commands and JSON output

- **Description:** One-shot inventory, host status/overview, VM detail, and audit reads with explicit section metadata and redaction.
- **Entry point:** `plaivid_cli/presentation/cli/dispatch.py::run_command` → `plaivid_cli/presentation/cli/reads.py`.
- **Main implementation:** `plaivid_cli/presentation/cli/reads.py`, `plaivid_cli/presentation/cli/serialization.py`.
- **Supporting modules:** `plaivid_cli/application/services.py`, `plaivid_cli/application/collection/coordinator.py`, `plaivid_cli/domain/redaction.py`.
- **Shared dependencies:** `plaivid_cli/domain/models/snapshots.py`, `plaivid_cli/domain/models/inventory.py`, `plaivid_cli/domain/models/host.py`.
- **Data models:** `InventoryData`, `VMRecord`, `HostStatus`, `HostMetrics`, `VMDetail`, `AuditEntry`, `SectionSnapshot`.
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_redaction.py`, `tests/unit/test_pvm_parsers.py`.
- **Related contracts:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md) (JSON shapes, exit codes), [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).
- **Potential impact areas:** automation consumers of `--json`, exit code semantics, redaction coverage.
- **Files that should NOT be modified:** `plaivid_cli/legacy/commands/show.py`, `plaivid_cli/legacy/commands/overview.py`, `plaivid_cli/legacy/render.py`.
- **Documentation references:** `docs/REFERENCE.md`, `README.md`.

---

### Feature: VM lifecycle operations (six actions, single and bulk)

- **Description:** `start`, `stop`, `kill`, `reset`, `pause`, `resume` with fail-closed admission, sequential dispatch, truthful outcomes, and TUI target precedence of checked rows → all inventory → highlighted row.
- **Entry point:** `plaivid_cli/presentation/cli/operations.py::_operate`; `plaivid_cli/presentation/tui/pages/virtual_machines/operations.py::VMOperationMixin`.
- **Main implementation:** `plaivid_cli/application/operations/coordinator.py`, `plaivid_cli/application/operations/planner.py`, `plaivid_cli/application/operations/results.py`.
- **Supporting modules:** `plaivid_cli/application/services.py`, `plaivid_cli/application/collection/coordinator.py`, `plaivid_cli/domain/policies.py`, `plaivid_cli/infrastructure/pvm/adapter/requests.py`, `plaivid_cli/presentation/tui/components/actions.py`.
- **Shared dependencies:** `plaivid_cli/config.py`, `plaivid_cli/domain/errors.py`, `plaivid_cli/domain/redaction.py`.
- **Data models:** `plaivid_cli/domain/models/enums.py::Action`, `OperationPlan`, `OperationResult`, `TargetOutcome`, `PvmReply`, `OperationState`, `VMRecord`.
- **Tests:** `tests/unit/test_application_operations.py`, `tests/unit/test_operation_policy.py`, `tests/unit/test_cli_and_tui.py`, `tests/unit/test_multi_select.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
- **Potential impact areas:** mutation generation barriers, bulk admission policy, CLI exit codes, TUI action dropdown, post-action reconciliation.
- **Files that should NOT be modified:** `plaivid_cli/legacy/actions/` (retired action registry), `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` (historical report).
- **Documentation references:** `README.md`, `docs/REFERENCE.md`, [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md), `docs/REAL_PVM_VALIDATION.md`.

---

### Feature: Session management and credential safety

- **Description:** Resume cached token, explicit login under the argv-risk gate, logout, private atomic token cache.
- **Entry point:** `plaivid_cli/application/session.py::SessionManager` (used by `plaivid_cli/presentation/cli/operations.py::_session` and `plaivid_cli/presentation/tui/session.py::SessionMixin`).
- **Main implementation:** `plaivid_cli/application/session.py`.
- **Supporting modules:** `plaivid_cli/infrastructure/pvm/adapter/local.py`, `plaivid_cli/presentation/tui/session.py`, `plaivid_cli/domain/redaction.py`.
- **Shared dependencies:** `plaivid_cli/config.py`, `plaivid_cli/application/ports.py`, `plaivid_cli/domain/errors.py`.
- **Data models:** `plaivid_cli/domain/models/session.py::PvmSession`; JSON cache `{"username": ..., "token": ...}`.
- **Tests:** `tests/unit/test_session_lifecycle.py`, `tests/unit/test_cli_and_tui.py`, `tests/unit/test_redaction.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
- **Potential impact areas:** login UI, CLI non-interactive behavior, session-state reset on logout, all token-bearing `sbell` calls.
- **Files that should NOT be modified:** `plaivid_cli/legacy/session.py`, `plaivid_cli/legacy/commands/logout.py`, `tests/smoke.py`.
- **Documentation references:** `README.md`, `docs/ENVIRONMENT.md`, `docs/REAL_PVM_VALIDATION.md`.

---

### Feature: Serialized read collection and section snapshots

- **Description:** One read lane with request coalescing, one bounded pending intent, per-section last-good values, freshness, and mutation barriers.
- **Entry point:** `plaivid_cli/application/collection/coordinator.py::CollectionCoordinator` (called by `PlaividApplication.refresh` and `RefreshMixin`).
- **Main implementation:** `plaivid_cli/application/collection/coordinator.py`, `plaivid_cli/application/collection/reader.py`, `plaivid_cli/application/collection/publisher.py`.
- **Supporting modules:** `plaivid_cli/application/collection/sections.py`, `plaivid_cli/application/collection/freshness.py`, `plaivid_cli/domain/inventory.py`.
- **Shared dependencies:** `plaivid_cli/application/ports.py`, `plaivid_cli/domain/models/snapshots.py`, `plaivid_cli/domain/models/enums.py`.
- **Data models:** `ApplicationSnapshot`, `SectionSnapshot`, `SourceResult`, `CollectionStatus`, `InventoryData`.
- **Tests:** `tests/unit/test_collection_coordinator.py`, `tests/unit/test_application_operations.py`, `tests/unit/test_domain_models.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).
- **Potential impact areas:** every read view, operation admission, TUI refresh cadence, stale/unavailable labels.
- **Files that should NOT be modified:** `plaivid_cli/legacy/monitoring.py`, `plaivid_cli/legacy/vms.py`, `plaivid_cli/application/collection/__init__.py` (facade only).
- **Documentation references:** [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md), `docs/ARCHITECTURE.md`, `docs/MONITORING_DASHBOARD.md`.

---

### Feature: Textual TUI shell, navigation, and theming

- **Description:** Three-tab dashboard, login gate, key bindings, responsive width classes, terminal palette adaptation.
- **Entry point:** `plaivid_cli/presentation/tui/app.py::PlaividTui` mounted by `dispatch.run_command`.
- **Main implementation:** `plaivid_cli/presentation/tui/app.py`, `plaivid_cli/presentation/tui/layout.py`, `plaivid_cli/presentation/tui/styles.py`, `plaivid_cli/presentation/theme.py`.
- **Supporting modules:** `plaivid_cli/presentation/logo.py`, `plaivid_cli/presentation/tui/components/`, `plaivid_cli/presentation/tui/pages/overview/page.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/page.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/page.py`.
- **Shared dependencies:** `plaivid_cli/presentation/charts/__init__.py`, `plaivid_cli/application/overview.py`, `plaivid_cli/domain/models/`.
- **Data models:** `plaivid_cli/presentation/theme.py::Palette` (verified via `palette_for`), `ApplicationSnapshot`.
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_tui_theme.py`, `tests/unit/test_group_palette.py`, `tests/unit/test_architecture_boundaries.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md) (presentation import restrictions), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md) (bindings).
- **Potential impact areas:** all pages, CSS selectors/ids, event handler wiring, color depth behavior.
- **Files that should NOT be modified:** `plaivid_cli/legacy/theme.py`, `plaivid_cli/legacy/render.py`, `.agents/skills/unslop/` (design guide, not runtime).
- **Documentation references:** `docs/MONITORING_DASHBOARD.md`, `docs/TUI_UNSLOP_PLAN.md`, `README.md`.

---

### Feature: Overview monitoring dashboard (telemetry cards)

- **Description:** Host/VM telemetry cards with explicit section status, N/A for missing values, NIC selection, and rediscover control.
- **Entry point:** `plaivid_cli/presentation/tui/pages/overview/page.py::OverviewPage`; snapshot rendering in `plaivid_cli/presentation/tui/pages/overview/controller.py`.
- **Main implementation:** `plaivid_cli/presentation/tui/pages/overview/controller.py`, `plaivid_cli/presentation/tui/pages/overview/host_controller.py`, `plaivid_cli/presentation/tui/pages/overview/presenter.py`.
- **Supporting modules:** `plaivid_cli/presentation/overview_metrics/`, `plaivid_cli/presentation/tui/pages/overview/components/`, `plaivid_cli/presentation/tui/components/card.py`, `plaivid_cli/application/overview.py`.
- **Shared dependencies:** `plaivid_cli/domain/overview.py`, `plaivid_cli/domain/models/host.py`, `plaivid_cli/presentation/theme.py`, `plaivid_cli/domain/redaction.py`.
- **Data models:** `LocalHostSample`, `DashboardSample`, `PhysicalNic`, `NicSample`, `HostMetrics`, `HostStatus`, `ProcessSample`, `SectionSnapshot`.
- **Tests:** `tests/unit/test_overview_monitoring.py`, `tests/unit/test_host_metrics_panels.py`, `tests/unit/test_quorum_status.py`, `tests/unit/test_pvm_uptime.py`, `tests/unit/test_dashboard_chart_refactor.py`.
- **Related contracts:** [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md), [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md).
- **Potential impact areas:** card ids/CSS, session reset (`METRIC_PANEL_IDS`), status labels, `docs/MONITORING_DASHBOARD.md`.
- **Files that should NOT be modified:** `plaivid_cli/legacy/commands/overview.py`, `plaivid_cli/legacy/render.py`, `plaivid_cli/presentation/overview_metrics/__init__.py` (facade only).
- **Documentation references:** `docs/MONITORING_DASHBOARD.md`, `docs/ENVIRONMENT.md`.

---

### Feature: Overview CPU/load charts (60-second window)

- **Description:** Two chart widgets with wall-clock 60 s pruning, strict dynamic Y scale, numeric Y-Max/Y-Mid/0 gutter, faint separate grid, sharp Braille lines, smooth Unicode time axis.
- **Entry point:** `plaivid_cli/presentation/tui/refresh.py::RefreshMixin` (tick/prune) → `plaivid_cli/presentation/tui/pages/overview/controller.py::OverviewMixin` (`_render_charts`).
- **Main implementation:** `plaivid_cli/presentation/charts/render.py`, `plaivid_cli/presentation/charts/grid.py`, `plaivid_cli/presentation/charts/widget.py`.
- **Supporting modules:** `plaivid_cli/application/overview.py`, `plaivid_cli/presentation/tui/pages/overview/components/cpu.py`, `plaivid_cli/presentation/tui/pages/overview/components/load.py`, `plaivid_cli/presentation/theme.py`.
- **Shared dependencies:** `plaivid_cli/domain/models/snapshots.py`, `plaivid_cli/domain/overview.py`, Rich `Text`, Textual `Static`.
- **Data models:** `plaivid_cli/presentation/charts/render.py::Series` (verified via `render_chart`), `OverviewHistory`, `LocalHostSample`.
- **Tests:** `tests/unit/test_charts.py`, `tests/unit/test_graph_history.py`, `tests/unit/test_background_graphs.py`, `tests/unit/test_dashboard_chart_refactor.py`, `tests/unit/test_multi_select.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../decisions/ADR/README.md`](../decisions/ADR/README.md).
- **Potential impact areas:** chart widget kwargs (`palette`, `y_labels`), `PLAIVID_CHART` mode, 1 Hz redraw behavior, `ChartView` compatibility with `Static`.
- **Files that should NOT be modified:** `plaivid_cli/presentation/charts/__init__.py` (facade only), `plaivid_cli/legacy/render.py`, `plaivid_cli/presentation/overview_metrics/` (unrelated text formatters).
- **Documentation references:** `docs/MONITORING_DASHBOARD.md`, `docs/ENVIRONMENT.md`, [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md).

---

### Feature: VM inventory page (search, multi-select, detail, bulk scope)

- **Description:** Local search without PVM reads, UUID-stable selection, checked-row-first action targeting, all-target toggle, selected-VM detail panel (aligned, colour-coded, scrollable, with explicit loading/failure states; native node and console port from the inventory read, console kind from the on-demand detail read, hostname appended only for the proven local node).
- **Entry point:** `plaivid_cli/presentation/tui/pages/virtual_machines/page.py::VirtualMachinePage`.
- **Main implementation:** `plaivid_cli/presentation/tui/pages/virtual_machines/selection.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/controller.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/components/inventory.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/components/details.py`.
- **Supporting modules:** `plaivid_cli/presentation/tui/components/checkable_table.py`, `plaivid_cli/presentation/tui/components/inventory_toolbar.py`, `plaivid_cli/presentation/tui/components/formatting.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/components/summary.py`.
- **Shared dependencies:** `plaivid_cli/application/services.py`, `plaivid_cli/domain/models/inventory.py`, `plaivid_cli/presentation/theme.py`.
- **Data models:** `InventoryData`, `VMRecord`, `VMDetail`, `SectionSnapshot`.
- **Tests:** `tests/unit/test_cli_and_tui.py`, `tests/unit/test_multi_select.py`, `tests/unit/test_vm_detail_panel.py`, `tests/unit/test_architecture_boundaries.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
- **Potential impact areas:** selection state on `PlaividTui`, scope labels, `CheckRequested` messages, sibling-page import ban.
- **Files that should NOT be modified:** `plaivid_cli/presentation/tui/pages/virtual_desktops/` (separate page), `plaivid_cli/legacy/vms.py`.
- **Documentation references:** `README.md`, `docs/MONITORING_DASHBOARD.md`.

---

### Feature: Virtual Desktop inventory and lifecycle actions

- **Description:** Desktop tab mirroring the VM page's summary/search/action/audit layout, with an unfiltered running/total summary (local or cluster `running`/`started`), checked bulk subsets, an all-inventory fallback, its own conservative refresh cadence, and six actions.
- **Entry point:** `plaivid_cli/presentation/tui/pages/virtual_desktops/page.py::VirtualDesktopPage`.
- **Main implementation:** `plaivid_cli/presentation/tui/pages/virtual_desktops/controller.py`, `plaivid_cli/application/operations/desktop_executor.py`.
- **Supporting modules:** `plaivid_cli/infrastructure/pvm/desktops.py`, `plaivid_cli/infrastructure/pvm/adapter/requests.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/policy.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/components/summary.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/components/inventory.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/components/details.py`.
- **Shared dependencies:** `plaivid_cli/application/operations/coordinator.py`, `plaivid_cli/domain/desktops.py`, `plaivid_cli/domain/models/operations.py`.
- **Data models:** `plaivid_cli/domain/desktops.py::VirtualDesktop`, `OperationPlan`, `OperationResult`, `SectionSnapshot`.
- **Tests:** `tests/unit/test_virtual_desktops.py`, `tests/unit/test_multi_select.py`, `tests/unit/test_architecture_boundaries.py`.
- **Related contracts:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).
- **Potential impact areas:** shared mutation lane, `DESKTOP_QUERY`, checked-subset and all-target admission, Desktop row/selection state.
- **Files that should NOT be modified:** `plaivid_cli/presentation/tui/pages/virtual_machines/` (sibling page), `openspec/changes/add-virtual-desktop-management/tasks.md` (historical spec).
- **Documentation references:** `README.md`, `docs/REAL_PVM_VALIDATION.md`, `openspec/changes/add-virtual-desktop-management/design.md`.

---

### Feature: Read-only audit view

- **Description:** Optional bounded, read-only SQLite `Log` view in CLI and TUI panels; unavailable schema does not break other views.
- **Entry point:** `plaivid_cli/presentation/cli/reads.py::_audit`; `plaivid_cli/presentation/tui/audit.py::AuditMixin`.
- **Main implementation:** `plaivid_cli/infrastructure/audit.py`, `plaivid_cli/application/services.py`.
- **Supporting modules:** `plaivid_cli/presentation/cli/serialization.py`, `plaivid_cli/presentation/tui/refresh.py`, `plaivid_cli/domain/redaction.py`.
- **Shared dependencies:** `plaivid_cli/application/ports.py::AuditGateway`, `plaivid_cli/domain/errors.py`.
- **Data models:** `plaivid_cli/domain/models/audit.py::AuditEntry`, `AuditSummary`.
- **Tests:** `tests/unit/test_audit_adapter.py`, `tests/unit/test_cli_and_tui.py`.
- **Related contracts:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md).
- **Potential impact areas:** audit panel ids (`audit-panel`, `desktop-audit-panel`), `--limit` bounds 1–500, redaction of command text.
- **Files that should NOT be modified:** `plaivid_cli/legacy/logs.py`, `plaivid_cli/legacy/commands/log.py`, the PVM-owned database itself.
- **Documentation references:** `README.md`, `docs/REFERENCE.md`, `docs/REAL_PVM_VALIDATION.md`.

---

### Feature: Local PVM protocol adapter and parsers

- **Description:** Repository-evidenced `sbell` argv request shapes, XML envelope handling, and pure parsers for inventory, host, detail, dashboard, NIC list, and desktops.
- **Entry point:** `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter` (wired only in `bootstrap.build_runtime`).
- **Main implementation:** `plaivid_cli/infrastructure/pvm/adapter/local.py`, `plaivid_cli/infrastructure/pvm/adapter/requests.py`, `plaivid_cli/infrastructure/pvm/sbell.py`, `plaivid_cli/infrastructure/pvm/parsers/common.py`, `plaivid_cli/infrastructure/pvm/parsers/inventory.py`, `plaivid_cli/infrastructure/pvm/parsers/host.py`, `plaivid_cli/infrastructure/pvm/parsers/vm_detail.py`.
- **Supporting modules:** `plaivid_cli/infrastructure/process.py`, `plaivid_cli/infrastructure/pvm/overview.py`, `plaivid_cli/infrastructure/pvm/desktops.py`, `plaivid_cli/infrastructure/pvm/uptime.py`.
- **Shared dependencies:** `plaivid_cli/application/ports.py`, `plaivid_cli/domain/errors.py`, `plaivid_cli/domain/redaction.py`, `plaivid_cli/infrastructure/diagnostics.py`.
- **Data models:** `SourceResult`, `PvmReply`, `ObjectVM`, `ProcessObservation`, `HostStatus`, `HostMetrics`, `VMDetail`, `VirtualDesktop`, `DashboardSample`, `PhysicalNic`.
- **Tests:** `tests/unit/test_pvm_adapter.py`, `tests/unit/test_pvm_parsers.py`, `tests/unit/test_sbell_client.py`, `tests/unit/test_monitoring_metrics_parser.py`, `tests/unit/test_nic_list_parser.py`, `tests/unit/test_process_runner.py`, `tests/unit/test_pvm_uptime.py`.
- **Related contracts:** [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md), [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md).
- **Potential impact areas:** every read/mutation, fail-closed parsing, truncation handling, credential argv gate.
- **Files that should NOT be modified:** `plaivid_cli/legacy/transport.py`, `plaivid_cli/legacy/monitoring.py`, `tests/fixtures/README.md` (states fixture provenance).
- **Documentation references:** `docs/SBELL-SABAD.md`, `docs/REAL_PVM_VALIDATION.md`, `tests/fixtures/README.md`.

---

### Feature: Local host monitoring and NIC sampling

- **Description:** Read-only `/proc` and sysfs sampling for CPU, memory, load, processes, and physical NIC counters; dashboard/NIC-list parsers stay conservative.
- **Entry point:** `plaivid_cli/infrastructure/local_monitor.py::LinuxMonitor` via `LocalPvmAdapter.local_host` / `nic_samples` / `physical_nics`.
- **Main implementation:** `plaivid_cli/infrastructure/local_monitor.py`, `plaivid_cli/infrastructure/pvm/overview.py`.
- **Supporting modules:** `plaivid_cli/application/collection/reader.py`, `plaivid_cli/presentation/tui/pages/overview/presenter.py`, `plaivid_cli/application/overview.py`.
- **Shared dependencies:** `plaivid_cli/domain/overview.py`, `plaivid_cli/infrastructure/process.py` (for `systemctl status sballd`).
- **Data models:** `LocalHostSample`, `DashboardSample`, `PhysicalNic`, `NicSample`, `ProcessSample`.
- **Tests:** `tests/unit/test_overview_monitoring.py`, `tests/unit/test_nic_list_parser.py`, `tests/unit/test_graph_history.py`.
- **Related contracts:** [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md), [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md).
- **Potential impact areas:** Overview charts, N/A rendering, NIC tabs, background sampling while another tab is active.
- **Files that should NOT be modified:** `plaivid_cli/legacy/monitoring.py`, `tests/fixtures/monitoring-metrics.xml` (synthetic fixture).
- **Documentation references:** `docs/MONITORING_DASHBOARD.md`, `docs/ENVIRONMENT.md`.

---

### Feature: Secret redaction and security boundaries

- **Description:** Pure redaction applied to CLI human/JSON output, TUI text, diagnostics, and adapter errors; default-deny credential argv gate.
- **Entry point:** `plaivid_cli/domain/redaction.py::redact_text`.
- **Main implementation:** `plaivid_cli/domain/redaction.py`, `plaivid_cli/infrastructure/diagnostics.py`, `plaivid_cli/presentation/cli/serialization.py`.
- **Supporting modules:** `plaivid_cli/infrastructure/pvm/adapter/local.py`, `plaivid_cli/application/session.py`, `plaivid_cli/presentation/tui/audit.py`, `plaivid_cli/infrastructure/process.py`.
- **Shared dependencies:** `plaivid_cli/config.py`, `plaivid_cli/domain/errors.py`.
- **Data models:** `AppError`, `Settings`, `PvmSession`; process `full_command` is deliberately never displayed.
- **Tests:** `tests/unit/test_redaction.py`, `tests/unit/test_cli_and_tui.py`, `tests/unit/test_session_lifecycle.py`.
- **Related contracts:** [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md), [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
- **Potential impact areas:** any new output surface, log records, process-argument handling, synthetic-secret regressions.
- **Files that should NOT be modified:** `docs/REAL_PVM_VALIDATION.md` (owner-run plan), `.gitignore` (already excludes state).
- **Documentation references:** `README.md`, `docs/ENVIRONMENT.md`, `docs/REAL_PVM_VALIDATION.md`.

---

### Feature: Packaging and distribution (internal capability)

- **Description:** Wheel-based packaging of the active runtime only; legacy is explicitly filtered; console script declares the `plaivid` command.
- **Entry point:** `pyproject.toml` (`[project.scripts]`, `[tool.setuptools.packages.find]`) and `setup.py::RuntimeBuildPy`.
- **Main implementation:** `setup.py`, `pyproject.toml`, `scripts/setup.sh`.
- **Supporting modules:** `plaivid_cli/version.py`, `plaivid_cli/bootstrap.py`, `plaivid_cli/__main__.py`.
- **Shared dependencies:** `README.md` (readme metadata), `assets/plaivid-logo.svg` (not packaged; `include_package_data=False`).
- **Data models:** none (build metadata only).
- **Tests:** `tests/unit/test_distribution.py`, `tests/unit/test_setup_script.py`, `tests/unit/test_bootstrap.py`.
- **Related contracts:** [`../workflows/BUILD.md`](../workflows/BUILD.md), [`../workflows/RELEASE.md`](../workflows/RELEASE.md), [`MODULE_INDEX.md`](MODULE_INDEX.md).
- **Potential impact areas:** installed package list, console script availability, version reported to users.
- **Files that should NOT be modified:** `plaivid_cli/legacy/` (intentionally excluded), `docs/architecture/adr/0010-packaging.md` (historical proposal).
- **Documentation references:** `README.md`, `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`, `docs/architecture/adr/README.md`.

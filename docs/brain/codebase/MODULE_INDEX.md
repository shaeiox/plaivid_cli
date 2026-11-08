# Module index — canonical vs legacy

**Use this document before editing anything.** It identifies the implementation that should be
modified for future development. Navigation: [`../README.md`](../README.md) ·
[`FILE_CATALOG.md`](FILE_CATALOG.md) · [`REPOSITORY_MAP.md`](REPOSITORY_MAP.md) ·
[`FEATURE_TO_FILE_MAP.md`](FEATURE_TO_FILE_MAP.md).

## Legend

| Label | Meaning |
|---|---|
| **CANONICAL** | Modify this for runtime behavior. |
| **FACADE** | Re-export only; change the implementation module, not the facade (keep its `__all__` in sync). |
| **SHIM** | Compatibility/lazy import layer; do not add behavior. |
| **LEGACY** | Retired, checkout-only, excluded from wheels/Ruff/Pyright/coverage. Do not modify for runtime work. |
| **OVERLAP** | Two implementations or constants with overlapping purpose; the canonical one is named. |

## Canonical modules by responsibility

| Responsibility | Canonical module | Public surface |
|---|---|---|
| Process entry / composition | **CANONICAL** `plaivid_cli/bootstrap.py` | `main`, `build_runtime`, `Runtime` |
| Configuration | **CANONICAL** `plaivid_cli/config.py` | `load_settings`, `Settings`, `ConfigurationError` |
| Outbound interfaces | **CANONICAL** `plaivid_cli/application/ports.py` | `PvmGateway`, `MonitoringGateway`, `AuditGateway` |
| Read use cases / selector resolution | **CANONICAL** `plaivid_cli/application/services.py` | `PlaividApplication`, `TargetSelection`, `as_inventory` |
| Read lane | **CANONICAL** `plaivid_cli/application/collection/coordinator.py` | `CollectionCoordinator`, `CollectionSuperseded` |
| Section reads / publication | **CANONICAL** `plaivid_cli/application/collection/reader.py`, `plaivid_cli/application/collection/publisher.py` | `SectionReader`, `publish_results` |
| Section validation / freshness | **CANONICAL** `plaivid_cli/application/collection/sections.py`, `plaivid_cli/application/collection/freshness.py` | `normalize_sections`, `section_is_fresh` |
| Mutation lane | **CANONICAL** `plaivid_cli/application/operations/coordinator.py` | `OperationCoordinator` |
| Admission / results / desktops | **CANONICAL** `plaivid_cli/application/operations/planner.py`, `plaivid_cli/application/operations/results.py`, `plaivid_cli/application/operations/desktop_executor.py` | `OperationPlanner`, `aggregate_state`, `DesktopOperationExecutor` |
| Session/token | **CANONICAL** `plaivid_cli/application/session.py` | `SessionManager`, `SessionStore` |
| Overview scheduling/history | **CANONICAL** `plaivid_cli/application/overview.py` | `OverviewSchedule`, `OverviewHistory`, `window_points`, `health` |
| Domain values / enums | **CANONICAL** `plaivid_cli/domain/models/audit.py`, `plaivid_cli/domain/models/enums.py`, `plaivid_cli/domain/models/host.py`, `plaivid_cli/domain/models/inventory.py`, `plaivid_cli/domain/models/operations.py`, `plaivid_cli/domain/models/session.py`, `plaivid_cli/domain/models/snapshots.py`, `plaivid_cli/domain/models/__init__.py` | dataclasses, StrEnums, `canonical_uuid` |
| Domain logic | **CANONICAL** `plaivid_cli/domain/inventory.py`, `plaivid_cli/domain/policies.py`, `plaivid_cli/domain/redaction.py`, `plaivid_cli/domain/errors.py` | `merge_inventory`, `bulk_may_dispatch`, `redact_text`, `AppError` |
| Child execution | **CANONICAL** `plaivid_cli/infrastructure/process.py` | `ProcessRunner`, `ProcessResult` |
| PVM gateway / requests | **CANONICAL** `plaivid_cli/infrastructure/pvm/adapter/local.py`, `plaivid_cli/infrastructure/pvm/adapter/requests.py` | `LocalPvmAdapter`, `VM_QUERY`, `DESKTOP_QUERY`, `DASHBOARD_QUERY` |
| `sbell` client | **CANONICAL** `plaivid_cli/infrastructure/pvm/sbell.py` | `SbellClient`, `SbellResponse` |
| Parsers | **CANONICAL** `plaivid_cli/infrastructure/pvm/parsers/`, `plaivid_cli/infrastructure/pvm/overview.py`, `plaivid_cli/infrastructure/pvm/desktops.py`, `plaivid_cli/infrastructure/pvm/uptime.py` | `parse_*` functions |
| Local host sampling / audit / logging | **CANONICAL** `plaivid_cli/infrastructure/local_monitor.py`, `plaivid_cli/infrastructure/audit.py`, `plaivid_cli/infrastructure/diagnostics.py` | `LinuxMonitor`, `ReadOnlyAuditAdapter`, `configure_logging` |
| CLI | **CANONICAL** `plaivid_cli/presentation/cli/parser.py`, `plaivid_cli/presentation/cli/dispatch.py`, `plaivid_cli/presentation/cli/reads.py`, `plaivid_cli/presentation/cli/operations.py`, `plaivid_cli/presentation/cli/serialization.py` | `build_parser`, `run_command`, handlers |
| TUI app / mixins | **CANONICAL** `plaivid_cli/presentation/tui/app.py`, `plaivid_cli/presentation/tui/layout.py`, `plaivid_cli/presentation/tui/session.py`, `plaivid_cli/presentation/tui/refresh.py`, `plaivid_cli/presentation/tui/audit.py`, `plaivid_cli/presentation/tui/styles.py` | `PlaividTui`, mixins, `TUI_CSS` |
| TUI pages | **CANONICAL** `plaivid_cli/presentation/tui/pages/overview/`, `plaivid_cli/presentation/tui/pages/virtual_machines/`, `plaivid_cli/presentation/tui/pages/virtual_desktops/` | `OverviewPage`, `VirtualMachinePage`, `VirtualDesktopPage` |
| Shared widgets | **CANONICAL** `plaivid_cli/presentation/tui/components/` | `DashboardCard`, `CheckableTable`, `InventoryToolbar` |
| Telemetry formatters | **CANONICAL** `plaivid_cli/presentation/overview_metrics/` | `*_body`, `body`, `finish` |
| Charts | **CANONICAL** `plaivid_cli/presentation/charts/grid.py`, `plaivid_cli/presentation/charts/render.py`, `plaivid_cli/presentation/charts/widget.py` | `render_chart`, `dynamic_top`, `ChartView` |
| Theme / wordmark | **CANONICAL** `plaivid_cli/presentation/theme.py`, `plaivid_cli/presentation/logo.py` | `palette_for`, `apply_theme`, `logo_text` |

## Re-export facades (FACADE)

| Path | Re-exports | Notes |
|---|---|---|
| `plaivid_cli/domain/models/__init__.py` | 32 names from 7 model modules | Highest fan-in (53 importing modules); rename exports with care. |
| `plaivid_cli/presentation/cli/__init__.py` | `run_command`, `build_parser`, `configuration_command`, exit constants | Used by `bootstrap.py`. |
| `plaivid_cli/presentation/charts/__init__.py` | 22 names from `render.py` + `widget.py` | `bucketed` is defined in `grid.py` and re-exported through `render.py`. |
| `plaivid_cli/presentation/overview_metrics/__init__.py` | 17 names (primitives + `*_body`) | Formatter surface for TUI controllers. |
| `plaivid_cli/presentation/tui/components/__init__.py` | 8 names | Shared widgets for all pages. |
| `plaivid_cli/application/collection/__init__.py`, `plaivid_cli/application/operations/__init__.py` | coordinator classes / `aggregate_state` | Package-level API. |
| `plaivid_cli/infrastructure/pvm/adapter/__init__.py`, `plaivid_cli/infrastructure/pvm/parsers/__init__.py` | gateway, query constants, parsers | Keep in sync when adding parsers. |
| `plaivid_cli/presentation/tui/pages/overview/components/__init__.py`, `plaivid_cli/presentation/tui/pages/virtual_machines/components/__init__.py`, `plaivid_cli/presentation/tui/pages/virtual_desktops/components/__init__.py` | page component classes | Page-local facades. |
| `plaivid_cli/__init__.py` | `__version__` | Docstring still mentions the retired `orchestrator`; that text is stale, the export is current. |

## Compatibility shims (SHIM)

| Path | Purpose | Rule |
|---|---|---|
| `plaivid_cli/presentation/tui/pages/overview/__init__.py` | `__getattr__` lazily exposes `OverviewPage` under `TYPE_CHECKING` | Deferred import only; do not place behavior here. |
| `plaivid_cli/__main__.py`, `plaivid` | Alternate process launchers into `bootstrap.main` | No logic; keep as thin shims. |
| `plaivid_cli/presentation/overview_metrics/common.py::finish` | Legacy status-footer helper retained for an existing unit-test contract (`tests/unit/test_host_metrics_panels.py`) | Prefer `body` for new rendering; keep `finish` until that test/contract is retired. |

## Legacy / retired (LEGACY)

| Path | Status | Evidence |
|---|---|---|
| `plaivid_cli/legacy/` (root modules, `legacy/actions/`, `legacy/commands/`) | Retired, checkout-only, excluded from distribution and static checks | `setup.py::RuntimeBuildPy`, `[tool.setuptools.packages.find]` in `pyproject.toml`, `tests/unit/test_distribution.py`, `docs/ARCHITECTURE.md` |
| `tests/smoke.py` | Opt-in real-host script that imports `plaivid_cli.legacy` | Its module docstring; excluded from unit runs |
| `REFACTOR.md`, `TASKS.md` | Historical design notes for the retired command/action registries | Their own headers |
| `docs/architecture/01-repository-audit.md` … `docs/architecture/07-validated-architecture.md` | Historical audit snapshots | `docs/architecture/adr/README.md` |

**No module in the active runtime is explicitly marked "deprecated" in code.** The repository
uses the word *retired/legacy* for the archived implementation; there is no deprecation
decorator, warning, or removal schedule. Do not infer one.

No active module imports `plaivid_cli/legacy/`. Legacy imports only
`plaivid_cli/version.py`, `plaivid_cli/config.py`, and `plaivid_cli/__init__.py` from the active
tree. Verified by an AST import scan; see
[`../architecture/DEPENDENCY_GRAPH.md`](../architecture/DEPENDENCY_GRAPH.md).

## Duplicate / overlapping implementations (OVERLAP)

| Pair | Canonical choice | Reason / evidence |
|---|---|---|
| `plaivid_cli/presentation/charts/render.py::dynamic_top` (strict, window-based) vs `stable_top` (legacy hysteresis) | Use `dynamic_top` for dashboard CPU/load scaling; keep `stable_top` only for its `strict=False` hysteresis compatibility path and existing tests. | `plaivid_cli/presentation/tui/pages/overview/controller.py::OverviewMixin`, `tests/unit/test_charts.py`, `tests/unit/test_dashboard_chart_refactor.py` |
| `plaivid_cli/presentation/overview_metrics/common.py::body` vs `finish` | `body` for all current card/panel rendering; `finish` is retained for a standalone status contract. | `tests/unit/test_host_metrics_panels.py`, `docs/MONITORING_DASHBOARD.md` |
| `EXIT_PARTIAL = 3` in `plaivid_cli/presentation/cli/operations.py` and again in `plaivid_cli/presentation/cli/dispatch.py` | `cli/operations.py` holds the full exit-code set; `dispatch.py` re-declares the same value. Both are current code; do not change one without the other. | source of both modules |
| `__version__` in `plaivid_cli/version.py` (`1.2.0`) vs `version = "0.4.0"` in `pyproject.toml` | `plaivid_cli/version.py` is authoritative for `--version`; the mismatch is a known, **unresolved** packaging inconsistency. | `plaivid_cli/presentation/cli/parser.py::build_parser`, [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md) |
| Flat module names in `docs/ARCHITECTURE.md` / `docs/REFERENCE.md` (e.g. `presentation/tui.py`, `application/collection.py`) vs actual packages | Actual packages under `plaivid_cli/presentation/` and `plaivid_cli/application/collection/` are canonical; the flat paths do not exist. | `docs/ARCHITECTURE.md`, [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md) |
| `docs/architecture/adr/0010-packaging.md` proposes a PyInstaller bundle vs actual setuptools wheel | Actual build is `python -m build --wheel` with `setup.py`; the ADR records a conditional proposal, not shipped behavior. | [`../workflows/BUILD.md`](../workflows/BUILD.md) |

## Which implementation should be modified?

1. Everything user-visible in the shipped application → the **CANONICAL** row above.
2. Public re-exports → edit the implementation module, then update the **FACADE**'s `__all__`.
3. Do not add behavior to **SHIM** modules.
4. Never fix a runtime bug in `plaivid_cli/legacy/`, `tests/smoke.py`, `REFACTOR.md`, or
   `TASKS.md` unless the task explicitly targets the retired implementation.
5. Before editing, confirm the file exists and check
   [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md) plus the related tests
   in [`../workflows/TESTING.md`](../workflows/TESTING.md).

# Entry points

Every entry point below is verified against source/config. The `path.py::Symbol` convention is
checked by `scripts/validate_brain.py`. Navigation: [`../README.md`](../README.md) ·
[`FILE_CATALOG.md`](FILE_CATALOG.md) · [`../architecture/DATA_FLOW.md`](../architecture/DATA_FLOW.md).

## Process entry points

| Entry point | Execution path | Next modules |
|---|---|---|
| `plaivid` console script (`[project.scripts]` in `pyproject.toml`) | `plaivid_cli.bootstrap:main` → `plaivid_cli/bootstrap.py::main` | `plaivid_cli/presentation/cli/parser.py::build_parser`, `plaivid_cli/config.py::load_settings`, `plaivid_cli/bootstrap.py::build_runtime`, `plaivid_cli/presentation/cli/dispatch.py::run_command` |
| `./plaivid` (checkout launcher) | `from plaivid_cli.bootstrap import main`; `raise SystemExit(main())` | same as console script |
| `python -m plaivid_cli` | `plaivid_cli/__main__.py` → `bootstrap.main` | same as console script |
| `plaivid_cli/bootstrap.py::main` | parse → `help` short-circuit or `load_settings` → config/diagnostics short-circuit → `configure_logging` → `build_runtime` → `run_command` → `finally: Runtime.close()` | `plaivid_cli/infrastructure/diagnostics.py::configure_logging`, `plaivid_cli/bootstrap.py::Runtime` |
| `plaivid_cli/bootstrap.py::build_runtime` | one `ProcessRunner` → `SbellClient` → `LocalPvmAdapter` → `CollectionCoordinator` → `ReadOnlyAuditAdapter` → `PlaividApplication` → `OperationCoordinator` → `SessionManager`/`SessionStore` | `plaivid_cli/infrastructure/process.py::ProcessRunner`, `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter` |

`--help`, `--version`, `help`, `config`, `diagnostics` return **before** `build_runtime`;
verified by `tests/unit/test_bootstrap.py`. `plaivid_cli/presentation/cli/parser.py::build_parser`
adds `--version` with `plaivid_cli/version.py::__version__`.

## CLI commands (`plaivid_cli/presentation/cli/parser.py::build_parser`)

| Command | Handler / execution path | Exit codes |
|---|---|---|
| `plaivid` / `plaivid tui` | `dispatch.run_command` TTY check → `plaivid_cli/presentation/tui/app.py::PlaividTui(...).run()` | 0 / 2 (non-TTY) |
| `inventory [--json]` | `_session` → `PlaividApplication.inventory` → `plaivid_cli/presentation/cli/reads.py::_inventory` → `_section_payload`/`_print_json` | 0 current, 3 partial |
| `host` / `status` / `overview [--json]` | `_session` → `PlaividApplication.refresh(sections=("host_status","host_metrics"))` → `reads.py::_host` | 0 current, 3 partial |
| `detail UUID [--json]` | `_session` → `PlaividApplication.detail` → `reads.py::_detail` | 0 current, 3 partial |
| `audit [--limit 1..500] [--json]` | `PlaividApplication.recent_audit` → `ReadOnlyAuditAdapter.recent` → `reads.py::_audit` | 0 / 3 |
| `config` / `diagnostics [--json]` | `plaivid_cli/presentation/cli/serialization.py::configuration_command` (no PVM runtime) | 0 |
| `logout` | `SessionManager.logout` or `clear_local_cache` | 0 |
| `help`, `--help`, `--version` | parser help/version (no PVM runtime) | 0 |
| `start` / `stop` / `kill` / `reset` / `pause` / `resume TARGET... [--json]` | `_session` → `PlaividApplication.inventory` → `resolve_targets` → `OperationCoordinator.create_plan` → `execute` → `plaivid_cli/presentation/cli/operations.py::_operate` | 0 / 1 / 2 / 3 / 4 |

Target selectors and the outcome→exit mapping: [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).

## TUI initialization and event handlers

- **Composition:** `plaivid_cli/presentation/tui/layout.py::LayoutMixin` yields `OverviewPage`
  (`id="overview"`), `VirtualMachinePage` (`id="fleet"`), `VirtualDesktopPage`
  (`id="desktops"`) inside `TabbedContent(initial="overview", id="tabs")`.
- **Mount:** `PlaividTui.on_mount` applies theme, sets tooltips/group boxes, adds DataTable
  columns, hides tabs until login, calls `_set_width_class`, starts
  `set_interval(0.5, self._tick)`, and calls `_resume_session`.
- **Login/logout:** `plaivid_cli/presentation/tui/session.py::SessionMixin` with
  `@work(thread=True, group="session", exclusive=True)` workers `_resume_session`,
  `_perform_login`, `_perform_logout`.
- **Key bindings** (`PlaividTui.BINDINGS`): `space` toggle_check, `a` toggle_all, `r` refresh,
  `enter` details, `q` quit, `1` overview_page, `2` vms_page, `3` desktops_page.
- **Decorated handlers on `PlaividTui`** (`@on(...)`): `submit_login`, `submit_logout`,
  `tab_activated`, `refresh_button`, `show_audit`, `show_desktop_audit`, `apply_interval`,
  `desktop_search_changed`, `desktop_scope_changed`, `desktop_row_highlighted`,
  `desktop_action_requested`, `vm_scope_changed`, `vm_search_changed`, `check_requested`,
  `row_highlighted`, `bulk_action_selected`. They delegate to the corresponding mixin methods;
  Textual discovers decorated handlers on the concrete `App` class.
- **Message producers:** `plaivid_cli/presentation/tui/components/checkable_table.py::CheckableTable`
  posts `CheckRequested`; `InventoryToolbar` emits `Input.Changed`, `Checkbox.Changed`,
  `Select.Changed`, `Button.Pressed`.

## Background services and scheduled work

| Kind | Implementation | Path |
|---|---|---|
| One serialized read worker | `ThreadPoolExecutor(max_workers=1, thread_name_prefix="plaivid-read")` plus one bounded pending intent | `plaivid_cli/application/collection/coordinator.py::CollectionCoordinator` |
| One serialized mutation lane | `threading.Lock` + closing `Event` | `plaivid_cli/application/operations/coordinator.py::OperationCoordinator` |
| TUI refresh worker | `@work(thread=True, group="refresh", exclusive=False)` `_collect_visible` | `plaivid_cli/presentation/tui/refresh.py::RefreshMixin` |
| TUI audit worker | `@work(thread=True, group="audit", exclusive=True)` `_request_audit` | `plaivid_cli/presentation/tui/audit.py::AuditMixin` |
| TUI operation worker | `@work(thread=True, group="operation", exclusive=False)` `_execute_action` | `plaivid_cli/presentation/tui/pages/virtual_machines/operations.py::VMOperationMixin` |
| 0.5 s app timer | `set_interval(0.5, self._tick)` in `on_mount` | `plaivid_cli/presentation/tui/app.py::PlaividTui` |
| 1 Hz chart tick | `_chart_tick_due` + `OverviewHistory.prune(time.monotonic())` while Overview is active | `plaivid_cli/presentation/tui/refresh.py::RefreshMixin`, `plaivid_cli/application/overview.py::OverviewHistory` |
| Collection cadence | `OverviewSchedule` (1–60 s local control, `host_status_interval`, 18 s PVM batch floor) and `MIN_REFRESH_SECONDS = 15.0` for Desktops | `plaivid_cli/application/overview.py::OverviewSchedule`, `plaivid_cli/presentation/tui/pages/virtual_desktops/policy.py::MIN_REFRESH_SECONDS` |

**No OS-level scheduled jobs, daemon, systemd unit, cron entry, or HTTP API endpoint exists in
this repository.** External "APIs" are the local `sbell` command argv protocol and the
read-only SQLite audit database; see [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).

## Build, test, and documentation entry points

| Entry point | Command / target | Notes |
|---|---|---|
| Wheel build | `python -m build --wheel` (`setup.py::RuntimeBuildPy`, `pyproject.toml`) | [`../workflows/BUILD.md`](../workflows/BUILD.md) |
| Developer setup | `./scripts/setup.sh` | [`../workflows/DEVELOPMENT.md`](../workflows/DEVELOPMENT.md) |
| Unit tests | `python -m pytest -q --ignore=tests/smoke.py` | `tests/unit/`, [`../workflows/TESTING.md`](../workflows/TESTING.md) |
| Lint / typecheck | `ruff check plaivid_cli tests/unit`, `pyright` | `pyproject.toml` |
| Brain audit | `python scripts/validate_brain.py` | `scripts/validate_brain.py::main`, [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md) |
| Opt-in real-host smoke (legacy) | `PLAIVID_PASS=... python3 tests/smoke.py` | imports `plaivid_cli/legacy/`; owner-run only, never part of unit CI |

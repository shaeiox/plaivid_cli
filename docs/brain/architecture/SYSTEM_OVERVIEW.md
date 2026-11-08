# System overview

**Status:** verified from source, configuration, tests, and existing documentation.
Inferred observations are labelled. See [`../README.md`](../README.md) for navigation.

## Purpose

`plaivid_cli` lets an operator inspect and operate Plaivid PVM virtual machines **from the
Linux host that already provides the PVM tooling**. It is a local client: it invokes the
configured `sbell` executable and the `pvm-running-vms` helper as bounded child processes.
There is no SSH transport, no remote collector, no application-owned telemetry database, and
no invented PVM endpoint. Evidence: `README.md`, `docs/ARCHITECTURE.md`,
`plaivid_cli/infrastructure/pvm/sbell.py::SbellClient`,
`plaivid_cli/infrastructure/process.py::ProcessRunner`.

## Main capabilities

| Capability | Implementation anchor |
|---|---|
| One-shot CLI reads: `inventory`, `host`/`status`/`overview`, `detail UUID`, `audit` | `plaivid_cli/presentation/cli/parser.py::build_parser`, `plaivid_cli/presentation/cli/reads.py` |
| Six lifecycle actions: `start`, `stop`, `kill`, `reset`, `pause`, `resume` | `plaivid_cli/domain/models/enums.py::Action`, `plaivid_cli/application/operations/coordinator.py::OperationCoordinator` |
| Interactive Textual dashboard with three tabs | `plaivid_cli/presentation/tui/layout.py::LayoutMixin`, `plaivid_cli/presentation/tui/app.py::PlaividTui` |
| Overview telemetry cards + 60-second CPU/load charts | `plaivid_cli/presentation/tui/pages/overview/page.py::OverviewPage`, `plaivid_cli/presentation/charts/render.py::render_chart` |
| VM inventory with local search, multi-select, detail, bulk actions | `plaivid_cli/presentation/tui/pages/virtual_machines/selection.py::VMSelectionMixin`, `plaivid_cli/presentation/tui/pages/virtual_machines/operations.py::VMOperationMixin` |
| Virtual Desktop inventory and lifecycle actions | `plaivid_cli/presentation/tui/pages/virtual_desktops/controller.py::DesktopMixin`, `plaivid_cli/application/operations/desktop_executor.py::DesktopOperationExecutor` |
| Local session-token cache, login/logout, secret redaction | `plaivid_cli/application/session.py::SessionManager`, `plaivid_cli/domain/redaction.py::redact_text` |
| Optional read-only SQLite audit view | `plaivid_cli/infrastructure/audit.py::ReadOnlyAuditAdapter` |
| Validated, redacted runtime configuration | `plaivid_cli/config.py::load_settings`, `plaivid_cli/presentation/cli/serialization.py::configuration_command` |
| `--json` output with section status/generation/source metadata | `plaivid_cli/presentation/cli/serialization.py::_section_payload` |

## Application lifecycle

1. **Process start.** `plaivid` (console script declared in `pyproject.toml`), `./plaivid`,
   or `python -m plaivid_cli` all reach `plaivid_cli/bootstrap.py::main`.
2. **Parse.** `plaivid_cli/presentation/cli/parser.py::build_parser` builds the argparse
   grammar. `--help`, `--version`, `help`, `config`, and `diagnostics` return without creating
   a PVM runtime (verified by `tests/unit/test_bootstrap.py`).
3. **Configure.** `plaivid_cli/config.py::load_settings` validates environment variables;
   an invalid value yields a configuration error and exit code 2 before any PVM work.
4. **Compose.** `plaivid_cli/bootstrap.py::build_runtime` constructs one `ProcessRunner`,
   `SbellClient`, `LocalPvmAdapter`, `CollectionCoordinator`, `ReadOnlyAuditAdapter`,
   `PlaividApplication`, `OperationCoordinator`, `SessionManager`, and `SessionStore`.
5. **Dispatch.** `plaivid_cli/presentation/cli/dispatch.py::run_command` routes one-shot
   commands, or mounts `plaivid_cli/presentation/tui/app.py::PlaividTui` when stdin/stdout
   are TTYs.
6. **Shutdown.** `bootstrap.main` always calls `bootstrap.Runtime.close`, which closes the
   operation and collection coordinators. Evidence: `tests/unit/test_bootstrap.py`.

## Major subsystems

- **Presentation** — `plaivid_cli/presentation/`: CLI handlers, Textual app/mixins/pages,
  pure telemetry text formatters, pure chart renderer, theme/CSS.
- **Application** — `plaivid_cli/application/`: read/use-case facade, single serialized
  collection lane, mutation coordinator, session management, narrow outbound `Protocol`s,
  Overview scheduling/history.
- **Domain** — `plaivid_cli/domain/`: immutable dataclasses, enums, typed errors, pure
  policies, correlation and redaction. Contains no I/O.
- **Infrastructure** — `plaivid_cli/infrastructure/`: bounded child process execution,
  `sbell`/PVM adapters and pure XML parsers, local `/proc`/sysfs monitoring, read-only
  SQLite audit, logging diagnostics.
- **Legacy** — `plaivid_cli/legacy/`: retired checkout-only implementation, excluded from
  distribution. See [`../codebase/MODULE_INDEX.md`](../codebase/MODULE_INDEX.md).

Details: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`COMPONENTS.md`](COMPONENTS.md),
[`../codebase/REPOSITORY_MAP.md`](../codebase/REPOSITORY_MAP.md).

## External integrations

| Integration | Boundary | Evidence |
|---|---|---|
| Local `sbell` command (`sudo sbell` default) | argv only, XML `<status>/<description>` envelope | `plaivid_cli/infrastructure/pvm/sbell.py::SbellClient`, `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter`, `docs/SBELL-SABAD.md` |
| `pvm-running-vms` helper | argv only, numbered text rows → process evidence | `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter`, `plaivid_cli/infrastructure/pvm/parsers/inventory.py::parse_process_rows` |
| Local Linux `/proc`, `/sys/class/net`, `systemctl status sballd` | read-only host sampling | `plaivid_cli/infrastructure/local_monitor.py::LinuxMonitor`, `plaivid_cli/infrastructure/pvm/uptime.py::sball_uptime_seconds` |
| PVM-owned SQLite `messages.db` | `mode=ro` URI, bounded query, schema check | `plaivid_cli/infrastructure/audit.py::ReadOnlyAuditAdapter` |
| Textual / Rich | terminal rendering | `pyproject.toml`, `plaivid_cli/presentation/tui/app.py::PlaividTui` |

Exact protocol forms: [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).
Fixtures are synthetic, not host captures: `tests/fixtures/README.md`.

## Execution environment

- Linux; Python **>=3.12** declared in `pyproject.toml` and enforced by `scripts/setup.sh`.
  The project uses a project-local `.venv`; setup never modifies system Python.
- Runtime dependency: `textual>=0.47` (which brings Rich). Dev extra: `pytest`,
  `pytest-cov`, `ruff`, `pyright`, `build` (`pyproject.toml`).
- Interactive TUI requires stdin **and** stdout to be TTYs; otherwise `dispatch.run_command`
  returns exit code 2 (`plaivid_cli/presentation/cli/dispatch.py::run_command`).
- Configuration is environment-only; no `.env` loader. Reference: `docs/ENVIRONMENT.md`.
- Credentials/tokens in `sbell` argv are an **unresolved risk**. Login and token-bearing
  calls are default-deny until `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` is set
  (`plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter`, `docs/ENVIRONMENT.md`).

## Important technical constraints

- **No host validation.** All real PVM behavior is PENDING MANUAL PVM VALIDATION in
  `docs/REAL_PVM_VALIDATION.md`; do not treat local tests as host evidence.
- **Truthful uncertainty.** Object state and process observations are separate; missing
  values are `None`/`N/A`, never invented zeros. `COMMAND_ACCEPTED_UNCONFIRMED` is a
  representable state that current code does not infer. See
  [`../contracts/DATA_MODELS.md`](../contracts/DATA_MODELS.md).
- **Serialized lanes.** One `ThreadPoolExecutor(max_workers=1)` for reads and one
  `threading.Lock` for mutations (`plaivid_cli/application/collection/coordinator.py::CollectionCoordinator`,
  `plaivid_cli/application/operations/coordinator.py::OperationCoordinator`).
- **Fail-closed admission.** Bulk operations require `PLAIVID_MAX_INVENTORY_AGE_SECONDS`,
  complete current inventory, matching generation, and freshness. Evidence:
  `plaivid_cli/application/operations/planner.py::OperationPlanner`, `tests/unit/test_application_operations.py`.
- **Layer boundaries are tested** by `tests/unit/test_architecture_boundaries.py`.
- **Version mismatch (verified fact).** `pyproject.toml` declares `version = "0.4.0"` while
  `plaivid_cli/version.py` exports `__version__ = "1.2.0"`; `--version` prints the latter.
  Tracked in [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md).

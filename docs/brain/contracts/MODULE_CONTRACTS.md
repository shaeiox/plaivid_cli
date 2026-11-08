# Module contracts

This document describes **boundaries between modules**, especially interfaces shared by many
consumers. For wire/command formats see [`API_CONTRACTS.md`](API_CONTRACTS.md); for value
shapes see [`DATA_MODELS.md`](DATA_MODELS.md). Navigation: [`../README.md`](../README.md).

## 1. Layer contract (enforced)

| Layer | May import | Must not import | Enforcement |
|---|---|---|---|
| `plaivid_cli/domain/` | stdlib, other `domain/` modules | application, infrastructure, presentation, bootstrap | `tests/unit/test_architecture_boundaries.py` |
| `plaivid_cli/application/` | `domain/`, `config.py`, other `application/` | infrastructure, presentation, bootstrap | same |
| `plaivid_cli/infrastructure/` | `domain/`, other `infrastructure/` | application, presentation, bootstrap | same |
| `plaivid_cli/presentation/` | `application/`, `domain/`, `config.py`, own presentation modules | infrastructure, bootstrap | same |
| TUI `components/` directories | Textual/Rich, presentation theme | application, infrastructure, bootstrap, `subprocess` | same |
| TUI page packages | own page modules, shared components | sibling page implementations | same |

`plaivid_cli/bootstrap.py` is explicitly exempt: it is the single composition root.

**Compatibility guarantee:** import direction and the single `CheckableTable` definition are
regression-tested. Breaking them fails the unit suite.

## 2. Outbound ports — `plaivid_cli/application/ports.py`

Three `typing.Protocol` definitions are the only outbound capabilities application code may
use. Infrastructure implements them structurally; there is no runtime registration or ABC
inheritance.

| Port | Methods (verified) | Inputs → outputs | Implemented by |
|---|---|---|---|
| `PvmGateway` | `login`, `validate_session`, `logout`, `list_objects`, `list_desktops`, `list_processes`, `host_status`, `host_metrics`, `vm_detail`, `tap_mapping`, `dispatch_action` | token/action/UUID → `PvmSession`, `bool`, `SourceResult[T]`, `PvmReply` | `plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter` |
| `MonitoringGateway` | `dashboard`, `local_host`, `physical_nics`, `nic_samples` | token/devices → `SourceResult` of monitoring samples | same adapter (docstring: "Optional read-only extension; existing PvmGateway implementations still work") |
| `AuditGateway` | `recent(limit)` | int → `tuple[AuditEntry, ...]` | `plaivid_cli/infrastructure/audit.py::ReadOnlyAuditAdapter` |

**Error handling:** adapter methods raise `plaivid_cli/domain/errors.py::AppError` with
`ErrorKind` and stable `code`; SectionReader converts any other exception into
`CollectionStatus.UNAVAILABLE` with a type-name message (never raw tracebacks).
**Side effects:** child processes (`sbell`, `pvm-running-vms`, `systemctl`), SQLite read, local
file reads. No network calls.

## 3. Collection contract — `plaivid_cli/application/collection/`

- **Owner:** `plaivid_cli/application/collection/coordinator.py::CollectionCoordinator` owns the
  in-memory `ApplicationSnapshot`, generation counter, mutation barrier, active/pending
  requests, and the single worker executor. No other component may mutate sections.
- **Public calls:** `snapshot()`, `request_refresh(token, *, sections)`,
  `collect_once(token, *, sections)`, `begin_mutation(...)`, `end_mutation(...)`,
  `is_fresh(section, *, max_age_seconds)`, `clear_desktop_session()`, `close()`.
- **Inputs:** `sections` is an iterable of names validated by
  `plaivid_cli/application/collection/sections.py::normalize_sections`. The 11 supported names
  are `inventory`, `objects`, `processes`, `host_status`, `host_metrics`, `tap_mapping`,
  `dashboard`, `desktops`, `local_host`, `physical_nics`, `nic_samples`; dynamic
  `detail:<canonical-uuid>` names are also accepted. Unsupported/empty requests raise
  `ValueError`.
- **Outputs:** `Future[ApplicationSnapshot]` for async requests; direct `ApplicationSnapshot`
  for `collect_once`/`snapshot`. Publication is suppressed if the mutation epoch changed.
- **State ownership:** each `SectionSnapshot` retains `value` plus `last_good_value`, status,
  generation, source, timestamps (wall + monotonic), error, and quality issues. A failed read
  keeps last-good data but labels it `STALE`/`UNAVAILABLE`.
- **Error handling:** `CollectionSuperseded` is raised on replaced pending requests; per-section
  failures are isolated (a failed `host_metrics` does not erase `inventory`).
- **Concurrency:** one `ThreadPoolExecutor(max_workers=1)`; `threading.RLock` around state;
  one bounded pending intent. `close()` prevents new admissions and waits.
- **Compatibility:** adding a section requires updating `SUPPORTED_SECTIONS`,
  `SectionReader.collect`, and the reader's source label; TUI/CLI demand lists must match.

Section → provider source labels (from `SectionReader.collect`): `objects`/`desktops`/`dashboard`/`tap_mapping`/`detail` → `user/objects` variants; `processes` → `pvm-running-vms`; `host_status` → `sball/show`; `host_metrics` → `monitoring/metrics`; `local_host` → `local /proc`; `physical_nics` → `network/nic-list`; `nic_samples` → `local sysfs`.

## 4. Operations contract — `plaivid_cli/application/operations/`

- **Owner:** `plaivid_cli/application/operations/coordinator.py::OperationCoordinator` owns the
  mutation lock, dispatch order, outcome accounting, and reconciliation.
- **Admission:** `OperationPlanner.create_plan` / `create_desktop_plan` require non-empty unique
  UUIDs, exact match with current inventory records, matching generation, current successful
  object inventory, and freshness. Bulk additionally requires a configured
  `PLAIVID_MAX_INVENTORY_AGE_SECONDS` and complete inventory
  (`plaivid_cli/domain/policies.py::bulk_may_dispatch`). Without a configured limit, single
  targets use `2 × refresh_interval`.
- **Inputs → outputs:** `execute(token, action, targets, section, *, is_bulk, plan)` →
  `OperationResult` with per-target `TargetOutcome`s and an aggregate `OperationState`.
- **Outcome mapping** (`_dispatch_one`): `status=success` → `SUCCEEDED`; `status=failed` →
  `FAILED` with errno/message; any other status, transport error, or unexpected exception →
  `OUTCOME_UNKNOWN`; `AppError` of `ErrorKind.POLICY` → `REJECTED`; `PROCESS_START_FAILED` →
  `FAILED` (not dispatched). Bulk stops on failure/unknown and marks remaining `NOT_STARTED`.
- **Aggregation:** `aggregate_state` precedence: `OUTCOME_UNKNOWN` >
  `COMMAND_ACCEPTED_UNCONFIRMED` > all `SUCCEEDED` > mixed `PARTIAL` > `FAILED` >
  `REJECTED` > `CANCELLED_BEFORE_DISPATCH`.
- **State ownership:** inventory snapshots belong to the collection coordinator; the operation
  coordinator only raises barriers (`begin_mutation`/`end_mutation`) and requests
  reconciliation through `collect_once`.
- **Side effects:** one `sbell vm/<action>` child per target, sequential; invalidation of
  affected sections; a post-operation `inventory` read. **No automatic retry, no confirmation
  prompt, no claim of terminal VM state.**
- **Compatibility:** `COMMAND_ACCEPTED_UNCONFIRMED` is representable but not produced by the
  current mapping; do not map it without host evidence (`docs/REAL_PVM_VALIDATION.md`).

## 5. Read facade / selector contract — `plaivid_cli/application/services.py`

- `PlaividApplication.refresh(token, *, sections)` → `ApplicationSnapshot`; `inventory(token)` →
  `(ApplicationSnapshot, SectionSnapshot)`; `detail(token, uuid)` → `SectionSnapshot`;
  `host_status`/`host_metrics`/`tap_mapping` → optional `SectionSnapshot`;
  `recent_audit(limit=100)` → `AuditEntry` tuple.
- `resolve_targets(inventory, selectors)` → `TargetSelection(records, is_bulk, selectors)`.
  Supported selectors: canonical UUID, exact name, unique case-insensitive name prefix, 1-based
  index, `all`, `state:<state>` (`running` matches `started`/`running`),
  `process:present|missing`. `tag:` is rejected as unsupported. Comma-separated selectors are
  split by CLI `_operate`; duplicates, ambiguity, and `all` mixed with others are rejected.
- **Error handling:** `AppError(ErrorKind.POLICY|COLLECTION|...)` with safe messages;
  `inventory_value` rejects non-current/non-partial sections.
- **Compatibility:** these signatures are consumed by both CLI and all TUI pages; changing them
  requires a coordinated update (see [`../codebase/FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md)).

## 6. Session contract — `plaivid_cli/application/session.py`

- `SessionManager.resume_or_login(*, username, password)` → `(PvmSession, bool)`;
  `SessionStore.load/save/clear`; `logout(session)`.
- **State ownership:** token cache at `Settings.session_file` (`<state_dir>/session.json`) with
  JSON keys `username`, `token`. Directory 0700, file 0600, `O_NOFOLLOW`, `O_EXCL`, atomic
  replace; symlink/ownership/permission checks reject unsafe paths. No password is persisted.
- **Side effects:** `PvmGateway.validate_session/login/logout` child processes; login and all
  token-bearing calls require `Settings.allow_credential_argv`.
- **Error handling:** `LOGIN_REQUIRED` (CLI non-interactive cache miss),
  `CREDENTIAL_ARGV_ACK_REQUIRED`, `SESSION_PATH_UNSAFE`, `SESSION_PERMISSIONS_UNSAFE`.
- **Compatibility:** the CLI `logout` command must still clear the local cache when no valid
  session exists; TUI logout must clear view state (selection, chart history, statuses).

## 7. Presentation contracts

- **CLI:** `run_command(args, *, application, operations, sessions, settings) -> int`; handlers
  return exit codes from `plaivid_cli/presentation/cli/operations.py` (0/1/2/3/4).
  `AppError` with `ErrorKind.POLICY|AUTHENTICATION` → 2, otherwise → 1;
  `OSError|ValueError` → 2. `--json` output is always redacted (`_redact_json`).
- **TUI:** `PlaividTui` is the only concrete `App`; mixins are behavior modules and must not
  define a second `App`. Event handlers are re-declared on `PlaividTui` with `@on(...)` because
  Textual discovers decorated handlers on the concrete class. Widget ids (`#tabs`, `#fleet-table`,
  `#cpu-chart`, `#load-chart`, `#audit-panel`, …) are a de-facto contract used by controllers,
  CSS, and tests.
- **Charts:** `ChartView` accepts `id`, `mode`, `palette`, `y_labels` and arbitrary extra
  composition keywords; it forwards only real `Static.__init__` parameters and ignores unknown
  hints. `render_chart` returns Rich `Text` with exactly `height` rows; grid dots are a separate
  dim style and never OR-ed into data glyphs. `dynamic_top` is the strict scaling path.
- **Formatters:** `presentation/overview_metrics/` and `presentation/tui/pages/overview/presenter.py`
  are pure: they accept snapshot values and produce display strings; they never call providers
  or read files. `body()` is the current rendering helper; `finish()` is retained for a
  standalone status contract.
- **Dependency restriction:** presentation must not import `infrastructure/` or `bootstrap.py`.
- **Compatibility:** redaction must be applied to any new user-visible string; missing values
  render as `—`/`N/A`, never synthetic zeroes.

## 8. Infrastructure contracts

- `ProcessRunner.run(argv, *, timeout) -> ProcessResult`: argv only (no shell), per-stream
  output cap, bounded deadline, POSIX process-session isolation and process-group cleanup on
  timeout, allowlisted default child environment (`PATH`, `HOME`, `LANG`, `LC_*`).
- `SbellClient.call(module, command, params, token) -> SbellResponse`: validates identifier
  characters, rejects truncated/empty/invalid XML, parses `<status>`, `<description>`,
  `<errno>`, `<what>`, `<action_id>`.
- `ReadOnlyAuditAdapter.recent(limit)`: `1 <= limit <= 500`; opens `file:...?mode=ro`; requires
  columns `{time, user, user_ip, product, message}`; bounded `LIMIT`; never writes.
- Parsers are pure and fail closed: missing/malformed/conflicting values produce
  `CollectionStatus` markers and quality issues, not healthy defaults.
- **Compatibility:** no alternative transport (stdin, environment, descriptor, SSH) is invented.
  Credential argv exposure is a known, unresolved risk; enabling the flag acknowledges it but
  does not mitigate it.

## 9. Cross-cutting error contract

`AppError(kind, message, *, code=None, retryable=False)` carries `ErrorKind` (9 values in
`plaivid_cli/domain/models/enums.py`), a stable `code`, and safe display text. Rendering layers
print/redact it; the collection layer converts unclassified exceptions into per-section
`UNAVAILABLE` results. Do not leak raw argv, XML, tokens, or process `full_command` into logs or
UI (`tests/unit/test_redaction.py`, `docs/MONITORING_DASHBOARD.md`).

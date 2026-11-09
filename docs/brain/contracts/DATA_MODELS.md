# Data models and shared state

Each row names the **authoritative definition**. All model modules are frozen/slots dataclasses
or `StrEnum`s unless noted. Navigation: [`../README.md`](../README.md) ·
[`MODULE_CONTRACTS.md`](MODULE_CONTRACTS.md) · [`API_CONTRACTS.md`](API_CONTRACTS.md) ·
[`../architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md).

## Authoritative model definitions

| Model / group | Authoritative file | Notes |
|---|---|---|
| `SourceResult[T]`, `SectionSnapshot[T]`, `ApplicationSnapshot` | `plaivid_cli/domain/models/snapshots.py` | Generic frozen slots dataclasses; `ApplicationSnapshot.section(name)` lookup; `SectionSnapshot.has_value` property. |
| `CollectionStatus`, `Action`, `RiskLevel`, `OperationState`, `ErrorKind`, `canonical_uuid` | `plaivid_cli/domain/models/enums.py` | `StrEnum` values listed below. |
| `ObjectVM`, `ProcessObservation`, `VMRecord`, `InventoryData` | `plaivid_cli/domain/models/inventory.py` | Object-store state vs local process evidence are separate fields. |
| `HostStatus`, `NetworkInterface`, `StoragePartition`, `DiskInfo`, `NicInfo`, `ConsoleInfo`, `VMDetail`, `UserSession`, `TemperatureReading`, `ProcessSample`, `HostMetrics` | `plaivid_cli/domain/models/host.py` | Host telemetry and VM detail values. |
| `ActionPolicy`, `PvmReply`, `OperationPlan`, `TargetOutcome`, `OperationResult` | `plaivid_cli/domain/models/operations.py` | `OperationResult.succeeded_count` / `unknown_count` properties. |
| `PvmSession` | `plaivid_cli/domain/models/session.py` | `username`, `token`, optional `authenticated_at`. |
| `AuditEntry`, `AuditSummary` | `plaivid_cli/domain/models/audit.py` | Read-only audit rows. |
| `LocalHostSample`, `DashboardSample`, `PhysicalNic`, `NicSample` | `plaivid_cli/domain/overview.py` | **Missing measurements are `None`, never synthetic zeroes.** |
| `VirtualDesktop` | `plaivid_cli/domain/desktops.py` | `__post_init__` normalizes UUID and name; `memory_size_raw` has no verified unit; `parent_id` is not a verified owner. |
| `AppError` | `plaivid_cli/domain/errors.py` | `RuntimeError` subclass with `kind`, `code`, `retryable`. |
| `Settings`, `ConfigurationError` | `plaivid_cli/config.py` | Frozen slots dataclass of validated runtime settings. |
| `Series` | `plaivid_cli/presentation/charts/render.py` | Chart series value object (name, colour, points). |
| `Palette` | `plaivid_cli/presentation/theme.py` | Terminal palette selected by `palette_for`. |

`plaivid_cli/domain/models/__init__.py` is a **re-export facade** (32 names in `__all__`), not
an authoritative definition. Always edit the sibling module above.

## Enumerations (verbatim values)

| Enum | Values | Used by |
|---|---|---|
| `CollectionStatus` | `never_collected`, `current`, `partial`, `stale`, `unavailable`, `unsupported` | all `SectionSnapshot`s, JSON `status` |
| `Action` | `start`, `stop`, `kill`, `reset`, `pause`, `resume` | CLI parsers, plans, `_action_params` |
| `RiskLevel` | `moderate`, `high`, `critical` | `action_policy` |
| `OperationState` | `QUEUED`, `DISPATCHING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`, `PARTIAL`, `CANCELLED_BEFORE_DISPATCH`, `NOT_STARTED`, `COMMAND_ACCEPTED_UNCONFIRMED`, `OUTCOME_UNKNOWN` | `TargetOutcome`, `OperationResult`, exit codes |
| `ErrorKind` | `configuration`, `process`, `protocol`, `pvm_response`, `authentication`, `collection`, `policy`, `audit`, `internal` | `AppError` |

`canonical_uuid(value)` returns a lowercase hyphenated UUID string or raises `ValueError("invalid UUID")`.

## Snapshot / section state (most shared structure)

`SourceResult[T]`: `value`, `status`, `source`, `attempted_at`, `succeeded_at`, `error`,
`quality_issues`, `latency_seconds`, `attempted_monotonic`, `succeeded_monotonic`.

`SectionSnapshot[T]`: `name`, `value`, `last_good_value`, `status`, `attempted_at`,
`succeeded_at`, `generation`, `source`, `error`, `quality_issues`, `attempted_monotonic`,
`succeeded_monotonic`, `latency_seconds`; property `has_value`.

`ApplicationSnapshot`: `generation`, `created_at`, `sections: tuple[SectionSnapshot[object], ...]`;
method `section(name)`.

**Invariants (verified in `plaivid_cli/application/collection/publisher.py::publish_results`):**
- A successful read (`value is not None` and status `CURRENT`/`PARTIAL`) publishes the new value
  and refreshes `last_good_value`; a failed read keeps the prior last-good value and marks the
  section `STALE` unless the status is `NEVER`.
- Publication is suppressed when the mutation epoch changed, so a pre-mutation read cannot
  overwrite newer state.
- Freshness uses `succeeded_monotonic` (wall-clock UTC timestamps are metadata only). See
  `plaivid_cli/application/collection/freshness.py::section_is_fresh`.

## Inventory model

`InventoryData` holds `objects`, `process_rows`, `records: tuple[VMRecord, ...]`,
`unmatched_process_rows`, and `quality_issues`. `VMRecord` correlates an `ObjectVM` with an
optional `ProcessObservation` and exposes `process_seen` / `state_disagreed` / `host`. Correlation
is pure: `plaivid_cli/domain/inventory.py::merge_inventory` receives
`(objects, process_rows, process_available, process_complete, quality_issues)`.

`ObjectVM.host` is the node from `virtual_machine/cluster/host` (verbatim, blank normalised to
`None`), so placement is available on first paint without the on-demand detail read.
`ObjectVM.configured_port` is the object's console port; the live port comes from a matched
`ProcessObservation.port`. `resolve_console_port(record, detail)` in
`plaivid_cli/domain/models/inventory.py` resolves display precedence: live process port →
configured object port → detail console port → `None`. It never derives or guesses a port.

**Rule:** process-only rows never create defined VM objects; a partial process list is not
negative evidence of absence; disagreements stay visible and block mutation of that record
(`tests/unit/test_domain_models.py`, `tests/unit/test_application_operations.py`).

## Operation model

`OperationPlan(action, target_uuids, inventory_generation, inventory_succeeded_at, is_bulk,
freshness_limit_seconds, created_at)` is immutable and re-validated at dispatch.
`TargetOutcome(uuid, state, message, dispatched)`.
`OperationResult(operation_id, action, state, targets, started_at, finished_at, message)`.
`PvmReply(status, action_id, errno, message, returncode)`.

`COMMAND_ACCEPTED_UNCONFIRMED` is representable in `OperationState` but is **not produced** by
the current reply mapping; do not infer acceptance as completion.

## Configuration structure

`Settings` fields (from `plaivid_cli/config.py`), with defaults used by `load_settings({})`:

| Field | Default | Notes |
|---|---|---|
| `sbell_argv` | `("sudo", "sbell")` | `shlex.split` of `PLAIVID_SBELL` |
| `running_vms_argv` | `("pvm-running-vms",)` | `PLAIVID_RUNNING_VMS` |
| `process_timeout` | `30.0` | finite positive seconds |
| `max_output_bytes` | `1048576` | integer >= 1024, per stream |
| `refresh_interval` | `3.0` | finite positive seconds |
| `state_dir` | `$XDG_STATE_HOME/plaivid` or `~/.local/state/plaivid` | private directory |
| `session_file` | `<state_dir>/session.json` | derived, not separately configurable |
| `default_username` | `manage` | non-empty |
| `allow_credential_argv` | `False` | explicit risk acknowledgement |
| `max_inventory_age_seconds` | `None` | required for bulk admission |
| `audit_database` | `/var/log/pvm/messages.db` | optional, read-only |
| `log_level` | `WARNING` | one of DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `host_status_interval` | `2.0` | separate Overview host-status cadence |

Full validation rules: `docs/ENVIRONMENT.md`.

## Shared runtime state (not persisted)

| State | Owner | Shape |
|---|---|---|
| Read sections / generation / mutation barrier / pending intent | `CollectionCoordinator` | in-memory dicts + `Future`s |
| Operation lane / closing flag | `OperationCoordinator` | `threading.Lock`, `threading.Event` |
| `OverviewHistory` | `PlaividTui._history` | bounded deque (`limit=1024`) of `(monotonic_time, value)` per named series; 60-second visibility window |
| `OverviewSchedule` | `PlaividTui._overview_schedule` | interval, host-status interval, due clocks, busy flag |
| TUI view state | `PlaividTui.__init__` | `_selected_uuid`, `_vm_checked`, `_desktop_checked`, `_render_cache`, `_chart_tick_due`, `_cpu_scale`, `_load_scale`, `_nic_selected`, `_session_epoch`, `_visible_snapshot`, etc. |
| Cached token | `SessionStore` | JSON on disk (only persisted application state) |

`PlaividTui` state is cleared/epoch-guarded by `plaivid_cli/presentation/tui/session.py::SessionMixin`;
no application-owned telemetry or operation-history database exists.

## Serialization contracts

| Format | Producer | Consumer |
|---|---|---|
| CLI `--json` | `plaivid_cli/presentation/cli/serialization.py::_print_json` | automation; shape in [`API_CONTRACTS.md`](API_CONTRACTS.md) |
| `session.json` | `SessionStore.save` | `SessionStore.load` |
| `sbell` XML params | `plaivid_cli/infrastructure/pvm/adapter/requests.py` | `SbellClient.call` |
| `sbell` XML response | external `sbell` | `SbellClient.call`, pure parsers |
| `pvm-running-vms` text | external helper | `parse_process_rows` |
| SQLite `Log` rows | PVM-owned DB | `ReadOnlyAuditAdapter.recent` |
| Rich `Text` chart output | `render_chart` | `ChartView` |

All user-visible strings pass through `plaivid_cli/domain/redaction.py::redact_text`; secret
keys are replaced by `[REDACTED]` in JSON. Synthetic fixtures in `tests/fixtures/` are **not**
authoritative schemas for deployed PVM versions (`tests/fixtures/README.md`).

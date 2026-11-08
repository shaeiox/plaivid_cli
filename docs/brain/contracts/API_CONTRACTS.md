# API, protocol, and command contracts

All examples below are extracted from implementation files, tests, or synthetic fixtures.
There is **no HTTP API, RPC service, or network endpoint** in this repository. Navigation:
[`../README.md`](../README.md) · [`MODULE_CONTRACTS.md`](MODULE_CONTRACTS.md) ·
[`DATA_MODELS.md`](DATA_MODELS.md) · [`../codebase/ENTRYPOINTS.md`](../codebase/ENTRYPOINTS.md).

## 1. CLI command grammar

Source: `plaivid_cli/presentation/cli/parser.py::build_parser`; user reference: `README.md`,
`docs/REFERENCE.md`.

```text
plaivid [--version]                       # version from plaivid_cli/version.py
plaivid                                   # Textual dashboard (TTY only)
plaivid tui                               # same dashboard explicitly
plaivid inventory [--json]
plaivid host|status|overview [--json]
plaivid detail UUID [--json]
plaivid audit [--limit 1..500] [--json]   # default 20
plaivid config|diagnostics [--json]
plaivid logout
plaivid help
plaivid start|stop|kill|reset|pause|resume TARGET [TARGET...] [--json]
```

`Action` values come from `plaivid_cli/domain/models/enums.py::Action`. `host`, `status`,
`overview` are argparse aliases of one parser; `config`, `diagnostics` likewise. Target
selectors are resolved by `plaivid_cli/application/services.py::PlaividApplication`:

| Selector | Behavior |
|---|---|
| canonical UUID | Normalized by `canonical_uuid`; exact match |
| exact name / unique name prefix | Case-insensitive; ambiguous prefix rejected |
| 1-based index | Position in `_record_order` sort |
| `all` | All sorted records; cannot be combined with others |
| `state:<state>` | Object-store state; `state:running` matches `started` or `running` |
| `process:present` / `process:missing` | Local process observation |
| `tag:...` | Explicitly unsupported (`AppError` POLICY) |
| comma-separated | Split into an explicit set by `cli/operations.py::_operate`; duplicates rejected |

### Exit codes (`plaivid_cli/presentation/cli/operations.py`)

| Code | Constant | Meaning |
|---|---|---|
| 0 | `EXIT_OK` | Successful read or `SUCCEEDED` operation |
| 1 | `EXIT_FAILURE` | `FAILED` operation / general error |
| 2 | `EXIT_REJECTED` | `REJECTED`, `CANCELLED_BEFORE_DISPATCH`, policy/auth/config error, non-TTY TUI |
| 3 | `EXIT_PARTIAL` | `PARTIAL`, partial/stale read, non-current section |
| 4 | `EXIT_UNKNOWN` | `OUTCOME_UNKNOWN` or `COMMAND_ACCEPTED_UNCONFIRMED` |

`dispatch.py::run_command` maps `AppError` of `ErrorKind.POLICY|AUTHENTICATION` to 2, other
`AppError`s to 1, and `OSError|ValueError` to 2. `bootstrap.main` returns 2 for
`ConfigurationError`. Verified by `tests/unit/test_cli_and_tui.py`, `tests/unit/test_bootstrap.py`.

## 2. JSON output contracts

`--json` uses `plaivid_cli/presentation/cli/serialization.py::_print_json`: `json.dumps` with
`indent=2`, `ensure_ascii=False`, ISO-8601 for datetimes, dataclasses converted with `asdict`,
and recursive redaction. `_redact_json` replaces values under keys
`password`, `token`, `secret`, `authorization`, `session_token` with `[REDACTED]` and applies
`redact_text` to every string.

**`plaivid config --json`** (from `configuration_command`; asserted partially by
`tests/unit/test_bootstrap.py`):

```json
{
  "command": "config",
  "status": "validated",
  "data": {
    "sbell_executable": "sudo",
    "running_vms_executable": "pvm-running-vms",
    "process_timeout_seconds": 30.0,
    "max_output_bytes_per_stream": 1048576,
    "refresh_interval_seconds": 3.0,
    "state_directory": "/home/user/.local/state/plaivid",
    "session_file": "/home/user/.local/state/plaivid/session.json",
    "default_username": "manage",
    "credential_argv_acknowledged": false,
    "max_inventory_age_seconds": null,
    "audit_database": "/var/log/pvm/messages.db",
    "log_level": "WARNING"
  }
}
```

**Section payload** (`_section_payload(section, data)`), used by `inventory`, `host`, `detail`:

```json
{
  "status": "current",
  "generation": 7,
  "source": "user/objects+pvm-running-vms",
  "attempted_at": "2026-11-08T00:00:00+00:00",
  "succeeded_at": "2026-11-08T00:00:01+00:00",
  "error": null,
  "quality_issues": [],
  "data": { }
}
```

`status` is a `CollectionStatus` value (`never_collected`, `current`, `partial`, `stale`,
`unavailable`, `unsupported`); `"unavailable"` is used when the section is absent. For
`InventoryData`, `data` is expanded by `_json_data` into `objects`, `process_rows`, `records`
(each with `uuid`, `name`, `state`, `object`, `process`, `process_seen`, `state_disagreed`,
`quality_issues`), `unmatched_process_rows`, `quality_issues`.

**`plaivid host --json`** wraps two section payloads:
`{"command": "host", "sections": {"host_status": {...}, "host_metrics": {...}}}`.
**`plaivid audit --json`**: `{"command": "audit", "status": "current", "data": [...]}`.
**Lifecycle `--json`**: `{"command": "<action>", "operation": <OperationResult asdict>}`.
Human lifecycle output is `<uuid>  <STATE>  <message>` per target plus an aggregate line.

Illustrative values above (generation/timestamps) are shape placeholders, not captured data.
Regression evidence: `tests/unit/test_cli_and_tui.py::test_cli_json_preserves_partial_inventory_status_and_records`.

## 3. `sbell` argv protocol

Source: `plaivid_cli/infrastructure/pvm/sbell.py::SbellClient`,
`plaivid_cli/infrastructure/pvm/adapter/local.py::LocalPvmAdapter`,
`plaivid_cli/infrastructure/pvm/adapter/requests.py`; protocol reference `docs/SBELL-SABAD.md`.
Default executable argv `sudo sbell` (`PLAIVID_SBELL`), never a shell.

```text
<sbell argv...> <module> <command> <params-xml> [token]
```

Module and command must match `^[A-Za-z0-9_-]+$`; `params` must be non-empty XML text.

| Module | Command | Params | Purpose |
|---|---|---|---|
| `user` | `login` | `_login_params(username, password)` = `<params><username>…</username><password>…</password></params>` | Acquire token (gated) |
| `user` | `whoami` | `<params/>` | Validate cached session |
| `user` | `logout` | `<params/>` | Invalidate session |
| `user` | `objects` | `VM_QUERY`, `DESKTOP_QUERY`, `DASHBOARD_QUERY`, or detail query | Object/desktop/dashboard/detail reads |
| `sball` | `show` | `<params/>` | Sball host status |
| `monitoring` | `metrics` | `<params/>` | Host telemetry XML |
| `network` | `nic-list` | `<params/>` | Physical NIC discovery |
| `vm` | `<action>` (`start`/`stop`/`kill`/`reset`/`pause`/`resume`) | `_action_params(action, uuid)` | Lifecycle dispatch |

Example request constants (verbatim from `requests.py`):

```xml
<params><query>/objects/object/pvm_vmm_obj[type[text()='pvm_vmm_virtual_machine']]</query></params>
<params><query>/objects/object/*[type[text()="pvm_desktop_lite_virtual_desktop"]]</query></params>
```

For `Action.START`, `_action_params` emits `<vm_start><vm_key>…</vm_key><host>auto</host>…`;
all other actions use `_xml_text("vm_key", key)`. `ERRNO_HINT` maps errno strings `39`, `40`,
`108`, `137`, `146`, `185` to operator hints.

**Response envelope** parsed by `SbellClient.call` (shape visible in
`tests/fixtures/sball-show.xml`):

```xml
<response>
  <status>success</status>
  <action_id>…</action_id>
  <description>
    <errno>…</errno><what>…</what>
    …payload…
  </description>
</response>
```

`SbellResponse` exposes `status`, `action_id`, `errno`, `what`, `description`, `returncode`,
`ok`, `token`, and `reply() -> PvmReply`. Empty stdout, invalid XML, missing `<status>`,
missing `<description>` on reads, and truncated stdout raise `AppError` with
`ErrorKind.PROCESS`/`PROTOCOL`/`PVM_RESPONSE` codes. Lifecycle state mapping is documented in
[`MODULE_CONTRACTS.md`](MODULE_CONTRACTS.md); response **acceptance/completion semantics are
unverified** on real hosts (`docs/REAL_PVM_VALIDATION.md`).

## 4. `pvm-running-vms` text protocol

`LocalPvmAdapter.list_processes` runs `PLAIVID_RUNNING_VMS` (default `pvm-running-vms`) and
`parse_process_rows` parses numbered `ROW` lines. Synthetic example from
`tests/fixtures/running-vms-six.txt`:

```text
List of running virtual machines:

ROW     PID     UPTIME          PORT    VCPU    MEMORY  UUID                                    NAME

1       1001    14-15:45:15     5901    4       2048    11111111-1111-4111-8111-111111111111    vm-one
...
Total VCPU   : 22 (24)
Total Memory : 30 (31) GB
```

The Running-VMs card uses the **last numbered ROW** from a complete listing; malformed,
truncated, or non-zero-exit output is partial, not a zero count. Process observations are
separate evidence from object-store VM state. Evidence: `docs/MONITORING_DASHBOARD.md`,
`tests/unit/test_overview_monitoring.py`, `tests/unit/test_pvm_parsers.py`.

## 5. Read-only audit database contract

`plaivid_cli/infrastructure/audit.py::ReadOnlyAuditAdapter`:

- URI `file:<quoted absolute path>?mode=ro`, `sqlite3.connect(..., uri=True, timeout=5)`.
- Required `Log` table columns: `time`, `user`, `user_ip`, `product`, `message`.
- Query: `SELECT time, user, user_ip, product, message FROM Log WHERE user != 'none' AND message LIKE 'Command %has been %' ORDER BY rowid DESC LIMIT min(limit*3, 1500)`.
- Messages are matched with `_COMMAND = re.compile(r"Command '([^']+)' has been (.+?)\.?\s*$")`;
  `started` results are skipped; `limit` must be 1–500.
- Output `AuditEntry(time, user, user_ip, product, command, result, succeeded)`; `summarize`
  produces `AuditSummary(total, failures, top_commands, top_users, span)`.
- Never creates or modifies tables. Schema/unavailable errors raise `AppError(AUDIT)` with
  `AUDIT_OPEN_FAILED`, `AUDIT_SCHEMA_UNSUPPORTED`, or `AUDIT_QUERY_FAILED`.

Tests: `tests/unit/test_audit_adapter.py`.

## 6. Configuration / environment protocol

All settings are read from the process environment by `plaivid_cli/config.py::load_settings`;
no `.env` loader exists. Validation rules and the full variable list (including
`PLAIVID_HOST_STATUS_INTERVAL`, `PLAIVID_CHART`, `XDG_STATE_HOME`, setup-only
`PLAIVID_PYTHON`) are in `docs/ENVIRONMENT.md` — that document is authoritative and is not
duplicated here. Invalid values raise `ConfigurationError` before any PVM work.

Session cache serialization: `{"username": "...", "token": "..."}` written with
`json.dumps(..., separators=(",", ":"))` to `<state_dir>/session.json` (0600, directory 0700).

## 7. TUI event / binding contract

| Binding | Action | Handler surface |
|---|---|---|
| `space` | `toggle_check` | `VMSelectionMixin.action_toggle_check` |
| `a` | `toggle_all` | `VMSelectionMixin.action_toggle_all` |
| `r` | `refresh` | `RefreshMixin.action_refresh` |
| `enter` | `details` | `VMSelectionMixin.action_details` |
| `q` | `quit` | Textual built-in |
| `1` / `2` / `3` | `overview_page` / `vms_page` / `desktops_page` | `PlaividTui` |

Widget/message contracts: `CheckableTable.CheckRequested`, `DataTable.RowHighlighted`,
`Input.Changed`, `Checkbox.Changed`, `Select.Changed`, `Button.Pressed`,
`TabbedContent.TabActivated`. Tab ids: `overview`, `fleet`, `desktops`. Source:
`plaivid_cli/presentation/tui/app.py::PlaividTui`, `plaivid_cli/presentation/tui/layout.py::LayoutMixin`.

## 8. Collection section names (internal API)

`SUPPORTED_SECTIONS` in `plaivid_cli/application/collection/sections.py`:
`inventory`, `objects`, `processes`, `host_status`, `host_metrics`, `tap_mapping`,
`dashboard`, `desktops`, `local_host`, `physical_nics`, `nic_samples`, plus dynamic
`detail:<canonical-uuid>`. TUI demand lists in
`plaivid_cli/presentation/tui/refresh.py::RefreshMixin` must use these exact strings.

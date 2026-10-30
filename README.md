# Plaivid PVM CLI

A Linux-local command-line and Textual terminal interface for inspecting and operating Plaivid PVM virtual machines. It invokes the repository-evidenced local `sbell` and `pvm-running-vms` commands; it does not use SSH, a remote collector, or a guessed PVM API.

> **Real-host validation is pending.** No PVM host, production VM, Sball/PVM cluster, SSH endpoint, or production system was accessed for this implementation. Every owner-run host scenario is marked **PENDING MANUAL VALIDATION** in [`docs/REAL_PVM_VALIDATION.md`](docs/REAL_PVM_VALIDATION.md).

## Requirements and installation

- Linux host with the locally configured PVM `sbell` command and `pvm-running-vms` helper.
- Python **3.12 or newer**.
- Textual, installed from the package dependency metadata.
- The account must have the same local permissions needed by its configured `sbell` command; the default executable is `sudo sbell`.

Install in a virtual environment (do not replace or modify system Python):

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install .
plaivid --help
```

For development, install `.[dev]`. The project console command and `python -m plaivid_cli` use the same Bootstrap composition root. `./plaivid` is also provided for a checkout-based launch. To roll back, install the previously approved wheel into the same virtual environment. To remove the package, run `python -m pip uninstall plaivid-cli` from that environment; this does not alter system Python or remove the user session cache. Clear the cached token deliberately with `plaivid logout` (or follow the operator's approved local-cache removal process) before deleting application state.

### Rocky Linux user-local build and run

Use an already-approved Python 3.12+ interpreter; these commands do not install OS packages or modify system Python. Run the PVM-dependent command only on an authorized host and only after the credential and manual-validation gates below are accepted.

```bash
cd /path/to/plaivid_cli
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip build
.venv/bin/python -m pip install '.[dev]'
.venv/bin/python -m pytest -q --ignore=tests/smoke.py
.venv/bin/python -m ruff check .
.venv/bin/python -m pyright
.venv/bin/python -m build --wheel
.venv/bin/python -m pip install --force-reinstall dist/plaivid_cli-0.4.0-py3-none-any.whl
.venv/bin/plaivid --help
# On an authorized PVM host only, after the documented gates:
.venv/bin/plaivid inventory
```

The build/install command block is a deployment recipe, not a claim that Rocky Linux or Python 3.12 was available in the implementation workspace.

## Commands

```text
plaivid                         Open the Textual dashboard (TTY only)
plaivid inventory [--json]      List defined objects and separate process evidence
plaivid host|status|overview [--json]  Read host/Sball status and monitoring metrics
plaivid detail UUID [--json]    Read one VM's detailed configuration
plaivid audit [--limit N]       Read the local audit database in read-only mode
plaivid config|diagnostics [--json]  Show validated redacted settings; no PVM calls
plaivid logout                 Log out and clear the local token cache
plaivid start TARGET [--json]  Submit a start command
plaivid stop TARGET --approve 'STOP UUID'  Submit a confirmed stop
```

The remaining lifecycle commands are `kill`, `reset`, `pause`, and `resume`. Targets may be a canonical UUID, exact VM name, unique name prefix, displayed inventory index, `all`, `state:<state>`, or `process:present|missing`. Comma-separated selections are accepted, for example `plaivid stop UUID1,UUID2 --approve 'STOP UUID1,UUID2'`. `state:running` is derived from object-store state; process observations remain distinct evidence and are not silently substituted for object state.

For actions requiring approval, the CLI prints the exact expected phrase and does not dispatch without it. The phrase binds the action and canonical UUID sequence; on execution, the application also binds the approval internally to the just-collected inventory generation and freshness. The TUI presents a scrollable target list, inventory status/age, and configured freshness bound, and requires typing the exact phrase. Start/Resume of one explicitly selected VM do not show an extra confirmation; bulk operations require one. Kill always has a distinct critical confirmation.

Bulk operations are fail-closed until `PLAIVID_MAX_INVENTORY_AGE_SECONDS` is set to an approved finite positive value. Bulk inventory must be complete and current. The repository does not establish whether a positive `sbell` reply proves acceptance or completion; every returned response after dispatch is therefore reported as `OUTCOME_UNKNOWN`, stops bulk processing, and must not be blindly retried. The CLI exit categories are `0` successful read or verified operation, `1` failure, `2` rejected, `3` partial, and `4` outcome unknown (including any future acceptance without verified completion).

Use `--json` on supported inventory, host, detail, audit, and lifecycle commands for structured output. JSON preserves section status, source, generation, quality issues, and per-target results. Help and version do not launch PVM tools.

## Security and sessions

Passwords are never stored. A reusable session token may be cached in the configured state directory with user-only directory/file permissions and atomic replacement. Logout clears that local cache.

**Important unresolved risk:** the existing `sbell` interface passes credentials and tokens in process arguments. This project has not verified a safer credential transport and does not invent one. Login and token-bearing calls are denied by default until the operator explicitly sets:

```bash
PLAIVID_ALLOW_CREDENTIAL_ARGV=1
```

Set this only after reviewing the local process-inspection risk and accepting it for the environment. The program warns when enabled; it does not claim argv secrets are protected. No automatic session eviction or session-cap recovery is performed.

Audit access is optional and read-only. The adapter opens SQLite with `mode=ro`, limits row counts, and rejects unsupported schemas. Plaivid does not create an application-owned telemetry or operation-history database.

## Configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `PLAIVID_SBELL` | `sudo sbell` | Local `sbell` argv; parsed as arguments, never a shell command. |
| `PLAIVID_RUNNING_VMS` | `pvm-running-vms` | Local process-evidence helper argv. |
| `PLAIVID_USER` | `manage` | Default interactive username. |
| `PLAIVID_STATE_DIR` | `$XDG_STATE_HOME/plaivid` or `~/.local/state/plaivid` | Private local token cache directory. |
| `PLAIVID_CMD_TIMEOUT` | `30` | Positive per-child deadline in seconds. |
| `PLAIVID_MAX_OUTPUT_BYTES` | `1048576` | Retained output cap per stream. |
| `PLAIVID_REFRESH` | `3` | Positive TUI refresh cadence in seconds. |
| `PLAIVID_MAX_INVENTORY_AGE_SECONDS` | unset | Required positive age bound for bulk mutation admission. |
| `PLAIVID_ALLOW_CREDENTIAL_ARGV` | disabled | Explicit acknowledgement of unresolved password/token argv exposure. |
| `PLAIVID_LOG_DB` | `/var/log/pvm/messages.db` | Optional existing audit database, opened read-only. |
| `PLAIVID_LOG_LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |

## Architecture

```text
CLI / Textual UI
       │
       ▼
Bootstrap ── SessionManager / OperationCoordinator
       │                    │
       └── PlaividApplication ── CollectionCoordinator (one serialized read lane)
                                      │
                                      ▼
                         LocalPvmAdapter / ReadOnlyAuditAdapter
                                      │
                     bounded argv ProcessRunner + pure parsers
                                      │
                       local sbell / pvm-running-vms only
```

- `domain/` contains immutable records, source/result statuses, errors, and pure policy.
- `application/` contains read use cases, session management, the serialized collection lane, and lifecycle orchestration.
- `infrastructure/` contains bounded child execution, the PVM adapter/parsers, redaction, and read-only audit access.
- `tui.py` uses Textual for rendering; blocking local work runs in workers and visible read requests go through the single collection coordinator.
- Operations use generation/freshness gates, explicit approval, sequential target order, no blind retry, and post-operation reconciliation. Acceptance is never presented as completion.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the current module boundaries and [`docs/REFERENCE.md`](docs/REFERENCE.md) for the command cheat sheet. PVM response contracts that remain uncertain are isolated and listed in the manual validation plan; no undocumented command or state transition is inferred.

## Local verification

Unit and fake-backed tests do not require PVM executables and do not contact any host. Use:

```bash
python -m pytest tests/unit -q
ruff check plaivid_cli tests/unit
```

A local test pass is not PVM contract verification. The owner must complete the separate manual checks before relying on the CLI against a real host.

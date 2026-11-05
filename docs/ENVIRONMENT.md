# Environment configuration

This is the environment-variable reference for the **current** `plaivid` CLI and Textual dashboard. Runtime settings are parsed by `plaivid_cli/config.py` at startup; `./scripts/setup.sh` has one additional setup-only setting. The checkout also contains retired modules and an opt-in real-host smoke script—those variables are listed separately below and are **not** part of the installed application.

Environment variables are inherited from the shell. The project does **not** automatically load a `.env` file. Configure them in the process environment (or a service manager's protected environment configuration) before launching `plaivid`. The ignored `.env` filename is not a loader or a safe place to store credentials.

## Current application settings

| Variable | Default | Validation and effect |
| --- | --- | --- |
| `PLAIVID_SBELL` | `sudo sbell` | Executable plus arguments for the local Sball command. Parsed with `shlex.split`; must be nonempty with valid quoting. It is **not** run through a shell, so pipes, `~`, `$VAR`, and shell operators are not expanded. Prefer absolute executable paths when command lookup is uncertain. |
| `PLAIVID_RUNNING_VMS` | `pvm-running-vms` | Executable plus arguments for local VM-process evidence; same argv parsing and validation as `PLAIVID_SBELL`. This is not an inventory of configured VMs. |
| `PLAIVID_USER` | `manage` | Default username for the interactive login prompt/TUI. Leading and trailing whitespace is removed; an empty result is rejected. This is **not** a password or a service account login by itself. |
| `PLAIVID_STATE_DIR` | `$XDG_STATE_HOME/plaivid`, or `~/.local/state/plaivid` if `XDG_STATE_HOME` is unset | Local state directory containing `session.json` (a cached **token**). `~` is expanded; there is no separate session-file variable. Use a private directory and do not commit or casually copy its contents. |
| `PLAIVID_CMD_TIMEOUT` | `30` | Finite, positive number of seconds for a bounded child-command deadline. A nonnumeric, zero, negative, `nan`, or infinite value fails configuration validation. |
| `PLAIVID_MAX_OUTPUT_BYTES` | `1048576` (1 MiB) | Maximum retained **per stdout/stderr stream** for a child command; integer at least `1024`. Exceeding the cap may leave a response truncated and unusable; it does not permit unbounded capture. |
| `PLAIVID_REFRESH` | `3` | Finite, positive default cadence in seconds. The Overview's local/NIC schedule starts with this value **clamped to 1–60 seconds**; its Apply field accepts whole seconds 1–60. Expensive Overview PVM reads run no faster than 18 seconds; the VM-page refresh and the default single-target freshness rule also use the configured interval. Changing the Overview field at runtime does not change the process-level setting or mutation policy. |
| `PLAIVID_HOST_STATUS_INTERVAL` | `2` | Finite, positive cadence in seconds for the Overview Host status read (`sball show`). It runs on its own schedule, separate from the 18-second PVM batch, so quorum changes show quickly. |
| `PLAIVID_CHART` | Unset | `braille` or `blocks` to force the Overview graph style. Unset uses Braille on UTF-8 terminals and block characters otherwise. |
| `PLAIVID_MAX_INVENTORY_AGE_SECONDS` | Unset (`None`) | Finite, positive age limit in seconds for operation-admission checks. Unset or blank **disables bulk VM mutations**; setting it does not waive current/complete inventory or other safety checks. With no configured limit, single-target operations instead use `2 × PLAIVID_REFRESH` as their default freshness limit. Agree an appropriate limit with the PVM owner; this is not a request to make stale data acceptable. |
| `PLAIVID_ALLOW_CREDENTIAL_ARGV` | Disabled | Explicit **risk acknowledgement**, not credential protection. Only `1`, `true`, `yes`, or `on` (case-insensitive, surrounding whitespace ignored) enables it; other values leave it disabled. The existing Sball interface passes credentials/tokens in process arguments. Review local process-visibility risks before enabling authenticated calls; the application warns when enabled. |
| `PLAIVID_LOG_DB` | `/var/log/pvm/messages.db` | Path of an existing optional audit SQLite database. The current adapter opens it **read-only**; audit reads may fail if it is missing, inaccessible, or has an unsupported schema. This variable does not configure application telemetry storage. |
| `PLAIVID_LOG_LEVEL` | `WARNING` | Logging threshold: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Case is normalized to uppercase; other values are rejected. It is not an audit-retention or redaction switch. |

All values are read when the process starts, except the Overview refresh interval you can adjust in the running TUI. Invalid runtime settings fail with a configuration error (exit code 2) **before** PVM work. `plaivid --help` and `plaivid --version` do not require loading settings; `plaivid config` / `plaivid diagnostics` validates and displays a redacted summary without contacting PVM:

```bash
plaivid config
plaivid config --json
```

The summary shows executable names, paths, username, and non-secret values, but omits additional command arguments and credentials. Treat those paths/usernames as potentially sensitive when sharing diagnostic output. Set `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` only after a separate operator/security decision, not as a general setup default.

### State-directory and child-process behavior

- `XDG_STATE_HOME` is a standard environment variable that changes the default `PLAIVID_STATE_DIR`. When neither is set, the fallback is `~/.local/state/plaivid`. An explicit `PLAIVID_STATE_DIR` takes precedence; the session file is always `session.json` inside that directory. An empty `XDG_STATE_HOME` is not treated specially by the parser—avoid setting it to an empty or relative path.
- `PATH` is used for executable lookup if an argv setting begins with an unqualified command such as `sudo`. The child environment is intentionally restricted to `PATH`, `HOME`, `LANG`, and `LC_*`; other ambient environment variables (including `PLAIVID_*` and possible secrets) are **not** forwarded to Sball or `pvm-running-vms` by the current process runner. This filtering does **not** mitigate credentials exposed in argv. `HOME` also affects the usual home-directory resolution of defaults; locale settings can affect child output.
- These are local commands, not SSH endpoints. No hostname, remote-agent, container, or credential-in-environment setting is supported by the current runtime. Do not put passwords or tokens into `PLAIVID_SBELL` arguments.

## Setup script only

| Variable | Default | Effect |
| --- | --- | --- |
| `PLAIVID_PYTHON` | Auto-detect an available Python 3.12+ interpreter | Used only by `./scripts/setup.sh`. Provide an executable path or command on `PATH` if auto-detection is unsuitable, for example `PLAIVID_PYTHON=/opt/python/bin/python3.12 ./scripts/setup.sh`. The script verifies its version and creates/reuses the project `.venv`. It does not change the runtime interpreter selection after installation. |

## Terminal presentation (external Textual/Rich conventions)

These are **not** `load_settings()` options. They affect the terminal renderer or the legacy checkout-only styling, and do not change monitoring data:

| Variable | Behavior |
| --- | --- |
| `TERM` | Terminal capability hint. For example, `xterm-256color` advertises **256 colors**, not necessarily truecolor. An inadequate value may cause a 16-color/monochrome fallback. |
| `COLORTERM` | `truecolor` or `24bit` can signal RGB support on non-Windows terminals. Only advertise this when the actual terminal supports it. |
| `TEXTUAL_COLOR_SYSTEM` | Textual's optional color-system override (normally `auto`); `256`, `standard`, or `truecolor` may be used for diagnosis. Do **not** force `truecolor` on an unsupported terminal. Plaivid chooses its canvas/palette according to Textual's detected output system. |
| `NO_COLOR` | **Presence** disables color, even if set to an empty string. Unset it to restore color. The dashboard also selects its high-contrast fallback when it is present. |

A shell such as PowerShell is not itself a guarantee of color depth; the terminal emulator and any remote session determine rendering. See [the monitoring dashboard guide](MONITORING_DASHBOARD.md#visual-system) for the color-depth behavior.

## Checkout-only legacy code and opt-in smoke test

These settings are mentioned so existing repository references are not mistaken for supported installed configuration. `setup.py` excludes the retired `plaivid_cli/legacy/` package from distribution artifacts; do not use it as the current production entry point.

| Variable | Where it appears | Important distinction |
| --- | --- | --- |
| `PLAIVID_ASCII` | Retired `plaivid_cli/legacy/theme.py` | Presence switches old glyphs to ASCII; **does not** control the current Textual dashboard. That legacy theme also observes `NO_COLOR`. |
| `PLAIVID_PASS` | `tests/smoke.py` only | Password for an opt-in legacy real-host smoke test; **not** read by the current CLI login. The smoke test invokes legacy modules against a real PVM host and should not be run without authorization. Avoid storing passwords in a repository file, shell history, or process-visible environment. |
| `PLAIVID_REFRESH`, `PLAIVID_USER`, `PLAIVID_LOG_DB` | Retired modules / smoke test as well as current runtime | The current definitions are in the main table above. The legacy overview reads refresh independently, and the retired log module reads the audit path at import time; these are not additional runtime settings. |

`PLAIVID_TEST_SECRET` appears in a process-runner **unit-test fixture** solely to verify that ambient secrets are omitted from child environments. It is not a project configuration variable.

## Example: inspect safe defaults

```bash
# These are non-secret examples; adapt paths and limits for your site.
export PLAIVID_STATE_DIR="$HOME/.local/state/plaivid"
export PLAIVID_SBELL='sudo sbell'
export PLAIVID_REFRESH=3
plaivid config
```

This only displays configuration. It does not log in, enable credential argv exposure, run a mutation, or validate a real PVM host. For security and real-host acceptance, also read [the README](../README.md#security-and-sessions) and [the manual validation plan](REAL_PVM_VALIDATION.md).

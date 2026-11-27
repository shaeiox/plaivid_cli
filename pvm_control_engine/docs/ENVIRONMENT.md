# Engine environment configuration

These settings are owned and read by `pvm-control-engine`, not by `plaivid-ui`. Values are loaded at Engine startup; no `.env` file is loaded automatically. Do not put passwords or PVM session tokens in environment variables.

| Variable | Default | Purpose and validation |
|---|---|---|
| `PLAIVID_SBELL` | `sudo sbell` | Executable and fixed base argv for the approved local sbell integration; shell-split once and always launched without a shell. |
| `PLAIVID_RUNNING_VMS` | `pvm-running-vms` | Local process-evidence helper argv, also shell-split without a shell. |
| `PLAIVID_USER` | `manage` | Default username for Engine-owned interactive `login`. |
| `PLAIVID_STATE_DIR` | `$XDG_STATE_HOME/plaivid`, else `~/.local/state/plaivid` | Engine session-cache and state directory. Session cache is owner-private and contains the Engine token. |
| `PLAIVID_CONTROL_SOCKET` | `$XDG_RUNTIME_DIR/pvm-control-engine.sock`, else `${PLAIVID_STATE_DIR}/pvm-control-engine.sock` | AF_UNIX socket path used by `serve`. The UI can override its client path with the same variable. |
| `PLAIVID_CMD_TIMEOUT` | `30` seconds | Finite positive bound for ordinary child processes. |
| `PLAIVID_ACTION_TIMEOUT` | `10` seconds | Finite positive per-target lifecycle trigger bound. |
| `PLAIVID_MAX_OUTPUT_BYTES` | `1048576` | Maximum retained bytes per child stdout/stderr stream; minimum 1024. |
| `PLAIVID_REFRESH` | `3` seconds | Collection refresh interval and default single-target freshness basis. |
| `PLAIVID_HOST_STATUS_INTERVAL` | `2` seconds | Independent local host-status collection cadence. |
| `PLAIVID_MAX_CONCURRENCY` | `3` | Positive bound for concurrent targets within one lifecycle bulk operation. |
| `PLAIVID_MAX_INVENTORY_AGE_SECONDS` | unset | Positive max inventory age for bulk action admission. Unset disables bulk VM mutation; it does not disable single-target policy. |
| `PLAIVID_ALLOW_CREDENTIAL_ARGV` | disabled | Explicit risk acknowledgement for the existing sbell credential/token-in-argv transport. Accepted truth values: `1`, `true`, `yes`, `on` (case-insensitive). Default-deny; this does not mitigate process-list exposure. |
| `PLAIVID_LOG_DB` | `/var/log/pvm/messages.db` | Optional audit SQLite database, opened read-only by the Engine. |
| `PLAIVID_LOG_LEVEL` | `WARNING` | Engine logging threshold: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

`pvm-control-engine login` prompts on an interactive terminal with echo disabled and persists session state only in the Engine-owned store. The Engine never offers a password-bearing JSON-RPC method. The UI does not read this environment configuration except socket-path selection and does not read Engine session files.

Use `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` only after the operator accepts the existing local process-argument exposure risk. It is not a security improvement or a transport substitution. See [architecture](ARCHITECTURE.md), [IPC contract](../../UI/docs/IPC.md), and [owner-run validation plan](REAL_PVM_VALIDATION.md).

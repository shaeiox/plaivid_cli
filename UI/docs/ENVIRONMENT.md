# UI environment and terminal settings

The UI has no PVM, session-store, sbell, or process-runner settings. It inherits the shell environment and does not load `.env` files.

| Variable | Default | Effect |
|---|---|---|
| `PLAIVID_CONTROL_SOCKET` | Engine's default socket path | Explicit local AF_UNIX Engine socket path. Set this when the Engine listens at a non-default path. |
| `XDG_RUNTIME_DIR` | unset | When `PLAIVID_CONTROL_SOCKET` is unset, client uses `$XDG_RUNTIME_DIR/pvm-control-engine.sock`. |
| `PLAIVID_STATE_DIR` | `~/.local/state/plaivid` | Final socket fallback: `${PLAIVID_STATE_DIR}/pvm-control-engine.sock`; configure consistently with the Engine state directory if no runtime directory is set. It is not read for or used to load the Engine session token. |
| `PLAIVID_CHART` | auto | Optional graph style override (`braille` or `blocks`). |
| `NO_COLOR` | unset | Presence selects the UI high-contrast/no-color palette. |
| `TERM`, `COLORTERM`, `TEXTUAL_COLOR_SYSTEM` | terminal-dependent | Hints/detection used by Textual/Rich to select supported color capability. Avoid forcing truecolor on an incompatible terminal. |

The UI socket client uses a bounded request timeout and validates JSON-RPC response framing/IDs. It does not send credentials, passwords, PVM tokens, arbitrary command names, raw XML, or argv. Authenticate locally with `pvm-control-engine login`; see [`IPC.md`](IPC.md).

For local UI development dependencies and the project setup script, run `./scripts/setup.sh` from this project directory. It creates/uses only `UI/.venv` and installs `plaivid-ui` from this directory.

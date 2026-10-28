# Plaivid CLI

A modular terminal client for controlling PVM / Plaivid virtual machines from
the command line, driven by `sbell` on the PVM host.

Styled after the gemini-cli TUI design system (256-color, rounded borders),
with graceful fallback to plain text when piped or when `NO_COLOR` is set.

## What it does

- **Session**: logs in on first use (prompts for user/password), caches the
  token so reopening the TUI does not re-prompt, and auto-recovers from the
  "too many sessions" cap by evicting an old session (like the web UI).
- **Host monitoring**: live CPU / RAM / disk / load for the PVM node.
- **VM inventory**: every defined VM with state, vCPU and memory; running VMs
  are enriched with PID / uptime / console port from `pvm-running-vms`, and
  shown first.
- **VM actions**: `start`, `stop`, `kill`, `reset`, `pause`, `resume` — each
  targetable by **index number or name** (exact, UUID, or unique prefix).

## Requirements

- Runs **on the PVM host** (it shells out to `sbell` and `pvm-running-vms`).
- **Python 3.6+**, standard library only — no pip installs.
- `sbell` needs root, so the tool calls it via `sudo` by default (the invoking
  user needs sudo rights to `sbell`).

## Usage

```bash
./plaivid                 # interactive TUI
./plaivid list            # one-shot: print the dashboard
./plaivid status          # one-shot: refresh + dashboard
./plaivid overview        # live monitoring (CPU, load, mem, network, storage)
./plaivid show Hadi-New    # one-shot: detailed view of one VM
./plaivid health          # one-shot: health & capacity summary
./plaivid log 30          # one-shot: last 30 audit actions
./plaivid stop Hadi-New    # one-shot: run an action by name
./plaivid stop state:off   # one-shot: bulk action by state
./plaivid start 12         # ... or by the index shown in the list
```

Inside the TUI:

| Command | Does |
| --- | --- |
| `list` / `ls` / `refresh` | reload VMs + host status |
| `overview` / `mon` | live monitoring page (auto-refresh; `q` / Ctrl-C to exit) |
| `health` / `hc` | health & capacity summary (quorum, storage, overcommit, license) |
| `show` / `detail` `<id\|name>` | detailed view of one VM (disks, NICs, console) |
| `log` `[N]` | audit log viewer + analyzer (recent actions, who did what) |
| `sort` `[field] [asc\|desc]` | sort the VM list by `name`, `state`, `cpu`, `mem`, `uptime`, `pid`, `port` (SPICE), `uuid`; `sort reset` restores the default |
| `status` | refresh and show host monitoring |
| `<action> <targets>` | run an action on one or many VMs (see below) |
| `help` / `?` | list commands and actions |
| `logout` | clear the saved session and exit |
| `quit` / `q` | exit (keeps the session cached) |

**Targets** for actions can be a single VM *or many at once*:

```
stop 3                 # by index
stop Hadi-New           # by name (or unique prefix)
stop 3,5,Hadi-New       # a comma-separated list
stop state:running      # every VM in a state (running/stopped/off/paused)
start off               # shorthand: all VMs in that state
kill all                # every VM
```

Destructive actions (`stop`, `kill`, `reset`) ask for one confirmation,
showing the full list of affected VMs for a bulk action.

## Configuration (environment variables)

| Var | Default | Purpose |
| --- | --- | --- |
| `PLAIVID_SBELL` | `sudo sbell` | how to invoke sbell (set to `sbell` if already root) |
| `PLAIVID_RUNNING_VMS` | `pvm-running-vms` | the running-VM lister |
| `PLAIVID_USER` | `manage` | default username at the login prompt |
| `PLAIVID_STATE_DIR` | `~/.local/state/plaivid` | where the session token is cached |
| `PLAIVID_CMD_TIMEOUT` | `30` | per-command timeout (seconds) |
| `PLAIVID_ASCII` | unset | force ASCII glyphs/borders |
| `NO_COLOR` | unset | disable color |

## Architecture

One **orchestrator** wires together small, independent modules. A failure in
any one of them is caught and reported — it never brings down the app.

```
plaivid                      entry point (interactive or one-shot)
plaivid_cli/
  orchestrator.py            the controller: session, refresh, screen, dispatch
  transport.py               the ONLY module that shells out + parses XML
  session.py                 login / logout / token cache / session recovery
  vms.py                     inventory (merge object-store + pvm-running-vms), resolve
  monitoring.py              host status
  render.py                  all presentation (banner, panels, tables, boxes)
  theme.py                   palette, glyphs, borders
  config.py                  paths + env overrides
  actions/                   ONE FILE PER ACTION (isolated + hot-swappable)
    __init__.py              registry: imports each action independently
    base.py                  shared helpers + the action contract
    start.py stop.py kill.py reset.py pause.py resume.py
tests/
  smoke.py                   non-interactive data-layer check (run on the host)
```

### Adding a new action

Drop a new file in `plaivid_cli/actions/`, e.g. `migrate.py`:

```python
from .base import simple_vm_action, vm_key

NAME = "migrate"
LABEL = "Migrate"
DESCRIPTION = "Live-migrate to another host."
APPLIES_TO = {"started", "running"}
DESTRUCTIVE = True
ORDER = 70

def run(ctx, vm):
    return simple_vm_action(ctx.token, "migrate", vm_key(vm))
```

It is discovered automatically. If it has a bug, the registry records the error
and disables just that action — everything else keeps working.

## Deploy

```bash
scp -r plaivid-cli youruser@pvmhost:~/     # copy to the host
ssh youruser@pvmhost
cd plaivid-cli && ./plaivid
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - how the app is built: design
  goals, every module's responsibility, runtime flow, the action plugin system,
  and how to extend it.
- [`docs/SBELL-SABAD.md`](docs/SBELL-SABAD.md) - the PVM control protocol in
  depth: sbell/sabad requests, per-command params, authentication and session
  handling, the object/query model, the HTTP API, and the raw wire framing.
  Written so a future developer or AI can send any request correctly.
- [`docs/REFERENCE.md`](docs/REFERENCE.md) - quick command cheat-sheet.

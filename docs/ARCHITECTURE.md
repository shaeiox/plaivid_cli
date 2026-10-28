# Plaivid CLI - Architecture & Internals

This document explains how the Plaivid CLI is built: its design goals, the
responsibility of every module, the runtime flow, and how to extend it. It is
written for future contributors (human or AI) who need to modify or grow the
application. For the underlying PVM control protocol, see
[`SBELL-SABAD.md`](SBELL-SABAD.md); for a quick command cheat-sheet, see
[`REFERENCE.md`](REFERENCE.md).

---

## 1. What this application is

A terminal UI (TUI) and one-shot CLI for operating PVM / Plaivid virtual
machines. It **runs on the PVM host** and shells out to the host's own
`sbell` and `pvm-running-vms` commands - it is a thin, well-structured client
over the same `sballd` core daemon that the Plaivid web UI drives.

It does **not** reimplement the PVM protocol in a library; it composes existing
host tools. That keeps it small, dependency-free, and always consistent with
whatever the host's `sbell` version supports.

```
                        the PVM host (e.g. sponge / spongebob)
  +-------------------------------------------------------------------------+
  |                                                                         |
  |   plaivid  (this app, Python 3.6+, stdlib only)                         |
  |      |  subprocess: `sudo sbell ...`      subprocess: `pvm-running-vms`  |
  |      v                                           v                      |
  |   sbell  --UNIX socket (root)-->  sballd :7090  <-- reads running VMs   |
  |                                      |                                  |
  |                                      v                                  |
  |                                   qemu VMs (.pvmon QMP sockets)         |
  +-------------------------------------------------------------------------+
```

## 2. Design goals

1. **Modularity with blast-radius isolation.** One orchestrator wires together
   small modules. Every risky operation (each VM action, each data fetch, the
   whole input loop) is wrapped so a failure is caught, reported, and survived -
   a single broken component never takes down the app. VM actions in particular
   are *independent files* loaded by a registry that records and skips any that
   fail to import.
2. **Zero dependencies.** Standard library only, Python 3.6+ (the host ships
   3.6.8). No pip, no venv - copy the folder and run.
3. **Graceful degradation.** Full color + rounded borders on a TTY; clean plain
   text when piped or when `NO_COLOR` / `PLAIVID_ASCII` is set. Missing data
   (e.g. host monitoring unreachable) degrades to a message, not a crash.
4. **The transport is the only thing that touches the outside world.** All
   subprocess calls and XML parsing live in `transport.py`; everything else
   works with typed objects. This makes it possible to add a new backend (SSH,
   the sabad HTTP API, a native socket client) without changing any caller.

## 3. Module reference

All modules live under `plaivid_cli/`.

| Module | Responsibility | Key API |
| --- | --- | --- |
| `config.py` | All tunables and paths, overridable by env vars. No logic. | `SBELL_CMD`, `RUNNING_VMS_CMD`, `SESSION_FILE`, `CMD_TIMEOUT`, `DEFAULT_USER` |
| `transport.py` | The **only** module that runs subprocesses and parses the `<response>` XML envelope. | `sbell(module, command, params, token)` -> `Response`; `running_vms_raw()`; `TransportError` |
| `session.py` | Login, logout, token cache (load/save/validate), and the "too many sessions" (errno 185) recovery. | `resume_or_prompt(prompt_fn)`, `login()`, `logout()`, `Session` |
| `vms.py` | The VM data model and inventory: merge the object store with `pvm-running-vms`, order it, and resolve a user selector. | `VM`, `inventory(token)`, `list_running()`, `resolve(vms, selector)` |
| `monitoring.py` | Host/cluster status (CPU, RAM, disk, load) from `sball show`. | `host_status(token)` -> dict |
| `theme.py` | Palette (gemini-cli 256-color), glyphs, rounded box parts, state styling, TTY/NO_COLOR detection. | `primary/accent/...`, `glyph()`, `BOX`, `state_style()` |
| `render.py` | Pure presentation: banner, host panel, VM table, framed boxes, messages. Knows nothing about transport or state. | `banner()`, `host_panel()`, `vm_table()`, `frame()`, `width()`, `center()` |
| `actions/` | One file per **VM action** (`run(ctx, vm)`), discovered by a registry with per-file error isolation. | `load()`, `get(name)`, `all_actions()`, `load_errors` |
| `commands/` | One file per **TUI verb** (`run(ctx, args)`: overview, health, show, log, list, …), discovered the same way. A `CommandContext` facade gives each command a stable view of the app. | `load()`, `get(name)`, `all_commands()`, `CommandContext`, `CONTINUE/EXIT` |
| `orchestrator.py` | The controller. Owns the session, data refresh, screen and input (readline + Tab completion). Dispatch is registry-first (commands, then actions); help and completion are derived from both registries, so adding a file is all it takes to add behavior. | `App`, `main(argv)` |

Dependency direction (arrows = "imports"):

```
orchestrator ─> actions ─> transport
      │           └──────> (base helpers)
      ├─> session ─> transport
      ├─> vms ─────> transport
      ├─> monitoring ─> transport
      ├─> render ──> theme
      └─> config, theme
```

`transport` depends on nothing but `config`. `render` depends only on `theme`.
There are no cycles.

## 4. Runtime flow

### Interactive (`./plaivid`)

```
main(argv=[])
  App.run_interactive()
    ensure_session()          # resume cached token, else prompt + login
    _setup_readline()         # Tab completion + candidate listing
    loop:
      refresh()               # host_status() + vms.inventory()  (first iter + after actions)
      draw()                  # clear screen; center+print banner, host panel, VM table, status, hint
      line = input(prompt)    # readline-edited, Tab-completed
      dispatch(line)          # builtin? action? -> run, set status, refresh
```

### One-shot (`./plaivid <cmd> ...`)

```
main(argv=["stop","Hadi-New"])
  App.run_once(argv)
    ensure_session(); refresh()
    if cmd in {list,status}: draw()        # print the dashboard and exit
    else: dispatch(line); print(status)    # run one action, print the result line
```

One-shot mode shares the exact same `dispatch()` path as the TUI, so behaviour
is identical and scripting is first-class.

## 5. The action plugin system

This is the core of the "if one fails the app doesn't fall apart" requirement.

**Contract** (see `actions/base.py`) - each action file defines:

```python
NAME        = "stop"              # command the user types
ALIASES     = ["shutdown"]        # optional alternative names
LABEL       = "Stop"              # menu title
DESCRIPTION = "Graceful ACPI shutdown of a running VM."
APPLIES_TO  = {"started", "running"}   # states where it is offered (empty = always)
DESTRUCTIVE = True                # ask for confirmation first
ORDER       = 20                  # sort order in menus
def run(ctx, vm): ...             # returns base.ActionResult(ok, message)
```

**Registry** (`actions/__init__.py`):

- On first use it scans the package with `pkgutil.iter_modules`, imports each
  candidate file **individually inside a try/except**, and validates it has the
  required attributes.
- A file that raises (syntax error, bad import, missing attribute) is recorded
  in `actions.load_errors` and skipped - every other action and the whole app
  keep working. The `help` screen lists any disabled actions and why.
- Successful modules are wrapped in `_Action`, keyed by name and every alias,
  and sorted by `ORDER`.

**Execution** - the orchestrator calls `action.run(ctx, vm)` inside *another*
try/except, so even a runtime bug in an action only produces an error message.

**`ctx`** is a tiny `Context` object exposing `ctx.token`; actions never touch
the session or transport internals directly - they call `base.simple_vm_action`.

**Adding an action** = drop a new file in `actions/`. Example `migrate.py`:

```python
from .base import simple_vm_action, vm_key
NAME, LABEL = "migrate", "Migrate"
DESCRIPTION = "Live-migrate to another host."
APPLIES_TO, DESTRUCTIVE, ORDER = {"started", "running"}, True, 70
def run(ctx, vm):
    return simple_vm_action(ctx.token, "migrate", vm_key(vm))
```

No registration, no edits elsewhere. If `migrate` needs richer params (like
`start` does), build the XML in `run()` - see `actions/start.py`.

## 6. Session & authentication lifecycle

Handled entirely by `session.py`; see [`SBELL-SABAD.md`](SBELL-SABAD.md) for the
wire details.

```
resume_or_prompt(prompt_fn)
  _load()                 # read ~/.local/state/plaivid/session.json
  _is_valid(cached)       # cheap server check: `sbell user whoami <token>`
  valid?  -> return (session, newly_logged_in=False)
  invalid -> prompt_fn()  # collect user/password (UI owns how)
             login(user, pw)
```

`login()`:
1. `sbell user login "<params>...</params>"`.
2. If it fails with **errno 185** (session cap reached), call
   `user/list-current-user-sessions` (username+password, no token) to list
   session UUIDs, then retry login with a `<session_delete_uuid>` to evict one -
   exactly what the web UI does.
3. On success, cache `{username, token}` to a `0600` file so the next launch
   does not re-prompt (requirement 1).

The token is a JWT; `Session.claims()` decodes its payload for display only.

## 7. Data model & inventory

`vms.VM` holds `uuid, name, state, vcpu, mem_mb, description` plus live
`pid, uptime, port, index`.

`vms.inventory(token)` merges two sources:

- **`user/objects`** typed query -> every defined VM with authoritative state
  (`started` / `stopped` / `off`), vCPU (`socket x core x thread`) and memory.
- **`pvm-running-vms`** -> live PID / uptime / console port for running VMs, and
  the automatic UUID discovery. Any running VM missing from the object store is
  still added.

The merged list is ordered **running-first, then by name**, and each VM gets a
stable 1-based `index`. `vms.resolve(vms, selector)` accepts an **index**, an
**exact name or UUID**, or a **unique name prefix**, and reports ambiguity.

## 8. Rendering & theming

- `theme.py` defines the gemini-cli palette as 256-color indices, the glyph set
  (unicode with ASCII fallback), and rounded box-drawing parts. `_enabled`
  (TTY and not `NO_COLOR`) and `_unicode` gate color and glyphs.
- `render.py` builds everything at `width()` = the **full terminal width** and
  draws rounded frames with a title embedded in the top border. `center()` and
  `margin()` exist to offset the block; with full-width rendering the margin is
  0. All width maths strip ANSI escapes so colored and plain output align.
- Input uses `readline` (when available): line editing, a completer that
  completes **commands first, then VM names/indices**, and a display hook that
  shows candidates as a themed multi-column list on the first Tab
  (`show-all-if-ambiguous`). The colored prompt wraps escapes in `\001..\002`
  so readline counts its width correctly.

## 9. Error-handling strategy

Layered, so failures surface as messages at the right level:

- `transport` raises `TransportError` for process/parse failures; it never
  lets a raw traceback escape.
- `session`, `vms`, `monitoring` catch `TransportError` and return empty
  data / an `{"error": ...}` dict where partial operation is sensible.
- `actions` run inside the orchestrator's try/except; a bug yields an error
  status line, not a crash.
- `run_interactive` wraps the whole loop body in a last-resort guard.

## 10. Configuration

All via environment variables (see `config.py` and the README table):
`PLAIVID_SBELL`, `PLAIVID_RUNNING_VMS`, `PLAIVID_USER`, `PLAIVID_STATE_DIR`,
`PLAIVID_CMD_TIMEOUT`, `PLAIVID_PRODUCT`, plus `NO_COLOR` and `PLAIVID_ASCII`.

## 11. Testing

`tests/smoke.py` is a non-interactive, **read-only** end-to-end check meant to
run on the host: it logs in (exercising session recovery), pulls host status,
builds the full inventory, resolves by index/name/prefix, and lists the action
registry - **without changing any VM state**.

```bash
PLAIVID_PASS='...' python3 tests/smoke.py
```

Interactive behaviour (the drawn dashboard, readline Tab listing) can only be
seen on a real terminal; the smoke test covers everything else.

## 12. Where to take it next

Natural extensions, each a small, isolated change:

- **New actions** (console/SPICE via `broker/console`, migrate, clone,
  snapshot/rollback) - just new files in `actions/`.
- **Live auto-refresh** - a timed redraw in `run_interactive`.
- **Alternate transports** - implement an SSH or sabad-HTTP backend behind the
  same `transport.sbell()` signature; nothing above it changes.
- **Per-VM detail view** - a new render function + a `show <id>` builtin using
  the already-fetched `virtual_machine` object fields.

## 13. File map

```
plaivid                      entry point (interactive or one-shot)
plaivid_cli/
  __init__.py  __main__.py  version.py
  config.py                  tunables + env overrides
  transport.py               subprocess + XML envelope (the only I/O boundary)
  session.py                 login / logout / token cache / 185 recovery
  vms.py                     VM model, inventory merge, selector resolve
  monitoring.py              host status
  theme.py                   palette, glyphs, borders
  render.py                  banner, panels, tables, frames
  orchestrator.py            controller: session, refresh, screen, input, dispatch
  actions/
    __init__.py              registry with per-file isolation
    base.py                  action contract + helpers
    start.py stop.py kill.py reset.py pause.py resume.py
tests/
  smoke.py                   read-only data-layer check (run on host)
docs/
  ARCHITECTURE.md            this file
  SBELL-SABAD.md             the PVM control protocol
  REFERENCE.md               quick command cheat-sheet
README.md
```

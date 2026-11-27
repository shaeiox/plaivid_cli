# 01 — Repository Audit

**Phase:** 1.1 technology and architecture validation  
**Audit date:** 2026-10-30  
**Status:** Investigation record; no application code was changed.

## Evidence conventions

- **Source-verified:** read directly from the current repository's executable source or configuration.
- **Documentation claim:** stated by repository documentation; not independently confirmed against a PVM host.
- **Environment observation:** observed only in the discovery sandbox, not on the target PVM system.
- **Proposal / unknown:** not an established fact or an approved implementation decision.

Line references below point to the audited checkout at `d051624` unless otherwise stated.

## Repository and working-tree baseline

- **Environment observation:** branch is `arena/15ca46c8-plaivid-cli`; `HEAD` is `d051624` (`feat: add .gitignore to exclude environment files, caches, and logs`). The working tree was clean at the start of this phase.
- The audit sandbox is Linux x86_64 and has Python 3.11.2. `python3.12`, `uv`, `pytest`, and `pyinstaller` were not found on its `PATH`. This says nothing conclusive about a PVM target.
- No dependency installation, target-host change, or application-code edit was performed for this audit. PyPI metadata was queried over HTTPS without installing packages.

## Current directory structure

```text
.
├── plaivid                         executable script
├── plaivid_cli/
│   ├── __init__.py  __main__.py  version.py
│   ├── config.py                   environment configuration
│   ├── orchestrator.py             App, input, dispatch, refresh
│   ├── transport.py                local subprocess integration, XML envelope
│   ├── session.py                  authentication and token cache
│   ├── vms.py                      VM model, inventory, selection and detail
│   ├── monitoring.py               host/metrics parsing and health calculations
│   ├── logs.py                     read-only SQLite audit-log reader
│   ├── render.py  theme.py         terminal rendering and styling
│   ├── commands/                   command modules and discovery registry
│   └── actions/                    VM operations and discovery registry
├── tests/
│   └── smoke.py                    credentialed PVM-host smoke script
├── docs/
│   ├── ARCHITECTURE.md  REFERENCE.md  SBELL-SABAD.md
│   ├── Plaivid CLI & sbell Reference.md / .pdf / .docx
│   └── architecture/               Phase 1.1 investigation records
├── README.md  REFACTOR.md  TASKS.md
└── .gitignore
```

There is no `pyproject.toml`, `uv.lock`, setup metadata, requirements file, CI configuration, test-runner configuration, or PyInstaller spec in the audited tree.

## Entry points and current commands

- **Source-verified:** `plaivid` imports `plaivid_cli.orchestrator.main`; `python -m plaivid_cli` reaches the same function (`plaivid`, `plaivid_cli/__main__.py`). `main()` selects interactive mode for no arguments and one-shot dispatch otherwise (`orchestrator.py:368–377`).
- Interactive commands are registered in `plaivid_cli/commands/`: `list` (aliases include `status`, `refresh`, `ls`), `overview`, `sort`, `health`, `show`, `log`, `version`, `help`, `logout`, and `quit`. Their exact metadata is in each module.
- VM action modules in `plaivid_cli/actions/`: `start`, `stop`, `kill`, `reset`, `pause`, and `resume`.
- Command/action registries discover Python modules at runtime (`commands/__init__.py`, `actions/__init__.py`). There is no `argparse`, Click, or Typer parser in current source.

## Existing architectural boundaries

- `orchestrator.App` owns session reference, current host/VM data, sort state, interactive loop, redraw, command dispatch, and action execution (`orchestrator.py:34–43, 68–79, 85–176, 334–365`).
- Command plugins depend on a `CommandContext` facade (`commands/base.py`); VM actions receive a separate minimal context (`orchestrator.py:23–32`).
- `transport.py` is the actual subprocess boundary for PVM command calls. `logs.py` separately opens the local SQLite audit database, so not all infrastructure I/O uses `transport.py`.
- `vms.py` and `monitoring.py` parse XML payloads into a mix of a mutable `VM` class and dictionaries. `render.py` handles formatting and `theme.py` handles colors/glyphs, though commands directly invoke rendering and some screen operations through the context.
- Registries provide per-module import error isolation, not a general dependency-injection or third-party plugin framework.

## Existing PVM integrations (source-verified)

`transport.py` constructs an argv list and launches configured local executable commands with `subprocess.Popen(..., shell=False by default)`. Defaults are `sudo sbell` and `pvm-running-vms`; stdin is `DEVNULL`; stdout/stderr are captured; default timeout is 30 seconds (`config.py:11–20`, `transport.py:66–115`).

Code uses these sbell module/command pairs:

- `user/login`, `user/whoami`, `user/logout`, `user/list-current-user-sessions` — `session.py`.
- `user/objects` — VM listing, VM detail, and tap-interface mapping — `vms.py`.
- `sball/show` — host/cluster/node status — `monitoring.py`.
- `monitoring/metrics` — detailed metrics — `monitoring.py`.
- `license/show` — license fields — `monitoring.py`.
- `vm/start`, `vm/stop`, `vm/kill`, `vm/reset`, `vm/pause`, `vm/resume` — action modules.

The app also executes the local `pvm-running-vms` binary. No SSH client, HTTP client, or direct sballd socket implementation exists in source.

## Existing data models, state, and rendering

- `vms.VM` is a mutable object with UUID, name, state, CPU/memory, description, live PID/uptime/port, and display index (`vms.py:20–44`).
- Other outputs are dictionaries: host status (`monitoring.py:21–70`), metrics snapshots (`monitoring.py:87–175`), VM detail (`vms.py:267–339`), license, action result, and health report.
- `App` stores the current session, VM list, host dictionary, status string, and sorting fields in memory. There is no explicit immutable snapshot or durable application state store.
- `draw()` clears the screen and prints complete dashboard output. Overview loops collect, clear, and print a new complete view. It is not a widget tree or explicit dirty-region renderer (`orchestrator.py:81–103`, `commands/overview.py:32–61`).
- `render.py` is a 462-line terminal formatting module; `theme.py` reads terminal/environment properties at import time.

## Existing dependencies and Python claims

- **Source-verified:** runtime imports are from the Python standard library. No third-party package is imported by current application code.
- **Documentation claim:** README says Python 3.6+ (`README.md:21–26`); architecture documentation says Python 3.6+ and mentions host Python 3.6.8 (`docs/ARCHITECTURE.md:27–29, 45–46`). These claims are historical documentation, not a current target-host observation.
- **Project decision supplied for this phase:** Linux, modern Python, target Python 3.12+. This is a new target and has not been validated on the PVM system.

## Tests and evidence limits

`tests/smoke.py` requires `PLAIVID_PASS` and a working PVM host, logs in, reads host status, inventory and action registry, resolves sample VMs, then logs out (`tests/smoke.py:1–59`). It does not exercise actions. No unit tests, parser fixtures, fake transport, terminal tests, or coverage configuration exist.

The smoke test is described as read-only with respect to VM state, but it does create a PVM login session and writes/removes the local cached-session file through session handling. It is not safe to run without considering session and credential effects.

No live PVM host was available during this investigation. Thus interface behavior, actual error codes/exit codes, schemas, membership/quorum semantics, version variation, and command latency remain unverified except as documented claims or behavior inferred from caller code.

## Retain / replace / redesign assessment

| Component | Initial disposition | Evidence and caveat |
|---|---|---|
| PVM action definitions and XML examples | Retain as protocol knowledge; redesign execution boundary | Action files encode concrete command bodies (`actions/*.py`). Reconfirm against supported PVM builds and tests before operational use. |
| VM inventory merge | Retain the domain need; redesign collection and freshness | `vms.inventory()` combines object query and running-process table (`vms.py:114–149`). The sources are not batched together today. |
| Session lifecycle | Retain lifecycle requirements; redesign secrets and process invocation | `session.py` documents useful reuse/recovery, but password argv exposure and silent cache errors require review. |
| Existing health thresholds | Investigate before retaining as policy | Thresholds are hard-coded in `monitoring.health_report()` (`monitoring.py:201–265`); no requirements or operational owner validate them. |
| Mutable VM and dictionary payloads | Redesign toward explicit validated boundary data and immutable published snapshots | Current types are inconsistent and shared mutable state has no freshness metadata. |
| Orchestrator | Retain as behavioral inventory, redesign into explicit application/use-case orchestration | It presently combines lifecycle, I/O sequencing, terminal loop, dispatch, and action safety. |
| Custom renderer/theme | Use as visual reference; replace or keep only after TUI prototype | Full-screen ANSI clear/reprint is the current approach; Textual is proposed, not yet validated. |
| Command/action registries | Reassess; keep only if they serve confirmed extension needs | They support modules but lack duplicate-name validation and state applicability is not enforced at action dispatch. |
| SQLite audit reader | Retain only if local audit access is a confirmed product capability | It is tied to `/var/log/pvm/messages.db` and an assumed schema (`logs.py:14, 30–56`). |
| Smoke test | Retain as an eventual integration-test pattern, not as the sole suite | Requires live host credentials; does not provide isolated regression coverage. |

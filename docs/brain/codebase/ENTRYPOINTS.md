# Project entry points

| Project | Command | Python target | Purpose |
|---|---|---|---|
| Engine distribution `pvm-control-engine` | `pvm-control-engine serve` | `pvm_control_engine.bootstrap:main` | Start the local Unix-socket RPC Engine |
| Engine | `pvm-control-engine login` | `pvm_control_engine.bootstrap:main` | Authenticate locally in an echo-disabled terminal; not exposed over IPC |
| UI distribution `plaivid-ui` | `plaivid` (no args or `tui`) | `plaivid_ui.engine_client.cli:main` | Launch the Textual client |
| UI | `plaivid health`, `inventory`, `host`, `overview`, `detail`, `audit`, `operate`, `logout` | `plaivid_ui.engine_client.cli:main` | UI-owned CLI requests through the local Engine RPC client |
| UI package module | `python -m plaivid_ui` | `plaivid_ui.__main__:main` | Same UI entry point |
| Repository validation | `python scripts/validate_brain.py` | `scripts/validate_brain.py:main` | Check two-project metadata, docs navigation and UI import boundary |

Engine installation/build metadata: `pvm_control_engine/pyproject.toml`; UI metadata: `UI/pyproject.toml`. Install and verification instructions live in each project README and [Build workflow](../workflows/BUILD.md). UI requires a separately installed/running Engine on the local Unix socket and an Engine-owned authenticated session. The UI has no password or token RPC.

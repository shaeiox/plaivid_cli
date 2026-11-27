# Plaivid UI (`plaivid-ui`)

The UI project owns the Textual presentation, local IPC client, UI wire DTOs, tests, assets, and UI documentation. Its import package is `plaivid_ui` under `tui/src/`, and its console command is `plaivid`. It has no Engine Python dependency and does not execute sbell, PVM tools, or child processes.

## Requirements and independent install

Python 3.12 or later (the project's declared runtime floor). Install the UI by itself in its own environment:

```sh
cd UI
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Install `pvm-control-engine` separately using its own README and environment. Start it as the trusted local PVM account, authenticate on its terminal, and then start the UI:

```sh
pvm-control-engine serve
# In the Engine terminal/session:
pvm-control-engine login
# In the UI terminal:
plaivid
```

The UI socket path is `PLAIVID_CONTROL_SOCKET`, then `$XDG_RUNTIME_DIR/pvm-control-engine.sock`, then the configured Engine state directory. UI authenticated requests validate the Engine-owned session; passwords and tokens are never sent to the UI or included in IPC. See [`docs/IPC.md`](docs/IPC.md).

## Development

From `UI/`:

```sh
python -m pytest -q
ruff check tui/src/plaivid_ui tests
pyright
python -m build --outdir /tmp/plaivid-ui-dist
```

The combined pre-split tests remain archived as source in `docs/migration/legacy-tests/`; they are not an active suite because they coupled presentation tests to the retired runtime. Active UI tests use fake RPC exchanges and enforce the import boundary. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/IPC.md`](docs/IPC.md), and [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md).

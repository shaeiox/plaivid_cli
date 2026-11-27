# PVM Control Engine (`pvm-control-engine`)

The Engine project exclusively owns authentication/session state, local PVM reads and operations, canonical UUID resolution, sbell command construction, process execution, audit, authorization and operation-safety policy. Its import package is `pvm_control_engine` under `src/`; the console command is `pvm-control-engine`.

## Requirements and install

Python 3.12 or later (the project's declared runtime floor). Install the Engine independently from this directory:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Run Engine commands as the local account permitted to use PVM:

```sh
pvm-control-engine login
pvm-control-engine serve
```

`login` prompts for credentials locally with terminal echo disabled. The approved local sbell integration retains the default-deny `PLAIVID_ALLOW_CREDENTIAL_ARGV` policy because existing credentials may be visible in process arguments. The UI cannot log in by RPC and never receives the token.

The service exposes a bounded, explicit `plaivid.engine.v1` JSON-RPC API over a private AF_UNIX socket. UI implementation and contract documentation are in the separate [`../UI/`](../UI/) project and [`../UI/docs/IPC.md`](../UI/docs/IPC.md). The Engine distribution does not include UI dependencies.

## Development and verification

```sh
python -m pytest -q
ruff check src/pvm_control_engine tests
pyright
python -m build --outdir /tmp/pvm-control-engine-dist
```

Tests use fakes and temporary sockets; they do not perform destructive real PVM operations. Review [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md), and [`docs/REAL_PVM_VALIDATION.md`](docs/REAL_PVM_VALIDATION.md) before any owner-run host validation.

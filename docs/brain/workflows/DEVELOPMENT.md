# Development workflow

This repository has two independent installable projects. Use Python 3.12 or later, matching both `pyproject.toml` declarations.

## Engine development

From `pvm_control_engine/`:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check src/pvm_control_engine tests
.venv/bin/pyright
```

Engine runtime configuration and credential policy: [`pvm_control_engine/docs/ENVIRONMENT.md`](../../../pvm_control_engine/docs/ENVIRONMENT.md). Local PVM access is only needed for explicitly authorized host use; tests use fakes.

## UI development

From `UI/`:

```sh
./scripts/setup.sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check tui/src/plaivid_ui tests
.venv/bin/pyright
```

The UI setup script creates/reuses only `UI/.venv` and installs `plaivid-ui` from this project. It does not install or configure the Engine. UI socket and terminal settings: [`UI/docs/ENVIRONMENT.md`](../../../UI/docs/ENVIRONMENT.md); wire method/security contract: [`UI/docs/IPC.md`](../../../UI/docs/IPC.md).

## Repository checks

From the checkout root, run `python scripts/validate_brain.py`. Build each project from its own directory; see [`BUILD.md`](BUILD.md). The local sandbox currently provides Python 3.11.2, so tests/builds performed there are supplemental and do not satisfy the declared Python >=3.12 supported-runtime install check. Do not run destructive host tests; see [`TESTING.md`](TESTING.md) and the Engine owner-run [PVM validation plan](../../../pvm_control_engine/docs/REAL_PVM_VALIDATION.md).

# Development workflow

Navigation: [`../README.md`](../README.md) · [`BUILD.md`](BUILD.md) · [`TESTING.md`](TESTING.md) ·
[`../codebase/ENTRYPOINTS.md`](../codebase/ENTRYPOINTS.md).

## Environment and required tools

| Requirement | Evidence |
|---|---|
| Linux host | `scripts/setup.sh` rejects non-Linux `uname -s`; `README.md` |
| Python **>=3.12** with `venv` + `ensurepip` | `pyproject.toml` `requires-python`, `scripts/setup.sh`, `docs/ENVIRONMENT.md` |
| Local `sbell` (default `sudo sbell`) and `pvm-running-vms` | Only needed for authorized real-host use, not for unit tests. `README.md`, `plaivid_cli/config.py::load_settings` |
| Runtime dependency `textual>=0.47` (brings Rich) | `pyproject.toml` |
| Dev tools: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.6`, `pyright>=1.1`, `build>=1.2` | `[project.optional-dependencies] dev` in `pyproject.toml` |

**Known environment limitation (documented, not invented):** `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`
records that the original workspace had Python 3.11.2 only and that Python 3.12 install/smoke
remained unchecked. `pyproject.toml` still declares `>=3.12`. Do not claim 3.12 verification
from a 3.11 interpreter.

## Setup

```bash
./scripts/setup.sh                    # creates/reuses .venv, installs -e '.[dev]', checks plaivid --help
source .venv/bin/activate
plaivid --help
```

`scripts/setup.sh` never installs OS packages, never uses `sudo pip`, and never changes system
Python. `PLAIVID_PYTHON` selects a specific 3.12+ interpreter for setup only. If creating the
venv manually, use `python -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'`.

## Configuration for local work

Configuration is **environment-only**; no `.env` loader. Full reference: `docs/ENVIRONMENT.md`.
For local unit work no PVM configuration is needed — tests use fake providers/process runners
and synthetic fixtures. Useful non-secret settings:

```bash
PLAIVID_LOG_LEVEL=DEBUG plaivid config
PLAIVID_CHART=braille plaivid            # force chart mode (docs/ENVIRONMENT.md)
PLAIVID_ALLOW_CREDENTIAL_ARGV=1 ...      # explicit risk acknowledgement; NOT a mitigation
```

Never set `PLAIVID_ALLOW_CREDENTIAL_ARGV` as a general default. Credentials/tokens in `sbell`
argv are an unresolved risk (`README.md`, `docs/REAL_PVM_VALIDATION.md`).

## Local execution

| Goal | Command | Notes |
|---|---|---|
| One-shot read | `plaivid config`, `plaivid inventory --json`, `plaivid host --json`, `plaivid detail UUID` | `config`/`diagnostics` never contact PVM |
| Interactive dashboard | `plaivid` (requires TTY) | `1`/`2`/`3` tabs, `r` refresh, `q` quit |
| Alternative launchers | `./plaivid`, `python -m plaivid_cli` | both reach `bootstrap.main` |
| Tests | `python -m pytest -q --ignore=tests/smoke.py` | [`TESTING.md`](TESTING.md) |
| Lint / types | `ruff check plaivid_cli tests/unit`, `pyright` | `pyproject.toml` config |
| Wheel | `python -m build --wheel` | [`BUILD.md`](BUILD.md) |
| Brain audit | `python scripts/validate_brain.py` | [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md) |

A non-TTY `plaivid` invocation returns exit code 2 with an explanatory message; use a one-shot
command in scripts. See [`../contracts/API_CONTRACTS.md`](../contracts/API_CONTRACTS.md).

## Development conventions

1. **Follow the brain workflow** in `AGENTS.md`: docs → canonical files → contracts/tests →
   impact analysis → code → tests → brain updates.
2. **Preserve layer direction.** `domain/` imports nothing internal above itself;
   `application/` and `infrastructure/` never import presentation; presentation never imports
   infrastructure. Enforced by `tests/unit/test_architecture_boundaries.py`.
3. **One composition root.** Add concrete wiring only in `plaivid_cli/bootstrap.py::build_runtime`;
   use `plaivid_cli/application/ports.py` `Protocol`s for new outbound capabilities.
4. **Truthfulness.** Missing data stays `None`/`N/A`; do not synthesize healthy values,
   do not treat process evidence as object state, and do not claim lifecycle completion without
   evidence.
5. **Redact every new output surface** with `plaivid_cli/domain/redaction.py::redact_text`.
6. **Fail closed** on parsing, admission, and credential/argv risk. No blind retries after
   `OUTCOME_UNKNOWN`.
7. **Do not edit `plaivid_cli/legacy/`** for runtime work; see
   [`../codebase/MODULE_INDEX.md`](../codebase/MODULE_INDEX.md).
8. **Keep `__all__` facades in sync** when adding/renaming public symbols.
9. **File size/cohesion:** split by responsibility (existing pattern: `application/collection/`,
   `application/operations/`, `presentation/tui/pages/`); do not grow unrelated helpers into one
   module.
10. **Tests are fake-backed.** Never require a real PVM host, never run `tests/smoke.py` as part
    of local verification, and never add a test that contacts production
    (`docs/REAL_PVM_VALIDATION.md`).

## State and generated artifacts

`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `build/`, `dist/`, `*.egg-info/`,
`.coverage`, `coverage.xml`, `htmlcov/`, and the session state directory are ignored by
`.gitignore`. Do not commit them. Session tokens live outside the repository under
`$XDG_STATE_HOME/plaivid` (or `~/.local/state/plaivid`).

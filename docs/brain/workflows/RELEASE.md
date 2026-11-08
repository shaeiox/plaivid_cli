# Release workflow

**Status of this document:** it records only what the repository actually contains. Most of a
conventional release process is **absent**; missing items are listed explicitly rather than
invented. Navigation: [`../README.md`](../README.md) · [`BUILD.md`](BUILD.md) ·
[`DEVELOPMENT.md`](DEVELOPMENT.md) · [`TESTING.md`](TESTING.md).

## Verified release-related facts

| Fact | Evidence |
|---|---|
| Project name `plaivid-cli`, `[project.scripts] plaivid`, `Requires-Python >=3.12`, runtime dep `textual>=0.47` | `pyproject.toml` |
| Build backend setuptools; wheel built with `python -m build --wheel` | `pyproject.toml`, `setup.py`, `README.md`, `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` |
| Retired `plaivid_cli.legacy*` is excluded from distribution artifacts | `setup.py::RuntimeBuildPy`, `tests/unit/test_distribution.py` |
| Manual version constant `__version__ = "1.2.0"`; commit `a6a64d9 Bump version to 1.2.0` | `plaivid_cli/version.py`, `git log` |
| `pyproject.toml` still declares `version = "0.4.0"`; historical wheel name `dist/plaivid_cli-0.4.0-py3-none-any.whl` | `pyproject.toml`, `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` |
| Install/rollback/removal guidance is user-facing prose, not automation | `README.md` ("reinstall the previously approved wheel"; `python -m pip uninstall plaivid-cli`) |
| Real-host validation and security approval are required before relying on the CLI against a host; all items are **PENDING MANUAL PVM VALIDATION** | `docs/REAL_PVM_VALIDATION.md`, `README.md`, `docs/architecture/adr/README.md` |
| `docs/architecture/adr/0010-packaging.md` describes a *conditional* PyInstaller one-directory candidate, offline delivery, signing, SBOM, versioned staging, and rollback — labelled "Partially implemented" / not accepted | `docs/architecture/adr/README.md`, `docs/architecture/adr/0010-packaging.md` |

## Versioning policy (as implemented)

- `plaivid_cli/version.py` is the authoritative runtime version used by
  `plaivid_cli/presentation/cli/parser.py::build_parser` for `--version` and re-exported by
  `plaivid_cli/__init__.py`.
- `pyproject.toml` carries a **separate** build version. There is no single-source-of-truth,
  no dynamic version hook, no tag-derived version, and no automated bump script.
- **Unresolved inconsistency:** runtime `1.2.0` vs build metadata `0.4.0`. Any release must
  reconcile these deliberately; this knowledge base does not assume which is correct. Tracked in
  [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md).

## Packaging and distribution (verified steps only)

```bash
./scripts/setup.sh                 # development environment; installs -e '.[dev]'
source .venv/bin/activate
python -m pytest -q --ignore=tests/smoke.py
ruff check plaivid_cli tests/unit
python -m build --wheel            # dist/*.whl
```

`README.md` also documents removing the package with
`python -m pip uninstall plaivid-cli` from the same environment, noting that this does not alter
system Python or remove the user session cache; clear the cache with `plaivid logout`. For
rollback, reinstall the previously approved wheel. No automation performs these steps.

`sbell` and `pvm-running-vms` remain host prerequisites and are not bundled. The wheel is
pure Python (`py3-none-any`) and declares `>=3.12`.

## Release gates documented but not automated

1. **Owner-run PVM validation** (`docs/REAL_PVM_VALIDATION.md`) — request/response contract,
   permissions, metric schemas, lifecycle acceptance/completion, credential argv exposure.
2. **Security/owner decision** on the unresolved credential-in-argv exposure;
   `PLAIVID_ALLOW_CREDENTIAL_ARGV` is a default-deny acknowledgement, not a fix
   (`docs/architecture/adr/README.md`, `docs/ENVIRONMENT.md`).
3. **Python 3.12 install/smoke** and target-platform compatibility remain unchecked in the
   recorded workspace (`docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`).
4. **No production access** is authorized by any ADR or spec in this repository.

## Explicitly missing (do not assume these exist)

- CI/CD configuration (`.github/workflows/`, GitLab CI, Jenkinsfile, etc.) — none tracked.
- Git tags / release branches / tag-derived versioning — `git tag -l` is empty; repository has
  two commits on the recorded history.
- Changelog, release notes, or release checklist.
- Automated version bump, lockfile, SBOM, dependency pinning, artifact signing, checksum
  publication, or trusted-channel distribution.
- PyPI/publishing credentials or upload configuration.
- Installer, systemd unit, container image, PyInstaller spec, automatic updater, deployment
  script, or rollback automation.
- Staging/versioned deployment directories and a defined supported-host matrix.
- A named release owner, cadence, or approval workflow beyond the ADR index's
  "Decision owner" notes in `docs/architecture/adr/0010-packaging.md`.

## Practical interpretation for an agent

A "release" in this repository currently means: build a wheel in a project-local venv, verify
the local suite and packaging tests, reconcile the two version constants deliberately, and
obtain the owner-run validation/security approvals described above. **Do not** add a pipeline,
signing scheme, or deployment mechanism unless the task explicitly asks for it and the
architecture contracts in [`../contracts/MODULE_CONTRACTS.md`](../contracts/MODULE_CONTRACTS.md)
are updated accordingly.

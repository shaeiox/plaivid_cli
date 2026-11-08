# Build and packaging

Navigation: [`../README.md`](../README.md) · [`DEVELOPMENT.md`](DEVELOPMENT.md) ·
[`TESTING.md`](TESTING.md) · [`RELEASE.md`](RELEASE.md).

## Verified build procedure

`pyproject.toml` declares `[build-system] requires = ["setuptools>=77", "wheel"]` with
`build-backend = "setuptools.build_meta"`. `setup.py` overrides `build_py` with
`setup.py::RuntimeBuildPy` to filter retired packages.

```bash
./scripts/setup.sh                     # installs build>=1.2 via .[dev]
source .venv/bin/activate
python -m build --wheel                # output: dist/*.whl
python -m pip install -e '.[dev]'      # editable development install
python -m build                        # sdist + wheel (build>=1.2)
```

`scripts/setup.sh` ends by verifying `.venv/bin/plaivid --help` (no PVM connection).
`README.md` documents `python -m build --wheel` as the standard wheel command and
`python -m pip uninstall plaivid-cli` as removal; it also notes rollback by reinstalling the
previously approved wheel.

## Package selection and artifacts

| Item | Verified behavior | Evidence |
|---|---|---|
| Included packages | `find_packages(include=["plaivid_cli*"], exclude=["plaivid_cli.legacy*"])` | `setup.py`, `pyproject.toml`, `tests/unit/test_distribution.py` |
| Excluded | `plaivid_cli.legacy` and all its subpackages; `RuntimeBuildPy.find_package_modules` returns `[]` for them | `setup.py::RuntimeBuildPy`, `tests/unit/test_distribution.py` |
| Console script | `plaivid = "plaivid_cli.bootstrap:main"` | `pyproject.toml` |
| Package data | `include_package_data=False`; `assets/plaivid-logo.svg` is not shipped (wordmark is embedded as text in `plaivid_cli/presentation/logo.py::logo_text`) | `setup.py`, `plaivid_cli/presentation/logo.py` |
| Wheel metadata | `Requires-Python: >=3.12`, runtime dependency `textual>=0.47` | `pyproject.toml`, `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` |
| Historical artifact name | `dist/plaivid_cli-0.4.0-py3-none-any.whl` recorded in the audit; 32 wheel entries, no legacy modules | `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` |
| Ignored artifacts | `build/`, `dist/`, `*.egg-info/`, `.coverage`, `coverage.xml`, `htmlcov/` | `.gitignore` |

## Supported platforms

- **Linux only** for the setup script and the PVM local-command design (`scripts/setup.sh`,
  `README.md`). No Windows/macOS build target, container image, or cross-platform wheel is
  declared.
- **Python >=3.12** is the declared runtime target. Pure-Python wheel (`py3-none-any`).
- `sbell` and `pvm-running-vms` remain **host prerequisites**; they are not bundled.
- No lockfile, SBOM, signature, checksum, installer, systemd unit, Docker/PyInstaller spec,
  or CI workflow exists in the repository (verified by `git ls-files` and
  `docs/architecture/adr/0010-packaging.md`).

## Build/verification checks

```bash
python -m pytest -q --ignore=tests/smoke.py
ruff check plaivid_cli tests/unit
pyright
python -m build --wheel
```

`tests/unit/test_distribution.py` must pass: it asserts all active subpackages are present and
no `plaivid_cli.legacy*` package is packaged. `tests/unit/test_setup_script.py` asserts
`scripts/setup.sh` is executable with LF line endings.

## Known limitations and conflicts

1. **Version mismatch (verified).** `pyproject.toml` still declares `version = "0.4.0"` while
   `plaivid_cli/version.py` exports `__version__ = "1.2.0"`; `--version` prints 1.2.0 and the
   historical wheel was named 0.4.0. There is no single-source versioning mechanism. Tracked in
   [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md).
2. **ADR 0010 proposes a PyInstaller one-directory bundle** as a *conditional candidate*, but
   the implemented build is a setuptools wheel. Treat `docs/architecture/adr/0010-packaging.md`
   as a proposal, not shipped behavior.
3. **Python 3.12 install/smoke is not verified** in the recorded workspace
   (`docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`).
4. **No release pipeline** is present; see [`RELEASE.md`](RELEASE.md).
5. Historical audit claims `pyright` reported 0 errors under its toolchain; a newer Pyright
   reports pre-existing mixin attribute diagnostics on both the current tree and the HEAD
   baseline. Do not treat that historical claim as a current gate. See
   [`../maintenance/DOCUMENTATION_AUDIT.md`](../maintenance/DOCUMENTATION_AUDIT.md).

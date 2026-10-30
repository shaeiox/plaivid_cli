# ADR 0003 — Dependency Groups and Tooling

- **Status:** Accepted (workflow/tool choices); exact pins and runtime set remain conditional
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Engineering owner; release engineering approves runtime artifacts.

## Context and evidence

- **Repository fact:** application imports only the Python standard library; there is no `pyproject.toml`, lockfile, dependency manifest, CI or test-runner configuration.
- **Approved choices:** uv for dependency management; pytest for testing; Ruff and Pyright for code quality.
- **Unverified:** target PVM wheel/ABI availability and the final set of application dependencies.

## Decision

Use uv as the **project/dependency manager**, and separate packages into three explicit groups. A package must not enter the runtime merely because it is useful in tests or development.

### Runtime dependencies

Only packages imported by shipped application code belong here. Candidate runtime packages are:

- Textual (ADR 0001, conditional); Rich is direct only if imported directly, otherwise use Textual's integration.
- Typer for process-level CLI, conditional on CLI grammar design.
- Pydantic at validated adapter/configuration boundaries where it provides material validation value.
- psutil only if an approved local-monitoring need remains unmet by PVM's existing monitoring interface.

Do not automatically include all candidates above. SQLAlchemy, Alembic, HTTPX, structlog, tenacity, platformdirs, and pydantic-settings are not runtime dependencies absent a separate accepted need.

### Development/build dependencies

- uv manages project environment, resolution/lock, and repeatable sync/build workflow. It need not be installed on the PVM target.
- Ruff and Pyright are development/CI quality tools, not runtime dependencies.
- Packaging/build tools (including PyInstaller if ADR 0010 selects it) belong in a controlled build environment, not necessarily in the application environment.

### Test-only dependencies

- pytest is the approved test runner.
- pytest-asyncio is optional only if direct asyncio tests require it; Textual testing APIs may be sufficient for UI tests.
- Hypothesis is optional for stable pure parsing/domain contracts where property-based tests have demonstrated value.

Use locked, reviewed dependency resolution, distinct groups/extras, declared Python constraints, and CI sync from the lock. Verify wheel and native-extension availability for each supported Linux architecture. Capture exact versions only after a compatibility matrix/build is tested; the Phase 1.1 PyPI observations are not a lockfile.

## Consequences

- Runtime footprint can remain smaller than the full developer/test toolchain.
- A project lockfile and group policy become required for reproducible builds.
- Developers/CI need uv; target servers do not need uv unless packaging ADR 0010 explicitly chooses it for runtime provisioning.
- Dependency upgrades require compatibility and package-artifact tests.

## Unresolved / evidence required

Final CLI grammar and direct Rich use; Pydantic model cost; psutil need; test plugin needs; target wheel availability; exact supported version ranges and update cadence. Individual library assessments are in `../03-technology-evaluation.md`.

# ADR 0003 — Dependency Management and Quality Tools

- **Status:** Proposed
- **Date:** 2026-10-30

## Context

Repository currently has no package metadata, lockfile, dependency manifest, test runner configuration or CI configuration. The approved proposal names uv, pytest, Ruff and Pyright plus numerous optional runtime packages.

## Proposal

Adopt uv for developer/CI environment creation, dependency resolution, lockfile and reproducible sync. Use pytest, Ruff and Pyright as development/CI tools. Keep those tools out of the packaged PVM runtime. Add optional tools only when tests/requirements use them; lock supported platforms and evaluate wheel availability before pins.

## Consequences

- Adds a defined, repeatable development workflow.
- Requires lockfile review and CI policy; does not imply uv must be installed on target PVM.
- Build and runtime dependency groups must be distinct.

## Validation required

Test uv lock/sync/build on Python 3.12 and target build architecture, offline artifact process, Pyright invocation/runtime, and locked PyInstaller build. Final exact versions are not decided by the PyPI point-in-time report.

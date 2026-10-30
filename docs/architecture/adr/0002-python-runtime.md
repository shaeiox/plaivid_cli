# ADR 0002 — Python Runtime

- **Status:** Proposed; conditional on target PVM discovery
- **Date:** 2026-10-30

## Context

Approved target is Python 3.12+ on Linux. Repository docs claim a PVM host has Python 3.6.8, but this was not checked against a target. The sandbox has Python 3.11.2. Replacing system Python is not an approved operational action.

## Proposal

Keep application Python isolated from system Python. First prototype a Python 3.12+ PyInstaller one-directory build for each supported architecture, built on the oldest supported Linux/glibc baseline. Keep host `sbell` and `pvm-running-vms` external prerequisites. If PyInstaller fails compatibility or support review, compare a signed, privately managed standalone interpreter environment.

## Consequences

- The CLI can target Python 3.12+ without requiring system interpreter upgrades if bundled runtime is compatible.
- Build and test responsibilities include native libraries, glibc, interpreter/dependency security updates, artifact signing and rollback.
- PyInstaller does not bundle glibc; target compatibility cannot be inferred from Python version alone.

## Validation required

Collect PVM distribution, architecture, glibc, mount/permission and vendor-support policy. Test the packaged executable on the oldest supported host cohort without modifying production systems. Decide only after evidence.

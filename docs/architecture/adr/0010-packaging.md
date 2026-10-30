# ADR 0010 — Linux Packaging

- **Status:** Proposed; conditional on PVM target profile
- **Date:** 2026-10-30

## Context

Target is Linux/Python 3.12+, while PVM host Python availability and glibc/architecture are unknown. No packaging configuration exists. Local vendor tools must remain available to the app. PyInstaller 6.22.3 was the latest package version returned by PyPI at investigation time; no artifact was built.

## Proposal

Prototype a signed/checksummed PyInstaller one-directory bundle with Python 3.12+ for each supported architecture, built against the oldest supported Linux/glibc baseline. Keep sbell and pvm-running-vms as declared system prerequisites. Do not use one-file mode unless host temp/noexec policy and startup behavior are confirmed. If incompatible with target/vendor policy, evaluate a privately managed standalone runtime.

## Consequences

- Application interpreter and Python dependencies can be isolated from system Python.
- glibc and other system ABI compatibility remain target constraints; per-cohort builds may be required.
- Distribution lifecycle must include native dependency scanning, updates, signing, rollback, and offline transfer.

## Validation required

Target inventory, vendor approval, reproducible build, runtime launch without Python installed, terminal signal/resize tests, native dependency audit, sbell lookup, offline install/update, and tested rollback on supported non-production hosts.

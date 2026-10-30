# ADR 0010 — Linux Packaging and Offline Deployment

- **Status:** Conditional
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Release/platform owner; security owner approves signing/trust; PVM vendor/operations approves host compatibility.

## Context and evidence

- **Repository fact:** there is no project metadata, lockfile, PyInstaller spec, release pipeline, installer, or update/rollback mechanism.
- **Approved constraint:** Linux and Python 3.12+ target (runtime requirement owned by ADR 0002); local PVM vendor commands remain host prerequisites.
- **Unknown:** supported PVM distribution, architecture, glibc, executable mount policy, network availability, vendor policy, install paths and administrator workflow.

## Decision

Conditionally prototype a **PyInstaller one-directory artifact** containing the selected Python 3.12+ runtime and application dependencies. Do not require uv or a system Python at application launch. `sbell` and `pvm-running-vms` remain explicit local host dependencies and must be discovered/validated safely.

This ADR owns artifact format and lifecycle; ADR 0002 owns the Python version/runtime requirement. A PyInstaller bundle is a candidate, not accepted until host compatibility and vendor policy are evidenced. PyInstaller does not bundle Linux glibc; build/test against the oldest supported Linux ABI and produce separate artifacts per supported architecture/cohort when required. Do not use one-file mode by default due extraction, temp/noexec, startup and diagnostics concerns.

### Offline deployment and artifact integrity

- Build artifacts in controlled CI from locked dependencies and a documented build image/toolchain. Capture artifact provenance, dependency inventory/SBOM as required by security policy, build ID and supported target matrix.
- Support offline delivery: package all required Python runtime/dependency files, transfer through an approved channel, and make installation possible without package-index access. Do not assume the PVM host can download updates.
- Sign artifacts or provide a cryptographic checksum through an authenticated trusted channel; checksum alone detects accidental corruption but does not establish publisher authenticity. Define verification key distribution/trust and operator verification steps.
- Stage new versions in a separate versioned directory; validate before switching the active entry point. Preserve a known-good prior version until the new version passes a launch/read-only health check. Define rollback, failed-upgrade cleanup, and compatibility with state/config formats before release.
- Do not add an automatic updater or modify system services/configuration without a separately approved operational design.

### Update and rollback ownership

A release owner must define cadence, vulnerability response, signing-key rotation, channel/approval, artifact retention, rollback trigger and support lifetime. The application must not overwrite a running version in place. Session/config data is separate from the immutable application bundle and governed by ADR 0008/0012.

## Consequences

- One-directory bundles are easier to inspect, stage, diagnose and roll back than an extracted one-file executable, but use more disk.
- Native extension and system ABI compatibility still require target tests; packaging does not remove the need for host PVM tools or privileges.
- Offline release requires reproducible builds, artifact transport, trust bootstrap, and an operator runbook.

## Validation required

Target OS/architecture/glibc/mount policy; vendor support approval; reproducible build; launch without host Python; local tool lookup and privilege behavior; terminal signals/resize; native dependency audit; offline installation/update; signature/checksum verification; staged activation and rollback test on non-production representative hosts. No target changes or artifact builds occurred in this investigation.

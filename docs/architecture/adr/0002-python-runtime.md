# ADR 0002 — Python Runtime Target

- **Status:** Accepted (target version constraint); runtime delivery mechanism remains open
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Product/platform owner; release engineering owns runtime support matrix.

## Context and evidence

- **Approved constraint:** Linux product targeting Python 3.12+.
- **Repository documentation only:** README/architecture docs claim a PVM host has Python 3.6.8. No target host was inspected; the claim is not evidence of the current supported PVM fleet.
- **Environment observation:** discovery sandbox has Python 3.11.2. It is not the target and does not satisfy the product runtime target.
- **Repository fact:** no project metadata or packaged runtime is present.

## Decision

The application runtime target is **Python 3.12 or newer**, subject to a declared and tested minor-version policy. Do not replace or upgrade the PVM system Python as an application installation step.

This ADR decides the **Python runtime requirement only**. It does not choose PyInstaller, uv-based target installation, containerization, or artifact layout. Those are owned by ADR 0010 (packaging). If the target environment cannot run the supported Python 3.12+ application runtime without changing unsupported system components, pause deployment design and obtain product/platform approval; do not silently lower the Python target.

## Target compatibility requirements

Before selecting a delivery mechanism, collect for every supported PVM cohort:

- PVM release and supported host distribution/base release.
- CPU architecture/word size and kernel/glibc baseline; any additional native library ABI dependencies.
- Existing Python versions (fact-finding only), vendor support policy, and whether application files may execute from user-writable/staged locations.
- Permissions, filesystem mount flags (including `noexec` locations), shell/utilities, and access to `sbell`/`pvm-running-vms`.
- Whether network access is unavailable and deployment must be offline.

A runtime is compatible only when the **Python 3.12+ interpreter plus every selected dependency/native extension and the application artifact** launch and operate on the oldest supported cohort without modifying system Python. Testing just `python --version` is insufficient.

## Consequences

- Existing documented Python 3.6 compatibility is superseded as a product target, but remains a deployment risk until the host cohort is measured.
- Python 3.12+ dependency metadata does not prove that binary wheels, PyInstaller artifacts, or system ABI dependencies support a particular PVM appliance.
- Interpreter security updates and supported minor-version cadence need an owner.

## Unresolved / evidence required

Actual host matrix, whether a privately managed runtime is permitted, which Python 3.12+ minor releases will be supported, and the update/support policy. Packaging comparison and offline artifact questions belong to ADR 0010.

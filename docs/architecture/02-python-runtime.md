# 02 — Python Runtime and Packaging Investigation

**Audit date:** 2026-10-30  
**Status:** Recommendation conditional on target-host discovery; no target system was queried or changed.

## Facts established

- The product decision for this phase targets Linux and Python 3.12+.
- Repository documentation says Python 3.6+ and specifically claims a PVM host ships Python 3.6.8 (`README.md:21–26`; `docs/ARCHITECTURE.md:27–29, 45–46`). This is a repository documentation claim only. The actual supported PVM OS, Python versions, glibc version, CPU architecture, filesystem mount policy, and installation permissions were not provided or queried.
- The discovery sandbox has Python 3.11.2 and no `python3.12`, `uv`, `pytest`, or `pyinstaller` on PATH. That sandbox is not the PVM target.
- Current runtime source uses the standard library. A future Textual/Pydantic/psutil deployment may include pure-Python modules and compiled extension modules.

## Runtime choices

| Approach | Benefits | Costs / risks | Assessment |
|---|---|---|---|
| Use host system Python | Small deployment; system security updates maintain interpreter | Cannot meet 3.12+ if PVM images remain on older Python; may require privileged OS changes; dependency isolation is poor | Do not assume this is available. Avoid changing system Python. |
| Install an isolated Python runtime in the application/user deployment | Can meet 3.12+ without replacing `/usr/bin/python`; explicit runtime lifecycle | Larger deployment; native library and glibc compatibility still applies; patch cadence and integrity must be owned; managed runtime may require a network or staged bundle | Viable only after target OS/runtime validation. `uv` can manage/install interpreters, but requiring the `uv` executable at runtime is not necessary. |
| PyInstaller one-directory bundle | Ships Python and Python dependencies together; no target Python install requirement; ordinary staged directory deployment | Linux binaries still link to host libc/system libraries; build on oldest supported Linux/glibc; extensions, data files, entry points, subprocess lookup and terminal behavior need packaging tests; larger bundle | **Recommended first deployment prototype**, conditional on supported PVM glibc/architecture. Keep `sbell` and `pvm-running-vms` as explicit host prerequisites, not bundled substitutes. |
| PyInstaller one-file bundle | Single artifact convenient to copy | Extracts bundled files at launch; temporary-directory execution/mount policy and startup overhead matter; more complex runtime diagnostics | Avoid as initial production default. Evaluate only if single-file transfer is a firm requirement. |
| Container | Strong dependency isolation and repeatable image | Requires container runtime, host integration and access to local PVM sockets/tools; may not be allowed or installed on appliance hosts | Do not select without PVM operational approval and a tested access model. |

PyInstaller documentation explicitly notes that GNU/Linux builds do not bundle glibc and advises building against the oldest GNU/Linux release intended for support. Its one-file mode extracts support files at runtime; temporary filesystem execution policy can prevent operation. See [PyInstaller GNU/Linux notes](https://pyinstaller.org/en/stable/usage.html#making-gnu-linux-apps-forward-compatible) and [one-file mode](https://pyinstaller.org/en/stable/operating-mode.html#how-the-one-file-program-works).

## Recommended runtime strategy

1. **Do not upgrade, replace, or depend on the system Python.** Keep application runtime separate from PVM's operating-system Python and components.
2. **First collect a target compatibility profile without changing the host:** PVM release, distribution/base release, architecture, glibc, available shell utilities, allowed installation paths, executable mount policy, and the minimum supported server cohort. Confirm whether Python 3.12+ is forbidden, absent, or merely not guaranteed.
3. **Prototype a Python 3.12+ PyInstaller one-directory build** on the oldest supported Linux build environment. Run it in a representative, non-production PVM test environment. Verify dynamic libraries, Textual terminal operation, Pydantic/psutil native modules if selected, PyInstaller data/hidden imports, access to local PVM tools, signals, permissions, and update/rollback.
4. **If PyInstaller cannot satisfy target compatibility or support policy**, compare shipping a privately managed standalone interpreter plus a locked application environment. This is not the same as installing into system Python; it still requires runtime patching, signing, and filesystem lifecycle decisions.
5. **Pin/lock the build inputs, but do not freeze exact dependency versions in this investigation.** Create reproducible artifacts per supported Linux architecture/runtime baseline and validate them on the actual target matrix.
6. **Keep `uv` a build/development tool** unless the selected deployment explicitly needs managed runtime installation. A production PVM host should not need `uv` merely to launch the packaged CLI.

This is a **conditional recommendation**, not a final deployment ADR. No target host was available to establish the compatibility baseline. PyInstaller cannot make a binary built against newer glibc run on older glibc just by bundling Python.

## Python/dependency compatibility evidence

On 2026-10-30, package metadata was queried from the public PyPI JSON API without installing packages. Reported `Requires-Python` ranges were:

| Package | Latest version returned by PyPI query | Declared `Requires-Python` |
|---|---:|---|
| textual | 8.2.8 | `>=3.9,<4.0` |
| rich | 15.0.0 | `>=3.9` |
| typer | 0.27.3 | `>=3.10` |
| pydantic | 2.14.2 | `>=3.10` |
| psutil | 7.2.2 | `>=3.6` |
| sqlalchemy | 2.1.6 | `>=3.11` |
| uv | 0.13.6 | `>=3.8` (PyPI wrapper metadata; standalone uv binary is also distributed) |
| pytest | 9.2.0 | `>=3.10` |
| pytest-asyncio | 1.4.1 | `>=3.10` |
| hypothesis | 6.170.14 | `>=3.11` |
| ruff | 0.17.3 | `>=3.7` (platform wheels also available) |
| pyright | 1.1.414 | `>=3.7` (Python wrapper; Node/runtime packaging must be verified for chosen install) |
| structlog | 26.1.0 | `>=3.10` |
| tenacity | 9.2.1 | `>=3.10` |
| platformdirs | 4.14.0 | `>=3.11` |
| pydantic-settings | 2.16.2 | `>=3.11` |
| alembic | 1.20.1 | `>=3.10` |
| httpx | 0.28.1 | `>=3.8` |
| pyinstaller | 6.22.3 | `>=3.8,<3.16` |

Source: PyPI project JSON endpoints, e.g. [`textual`](https://pypi.org/pypi/textual/json), [`pydantic`](https://pypi.org/pypi/pydantic/json), [`pyinstaller`](https://pypi.org/pypi/pyinstaller/json). Versions are a point-in-time registry observation, not tested combinations or a lockfile. Check release support, wheel availability for target architecture, and transitive dependency metadata before selecting exact pins.

## Open runtime questions

- What PVM distributions/releases and CPU architectures are supported?
- What glibc baseline and host kernel/libstdc++/system libraries exist across those systems?
- May a signed, self-contained application directory be copied to a PVM appliance? Which paths are writable and executable?
- Can the target reach package indexes, or must all artifacts be built and transferred offline?
- Who owns runtime and dependency security updates, signing, rollout, rollback, and incident response?
- Is PyInstaller acceptable to PVM vendor/support policy?

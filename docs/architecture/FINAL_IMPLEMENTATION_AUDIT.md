# Final Implementation Audit — AUD-01 through AUD-14

**Audit/update date:** 2026-10-30  
**Branch:** `arena/15ca46c8-plaivid-cli` (`active`)  
**Scope:** Remediation of the existing implementation audit, fake-based regression tests, documentation/ADR and OpenSpec reconciliation, and local validation.  
**Host safety:** No PVM host was contacted. No host command, lifecycle operation, `tests/smoke.py`, commit, or push was run.

## Executive summary

All 14 findings have a local disposition. Thirteen are **FIXED** in the active implementation and have regression coverage; AUD-04 is **BLOCKED** because the repository provides no evidenced safer `sbell` credential-input mechanism. The argv credential gate remains default-deny; explicitly opting in acknowledges exposure but does not mitigate it. Owner/security review is required before authenticated PVM validation.

The implementation deliberately does not invent PVM response semantics. Until evidence is supplied by the PVM owner, every response after lifecycle dispatch—including an XML `success` envelope with a zero process exit—is `OUTCOME_UNKNOWN`; bulk execution stops and the remainder is `NOT_STARTED`. This is a conservative local policy, not proof of target behavior. Target command, credential, permission, process-wrapper, and lifecycle semantics remain **PENDING MANUAL PVM VALIDATION**.

**Python requirement remains `>=3.12`.** This workspace has Python 3.11.2 only; `python3.12` is unavailable. Ruff, Pyright, fake-backed tests, coverage, wheel build, and a supplemental Python 3.11 wheel smoke were run, but none is claimed as Python 3.12 verification. The required Python 3.12+ install/smoke task remains unchecked in the OpenSpec Change. No system Python was replaced.

## AUD-01–AUD-14 dispositions

| Finding | Status | Remediation and regression evidence | Remaining boundary |
|---|---|---|---|
| AUD-01 — Unverified reply treated as acceptance | **FIXED** | `OperationCoordinator` no longer interprets status text or exit code as acceptance/completion. Every returned post-dispatch reply is unknown; a bulk plan stops and reports remaining targets `NOT_STARTED`. Fake positive-response test in `tests/unit/test_application_operations.py`; CLI exit/output assertions in `tests/unit/test_cli_and_tui.py`. | PVM response/acceptance/completion semantics: **PENDING MANUAL PVM VALIDATION**. |
| AUD-02 — Aggregate result hides higher-risk target outcomes | **FIXED** | Added `PARTIAL`, explicit aggregate precedence (unknown, accepted-unconfirmed, confirmed mixed partial, definite failure/rejection), and explicit CLI exit mapping. Aggregate matrix and CLI tests cover the new behavior. | `COMMAND_ACCEPTED_UNCONFIRMED` is representable but not inferred for current PVM replies. |
| AUD-03 — Infinite age bypasses freshness | **FIXED** | Reject non-finite and non-positive process timeouts, refresh interval, and configured inventory age. `tests/unit/test_config.py`, `tests/unit/test_process_runner.py`. |
| AUD-04 — Credential argv exposure | **BLOCKED** | Confirmed no repository-evidenced safer credential mechanism. No stdin, environment, descriptor, or alternate `sbell` contract was invented. Credential argv remains off by default; `PLAIVID_ALLOW_CREDENTIAL_ARGV` is an explicit risk acknowledgement, not protection. Existing security tests verify default denial before child execution. | Owner/security decision is required before authenticated PVM use. |
| AUD-05 — Truncated process output treated as complete | **FIXED** | Process-helper truncation produces partial quality; truncated Sball XML is rejected before parsing. Regressions in `tests/unit/test_pvm_adapter.py` and `tests/unit/test_sbell_client.py`. |
| AUD-06 — Partial enrichment creates false state conflicts | **FIXED** | `merge_inventory` distinguishes helper availability from completeness. Absence is negative evidence only for a complete result. Regressions in `tests/unit/test_domain_models.py` and operation eligibility tests. |
| AUD-07 — Confirmation hides freshness | **FIXED** | The TUI confirmation now shows source status, last-success timestamp, computed age, configured freshness bound, full target set, and exact action. Pilot test checks those values. |
| AUD-08 — Child receives ambient caller environment | **FIXED** | Default `ProcessRunner` environment allowlists `PATH`, `HOME`, `LANG`, and `LC_*`; an explicit runner environment remains available to trusted composition. A synthetic ambient-secret test confirms unrelated values are omitted. |
| AUD-09 — PVM metadata bypasses redaction | **FIXED** | Added pure domain redaction and applied it to CLI human/JSON and TUI names, detail, host/audit/error content. Dynamic PVM text widgets disable markup; table cells use Rich `Text`. Synthetic-secret regressions cover CLI and TUI. |
| AUD-10 — Timeout kills only direct child | **FIXED** | POSIX children start in isolated sessions; timeout/reader cleanup kills the process group, then reaps the child. A fake parent/grandchild test asserts the descendant cannot complete a delayed side effect. | Actual target `sudo`/PVM wrapper behavior: **PENDING MANUAL PVM VALIDATION**. |
| AUD-11 — Audit polled on generic refresh timer | **FIXED** | Generic refresh returns without polling Audit. Audit reads on tab entry or explicit refresh. Pilot test verifies no repeated database read across refresh intervals. |
| AUD-12 — Retired legacy implementation shipped | **FIXED** | `setup.py` explicitly selects supported packages and filters legacy root modules; distribution regression and wheel-content inspection confirm retired `actions/`, `commands/`, and root legacy modules are absent from the wheel. They remain checkout-only. |
| AUD-13 — Exclusive worker cancellation hides active operation | **FIXED** | Operation worker is non-exclusive; the TUI blocks duplicate operation submission and logout while an operation is active; the application coordinator closes admission and waits for the operation lane. Fake operation/TUI tests cover the guards and shutdown wait. |
| AUD-14 — ADR/planning records conflict | **FIXED** | ADR index and relevant ADRs now distinguish locally implemented behavior from owner/host evidence. Historical architecture proposal and OpenSpec design identify old planning text as historical; the existing Change/tasks and this report describe current state. |

## Changed files and areas

- **Runtime/security/operations:** `plaivid_cli/config.py`, `plaivid_cli/application/{collection,operations,services,session}.py`, `plaivid_cli/domain/{inventory,models,redaction}.py`, `plaivid_cli/infrastructure/{process,diagnostics}.py`, `plaivid_cli/infrastructure/pvm/{adapter,parsers,sbell}.py`, `plaivid_cli/{bootstrap,cli,tui}.py`, and `plaivid_cli/__main__.py`.
- **Packaging:** `pyproject.toml`, `setup.py`, `.gitignore`. The wheel declares `Requires-Python: >=3.12` and ships only the active runtime packages/modules.
- **Regression tests:** `tests/unit/test_{application_operations,cli_and_tui,config,distribution,domain_models,pvm_adapter,process_runner,sbell_client,session_lifecycle}.py` plus the existing fake/parser/architecture/audit tests and `tests/fixtures/`.
- **Operator/docs/ADRs:** `README.md`, `docs/ARCHITECTURE.md`, `docs/REFERENCE.md`, `docs/REAL_PVM_VALIDATION.md`, `docs/architecture/07-validated-architecture.md`, `docs/architecture/adr/README.md`, ADRs 0004, 0005, 0007, 0008, 0010, 0012, 0013, 0014, and this report.
- **Existing OpenSpec Change only:** `openspec/changes/implement-complete-plaivid-cli/` design, tasks, and applicable application-runtime, diagnostics/audit, PVM data, sessions/security, TUI, and VM-operations specs. No new Change was created.

## Verification performed

All commands ran in the repository workspace under Python 3.11.2 unless otherwise noted. `tests/smoke.py` was intentionally excluded and never executed.

| Check | Result |
|---|---|
| Unit/fake integration/Textual suite | `PYTHONPATH=. .venv/bin/python -m pytest -q --ignore=tests/smoke.py --cov=plaivid_cli --cov-report=term-missing --cov-report=xml:coverage.xml` — **96 passed**. |
| Coverage | **77%** active `plaivid_cli` coverage (2,382 statements; retired legacy files excluded by `pyproject.toml`). |
| Ruff | `PYTHONPATH=. .venv/bin/python -m ruff check .` — **passed**. `tests/smoke.py` is excluded from lint and was not run. |
| Pyright | `PYTHONPATH=. .venv/bin/python -m pyright` — **0 errors, 0 warnings, 0 informations**. |
| OpenSpec strict validation | `node /home/user/.npm/_npx/21a1280729add0a7/node_modules/@fission-ai/openspec/bin/openspec.js validate implement-complete-plaivid-cli --type change --strict` — **valid**. |
| Diff whitespace | `git diff --check` — **passed** for tracked diff. |
| Wheel build | `PYTHONPATH=. .venv/bin/python -m build --wheel` — **built** `dist/plaivid_cli-0.4.0-py3-none-any.whl`; metadata says `Requires-Python: >=3.12`; wheel inspection found 32 entries and no retired legacy packages/modules. |
| Supplemental wheel smoke | Installed that wheel into a clean temporary Python 3.11 venv using `--ignore-requires-python`; `plaivid --help` and legacy-module exclusion checks passed. This is only a Python 3.11 packaging smoke, **not** the required Python 3.12+ verification. The temporary venv was removed. |
| Python 3.12+ wheel install/smoke | **BLOCKED**: Python 3.12 is unavailable. No system interpreter was changed. OpenSpec tasks 1.1/7.3 remain unchecked for this required check. |
| Real-PVM checks | Not run. No host access or lifecycle operation occurred. |

## Decisions and remaining limits

1. **Credential transport:** the existing interface sends password XML/token arguments to a child process. No safe alternative is evidenced. Keep the default gate closed; explicit opt-in is not secure transport. Product/security owner must decide whether to provide verified supported input or accept the residual exposure before authenticated host validation.
2. **PVM outcome contract:** all post-dispatch responses are currently unknown; no retries occur. Owner/vendor evidence is needed before narrower acceptance/failure/completion mapping or bulk continuation is considered.
3. **Process cleanup contract:** POSIX fake process-group cleanup is locally tested. Do not generalize this to a target `sudo` wrapper without manual evidence.
4. **Platform/host support:** no Rocky Linux, Python 3.12, PVM/Sball version, host ABI, permissions, data schema, load, or vendor compatibility was verified.
5. **OpenSpec status:** local code/tests/docs and strict validation are done for this turn; wheel build and supplemental Python 3.11 smoke are recorded. Tasks that require Python 3.12+ remain unchecked. All host-dependent tasks remain **PENDING MANUAL PVM VALIDATION**; AUD-04 remains **BLOCKED** by the owner decision.

## Rocky Linux build/run commands (owner/operator only)

Use an already-approved Python 3.12+ interpreter on Rocky Linux. These commands use a project-local virtual environment and do not change system Python or install anything on a PVM host. `inventory` is PVM-dependent and must only be run by an authorized operator after the credential/security and manual-validation gates have been accepted.

```bash
cd /path/to/plaivid_cli
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip build
.venv/bin/python -m pip install '.[dev]'
.venv/bin/python -m pytest -q --ignore=tests/smoke.py
.venv/bin/python -m ruff check .
.venv/bin/python -m pyright
.venv/bin/python -m build --wheel
.venv/bin/python -m pip install --force-reinstall dist/plaivid_cli-0.4.0-py3-none-any.whl
.venv/bin/plaivid --help
# Only on an authorized PVM host after owner/security approval:
.venv/bin/plaivid inventory
```

**Disposition:** local remediation is ready for review. Authenticated PVM validation is not authorized by this report; first resolve the credential owner decision and follow the owner-run checklist in `docs/REAL_PVM_VALIDATION.md`. No commit or push was made.

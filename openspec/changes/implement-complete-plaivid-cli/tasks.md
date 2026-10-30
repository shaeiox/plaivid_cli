# Tasks

## 1. Foundation and execution boundary

- [ ] 1.1 Add Python package metadata, Python >=3.12 declaration, Textual runtime dependency, development test/lint/type extras, and CLI entry point; verify metadata builds and the entry point resolves in a temporary environment. Python 3.12 installation/smoke verification remains blocked by interpreter unavailability.
- [x] 1.2 Add typed immutable domain models, section/result/error categories, and pure operation policy; verify enums, UUID normalization, and policies with focused unit tests.
- [x] 1.3 Add validated configuration and one Bootstrap composition root with orderly shutdown; verify invalid configuration fails before any provider call and shutdown closes owned workers.
- [x] 1.4 Implement bounded argv-only child execution, timeout/output handling, redacted diagnostics, and child wait/reap; verify with fake executables for success, nonzero exit, timeout, output cap, and missing executable.
- [x] 1.5 Establish pytest fixtures, import-boundary checks, Ruff/Pyright config, and test commands; verify a clean test collection and expected layer-import constraints.

## 2. PVM adapters and coordinated data collection

- [x] 2.1 Move evidenced XML/table parsing into pure Infrastructure parsers and add illustrative fixtures clearly distinguished from target captures; verify valid, empty, malformed, duplicate, and missing-field cases.
- [x] 2.2 Implement local `sbell` and `pvm-running-vms` adapters for only existing operations; verify exact argv/XML request forms and responses with fake executables, never a live host.
- [x] 2.3 Implement independent defined-object and process-evidence records with canonical UUID correlation and partial-quality reporting; verify conflicts, helper-only rows, duplicates, invalid rows, and source failures.
- [x] 2.4 Implement one CollectionCoordinator with single-flight, bounded pending intent, per-section freshness, immutable publication, last-good retention, and generation rejection; verify concurrent duplicate requests coalesce and failed enrichment cannot clear inventory.
- [x] 2.5 Implement host/Sball/metrics/storage/network parsing and on-demand detail/tap access; verify unavailable fields stay unavailable and `quorate` is not converted into cluster-health claims.

## 3. Application services and CLI

- [x] 3.1 Implement application read use cases, strict whole-set selector resolution, stable UUID identity, and optional read-only audit service; verify selector ambiguity/partial failures and audit unavailability with fakes.
- [x] 3.2 Implement argparse one-shot inventory, status, detail, overview, diagnostics/audit, help, version, and configuration commands; verify each read is bounded to one request and help/version invoke no provider.
- [x] 3.3 Implement human and JSON serialization plus stable exit mapping for success, failure, rejected, partial, and unknown outcomes; verify representative output and exit codes in subprocess CLI tests.

## 4. Textual TUI

- [x] 4.1 Implement TTY-gated Textual bootstrap, dashboard, inventory, host/cluster monitoring, detail, audit/diagnostic screens, and keyboard navigation; verify the app mounts and views navigate under Textual Pilot.
- [x] 4.2 Move blocking use cases to bounded workers and route visible refresh demand through CollectionCoordinator; verify slow fake calls do not block navigation and leaving live views stops periodic requests.
- [x] 4.3 Implement freshness/loading/error presentation and stable UUID selection/focus retention; verify refresh and sort preserve the same selected UUID in Pilot tests.

## 5. VM lifecycle operations

- [x] 5.1 Implement immutable operation plans, action-specific risk/confirmation rules, inventory-generation binding, and fail-closed freshness/authorization gates; verify changed generations, partial inventories, and unset destructive-bulk age reject before dispatch.
- [x] 5.2 Implement OperationCoordinator serialization and the six repository-evidenced action parameter forms; verify exact fake-provider calls and target order for each action.
- [x] 5.3 Implement per-target and aggregate states, dispatch/acceptance/completion distinction, stop-on-first-failure-or-unknown, and `NOT_STARTED` remainder reporting; verify unknown precedence, accepted-unconfirmed aggregation, and no automatic retries.
- [x] 5.4 Wire action confirmation to TUI and explicit non-TTY approval to CLI; verify approval binds exact action/UUIDs/current generation and that TTY absence never implies approval.
- [x] 5.5 Implement mutation/read generation barriers and post-operation stale marking; verify pre-mutation reads cannot overwrite newer affected-UUID results.

## 6. Security and reliability

- [x] 6.1 Replace session auto-eviction with explicit session-cap reporting; implement private atomic token caching and argv-risk acknowledgement; verify file modes, no password persistence, no session deletion, and blocked requests without acknowledgement.
- [x] 6.2 Add safe structured diagnostics and redaction tests across errors, logs, CLI, and TUI; verify synthetic passwords/tokens never appear in captured output.
- [x] 6.3 Add failure-path integration tests for permissions, nonzero exit, malformed XML/table, timeout, cancellation, shutdown, partial collection, and unknown mutation result; verify no live PVM dependency.

## 7. Packaging, operator documentation, and full verification

- [x] 7.1 Create `docs/REAL_PVM_VALIDATION.md` with prerequisites, exact owner-run manual scenarios, expected outcomes, failure indicators, evidence collection, uncertainties, and all host tests marked `PENDING MANUAL PVM VALIDATION`; verify no test is executed by this implementation.
- [x] 7.2 Rewrite README usage, architecture, requirements, security, and deployment instructions to match the implemented CLI/TUI; verify documented commands match `plaivid --help` and do not claim real-host validation.
- [ ] 7.3 Build a wheel and install/smoke-test it in a temporary isolated environment; verify package entry point, removal/rollback documentation, and no system-Python modification. A wheel was built and an isolated Python 3.11 supplemental install/help/package-exclusion smoke test passed with `--ignore-requires-python`; required Python 3.12+ install/smoke validation remains blocked because Python 3.12 is unavailable.
- [ ] 7.4 Run the complete unit, integration, CLI, Textual, lint, type, coverage, OpenSpec, package, secret-scan, and diff-review checks; record exact commands/results and keep all real-PVM validation pending owner execution. Reopen until every local check is run and recorded.

## Audit remediation (AUD-01–AUD-14)

Statuses refer to local code/tests only; they do not imply PVM-host verification.

| Finding | Status | Evidence / outstanding boundary |
|---|---|---|
| AUD-01 | FIXED | Post-dispatch replies map conservatively to `OUTCOME_UNKNOWN`; fake-provider regression covers positive-looking reply. PVM response contract remains PENDING MANUAL PVM VALIDATION. |
| AUD-02 | FIXED | Aggregate precedence includes unknown/accepted-unconfirmed/partial; CLI exit mapping is explicit and tested. |
| AUD-03 | FIXED | Non-finite and non-positive timeout/refresh/inventory-age values reject before use. |
| AUD-04 | BLOCKED | No repository-evidenced safer `sbell` credential channel exists. Keep default-deny; explicit argv acknowledgement is not a mitigation. Security/owner decision is required before authenticated PVM use. |
| AUD-05 | FIXED | Truncated process listing is partial and truncated Sball XML is rejected; regression tests added. |
| AUD-06 | FIXED | Missing process rows are negative evidence only for a complete process result; partial-enrichment regression covers it. |
| AUD-07 | FIXED | Confirmation shows inventory status, age, and freshness bound; Textual confirmation tests retained. |
| AUD-08 | FIXED | Default child environment allowlist is tested against ambient secret inheritance. |
| AUD-09 | FIXED | Pure redaction is applied to CLI JSON/human and TUI PVM-derived content; synthetic-secret regressions added. |
| AUD-10 | FIXED | POSIX session/process-group cleanup and grandchild regression test added. Target `sudo`/PVM wrapper behavior remains PENDING MANUAL PVM VALIDATION. |
| AUD-11 | FIXED | Audit is queried on tab entry/explicit refresh, not by the generic interval; TUI call-count regression added. |
| AUD-12 | FIXED | Setuptools excludes retired legacy packages/modules; distribution boundary test added. |
| AUD-13 | FIXED | Operation workers are non-exclusive and duplicate submission/logout are blocked while active; fake Textual guard regression added. |
| AUD-14 | FIXED | ADR index, implementation status, operation semantics, and historical planning scope reconciled with the existing Change and audit report. |

## Workflow follow-up

- Archive this single OpenSpec Change only after all implementation tasks are verified and the project owner has reviewed the pending real-PVM validation plan; host validation remains owner-run and is not a prerequisite for claiming local tests passed.

# Design

## Context

See `proposal.md` for motivation and the capability contracts in `specs/`. The first sentences of the proposal describe the repository before implementation and are historical. The current active runtime, local verification, and remaining audit findings are recorded in `docs/ARCHITECTURE.md` and `docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md`. No target-host output has been captured in this environment.

## Goals / Non-Goals

**Goals:** implement the complete local product within the established architecture; make core behavior testable with fake ports/executables; preserve partial source evidence and uncertain mutation results; keep UI responsive and non-TTY behavior bounded; prepare an installable Linux package and owner-run host-validation plan.

**Non-Goals:** accessing any PVM host; claiming vendor/host contracts are verified; adding PVM commands not present in repository source; remote collection; session-cap eviction; an application database; default `/proc` scans; multi-provider plugins, event buses, scheduler package, or a replaceable snapshot store; a custom terminal renderer.

## Decisions

### Package boundaries and composition

```text
plaivid_cli/
  __main__.py, bootstrap.py, config.py
  domain/                 immutable facts, errors/outcomes, pure action policies
  application/            ports.py, services.py, collection.py, operations.py
  infrastructure/         diagnostics.py; pvm/process.py, sbell.py, parsers.py,
                          adapter.py, audit.py, session.py
  presentation/           cli.py, tui.py, screens.py, widgets.py

tests/{unit,integration,ui,fixtures}/
```

Keep small responsibilities together when splitting them would add indirection. There is one `application/` package, one `CollectionCoordinator`, one `OperationCoordinator`, and `bootstrap.py` is the only composition root. `Application` depends on narrow ports; Infrastructure implements them; Presentation calls application services and cannot call PVM or parse XML. Retired `commands/`, `actions/`, and root-level legacy runtime files remain in the source checkout but are excluded from the built distribution; they are not supported entry points.

`Bootstrap` validates configuration, constructs one provider and coordinator of each kind, selects CLI or TUI from explicit arguments/TTY state, and closes the same graph in `finally`. Domain remains standard-library-only. Dependency direction is enforced with tests/import inspection.

### Domain and application results

Use typed, immutable dataclasses/enums for `VM`, source observations, section state, host metrics, inventory, operation request/approval/result, and errors. Keep source value/time/status distinct rather than normalizing process presence into object state. A section distinguishes never-collected, valid empty, current, partial, stale, failed-without-value, and unsupported. A successful empty response is not an error. Error text is sanitized at presentation/log boundaries; raw credentials/payloads are not part of model reprs.

Application services are synchronous use-case APIs usable from argparse and Textual worker threads. Ports describe only supported local behavior: login/identity/logout, one `user/objects` batch, selected UUID detail, `pvm-running-vms`, `sball/show`, `monitoring/metrics`, existing six `vm/*` actions, and optional read-only audit access. Parameter shapes are based on existing source and repository references; adapter-specific fixtures do not assert that an untested target has the same schema.

### Infrastructure and child processes

`ProcessRunner` accepts trusted argv lists and finite deadlines, never a shell string. It bounds retained stdout/stderr, continuously drains pipes, uses a minimal default child environment, and waits/reaps the child. On POSIX it starts an isolated session and kills its process group on timeout/reader cleanup; a fake descendant test validates this implementation behavior but does not prove target `sudo`/PVM wrapper semantics. Truncation propagates to parsers. Tests use fake executables only. A timeout after mutation dispatch is uncertain; the runner never retries.

`SbellAdapter` preserves the existing local invocation order and parses the existing XML envelope with bounded input and explicit process/protocol/response failures. It will not interpret `Response.status`, action IDs, errno, or exit status as proof of lifecycle completion unless owner-supplied evidence validates that mapping. `RunningVmsAdapter` parses recognized table rows; malformed/duplicate rows produce partial quality status rather than false empty success. It does not inspect `/proc`.

XML builders use `ElementTree` for text escaping and preserve the exact action structures already present in the repository for start and the five simple UUID actions. Unknown structures are not generated. Parsers accept only evidenced fields; absent fields remain unavailable.

### Collection and snapshots

`CollectionCoordinator` owns read cadence/demand, single-flight admission, logical request coalescing, bounded pending refresh intent, per-section last-good state, and publication generation. One bounded read worker lane performs blocking adapters off the Textual event loop. The CLI asks once and exits; only an active visible live TUI view schedules refresh requests. Freshness thresholds are configuration/product policy and default conservatively; action eligibility fails closed when the required threshold is unset.

The all-VM `user/objects` result and process list are independent facts correlated by strict UUID parsing. Object inventory can publish when enrichment fails. Duplicate canonical UUIDs are non-actionable; malformed rows are excluded with partial quality; helper-only rows remain unmatched process evidence. Host metrics and Sball status are independent sections with source times. Sball `quorate` is displayed as “Sball reports Quorate,” never as full membership or universal health. Selected detail and optional tap/audit sections are on demand. Metric history is bounded in memory only.

On a mutation, `OperationCoordinator` establishes an affected-UUID generation barrier. Pre-barrier reads cannot publish over the new generation; affected sections remain stale until a later supported collection. Infrastructure calls remain serialized until target-owner evidence approves increased PVM concurrency.

### VM operations

`OperationCoordinator` resolves the entire requested set against one inventory generation before dispatch. It rejects duplicate, ambiguous, invalid, partial, or stale plans. Confirmations are immutable approval records keyed to action, ordered canonical UUIDs, and inventory generation/freshness. TUI displays the complete target list; non-TTY mutation requires an explicit operator-provided approval mechanism and argv-risk acknowledgement, never implicit consent.

Risk policy follows ADR 0012: Start/Resume need explicit single-target intent and bulk approval; Stop/Reset/Pause require action-specific confirmation; Kill uses a distinct strong confirmation. Until a numeric maximum age is set, destructive bulk operations are rejected. Action applicability is advisory only where PVM semantics are not verified; the app must not claim authorization.

Dispatch is sequential and mutations are serialized. A definite failure, rejection, or unknown result halts the bulk plan; all later targets are `NOT_STARTED`. Because the repository has no verified acceptance contract, every returned reply after dispatch—including a positive-looking status—is `OUTCOME_UNKNOWN` and stops bulk processing. `COMMAND_ACCEPTED_UNCONFIRMED` is reserved for a future mapping supported by owner evidence. Only a verified response/readback contract may yield per-target `SUCCEEDED`. Aggregate unknown takes precedence; unverified lifecycle outcomes use exit code 4 following ADR 0013. An observed desired state does not claim command causality.

### CLI and TUI

Use Python `argparse` for the stable explicit CLI to avoid an extra runtime dependency. Expose `list`, `status`, `show`, `overview`, `log`, and the six actions, with human output by default and JSON where meaningful. `help`, `version`, and config checks never collect PVM data. One-shot read commands collect once and terminate. Exit categories are 0 success, 1 definite failure, 2 rejected, 3 partial, and 4 unknown.

Use Textual for the interactive dashboard and inventory/monitoring/detail/diagnostic screens. The framework owns differential terminal rendering. UI callbacks submit use cases to bounded workers and receive typed results on the UI thread. Stable UUID row keys preserve selection/focus across sorting and refresh. Refresh timers request CollectionCoordinator work only while the live view is active. Confirmation modals display the immutable plan, full target set, and freshness; widgets do not own provider workers or collection policy. TUI starts only with TTY input and output; otherwise the CLI path is used.

### Sessions, diagnostics, and audit

Retain the existing PVM login/whoami/logout command forms only. Remove errno-185 automatic session listing/deletion. Passwords are never persisted. Session tokens, if cached, use atomic owner-only storage; cache failures remain visible but do not print values. Since both passwords and tokens currently appear in child argv, every credentialed request is blocked unless the operator explicitly acknowledges the exposure; this is not a claim of safety, and release remains gated on PVM-supported input or formal security acceptance. No stdin/env/fd credential mode is invented. No auto-logout occurs during shutdown.

Diagnostics use stdlib logging with an allowlist of operation id, category, source, elapsed time, and safe exit/errno metadata. Never log argv, raw XML, token, password, or full PVM output. Optional audit uses SQLite read-only URI/query limits and reports schema/permission failures without affecting other features.

### Dependencies, tests, and packaging

Runtime: Python `>=3.12`; Textual as the only new UI dependency (Rich is provided by Textual). CLI and data structures use stdlib argparse/dataclasses/ElementTree/sqlite3. Development extras include pytest, pytest-cov, Ruff, Pyright, and optional build tooling. Avoid Pydantic/ORM/database/runtime process libraries absent a concrete need.

Unit tests cover pure policies/parsers. Application tests use fake ports and clocks. Integration tests put small executable fakes named `sbell` and `pvm-running-vms` at temporary paths, assert exact argv and output, and never connect to PVM. Textual Pilot tests verify navigation, stale/loading/error states, confirmation binding, and no hidden non-TTY polling. Package tests build and install a wheel into a temporary virtual environment; PyInstaller remains optional unless it builds and smoke-tests reliably here. Python 3.11 is the available local interpreter; declare/target 3.12+ and report local compatibility checks accurately rather than claiming a 3.12 host run.

## Risks / Trade-offs

- [Credential/token argv exposure] → Block credentialed requests without explicit operator acknowledgement, redact all diagnostics, and keep real-host/release validation pending until a supported channel is verified or the risk is formally accepted.
- [PVM completion semantics are unknown] → Preserve accepted-unconfirmed/unknown states; do not retry; require owner captures before mapping responses to success/failure.
- [Host/ABI and Textual scale are untested] → Test only the available build/runtime environment and provide owner validation steps; do not claim target compatibility.
- [Old code includes implicit session eviction, broad exception suppression, and unsafe bulk continuation] → Replace rather than wrap those pathways; regression-test fail-closed behavior.
- [Some historical fields/query forms may not exist on supported builds] → Keep parser/adapters narrow, show unavailable/partial values, and mark affected manual checks pending.

## Migration Plan

1. Add packaging and test scaffolding without changing behavior; capture legacy behavior in tests and fixture examples.
2. Implement domain/ports/infrastructure and collection/application services behind fakes.
3. Replace entry point with Bootstrap and CLI, then Textual views, reusing parsers only after they pass fixtures.
4. Replace actions with OperationCoordinator, mandatory safety gates, and explicit outcomes; remove obsolete registry/orchestrator/custom terminal engine.
5. Build/install/test package locally; update operator docs and create `docs/REAL_PVM_VALIDATION.md` with every real-host test pending.
6. Rollback is to the previous package/source revision. No PVM configuration or durable application data migration exists.

## Open Questions

None that change this design. PVM command/schema/credential/completion semantics, host distribution/ABI, permissions, measured overhead, and deployment acceptability are external validation gates assigned to the project owner; the application behavior when evidence is absent is defined above.

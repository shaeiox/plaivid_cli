# Plaivid CLI/TUI architecture

This describes the current implementation, not the earlier dynamic command/action plugin design. The application is Linux-local and calls only the configured local `sbell` and `pvm-running-vms` programs. It does not use SSH or an application-owned telemetry database. The retired implementation—including the former `actions/`, `commands/`, and root-level runtime modules—is grouped under `plaivid_cli/legacy/` for historical reference; the supported runtime does not route through it, it is excluded from release packages, and it is excluded from active Ruff/Pyright checks rather than mechanically rewritten. Active CLI and TUI front ends live under `plaivid_cli/presentation/`; application, domain, infrastructure, and PvM integrations each have their own package directories.

The active multi-file responsibilities use focused packages: `presentation/cli/` separates parsing, dispatch, read handlers, operation handling, and serialization. The Textual frontend has an app shell plus independent entry points under `presentation/tui/pages/overview/`, `virtual_machines/`, and `virtual_desktops/`; each page owns its composition and page-specific components. Reusable widgets such as cards, inventory toolbars, and checkable tables live in `presentation/tui/components/`. Overview telemetry text formatting is pure and grouped by concern in `presentation/overview_metrics/`, while snapshot-to-display assembly lives alongside the Overview page in `presentation/tui/pages/overview/presenter.py`; page components only render supplied values and callbacks, never invoke infrastructure. `presentation/charts/` separates geometry, rendering, and the Textual widget. `application/collection/` contains the serialized coordinator, source reader, freshness policy, and last-good publisher; `application/operations/` separates lifecycle planning, dispatch, and result aggregation. Domain value groups live in `domain/models/`, while `infrastructure/pvm/adapter/` and `infrastructure/pvm/parsers/` isolate PVM requests, gateway behavior, and response parsing. TUI code imports page controllers, presenters, and components from their canonical package paths; obsolete root-level page shims and formatter facades have been removed. File size is treated as a maintainability signal, not a hard limit; active modules are split by responsibility and cohesion. The retired `legacy/` archive remains excluded from active architecture checks.

## Runtime boundaries

```text
                   ┌──────────────────┐
                   │ argparse CLI     │
                   │ Textual TUI      │
                   └────────┬─────────┘
                            │
                  ┌─────────▼──────────┐
                  │ Bootstrap          │  one composition root
                  └─────────┬──────────┘
                            │
             ┌──────────────▼─────────────┐
             │ PlaividApplication         │
             │ SessionManager              │
             │ OperationCoordinator        │
             │ CollectionCoordinator       │
             └──────────────┬─────────────┘
                            │ narrow protocols
             ┌──────────────▼─────────────┐
             │ LocalPvmAdapter             │
             │ ReadOnlyAuditAdapter        │
             │ pure PVM/XML parsers        │
             │ bounded ProcessRunner       │
             └──────────────┬─────────────┘
                            │ argv only; no shell
                 local sbell / pvm-running-vms
```

- `domain/` owns immutable PVM facts and evidence, result/section status, typed errors, operation outcomes, and pure risk policy. Defined-object state and local process observations are intentionally separate.
- `application/ports.py` defines the narrow `PvmGateway` and `AuditGateway` interfaces.
- `application/collection.py` owns one local read executor, request coalescing, one bounded pending intent, independent last-good sections, freshness clocks, and mutation generation barriers. Reads requested during a mutation wait until the barrier lifts. A pre-mutation read cannot publish over newer state.
- `application/services.py` provides stable UUID/name/prefix/index and group-selector resolution, detail/host/inventory reads, and optional audit queries.
- `application/operations/` creates immutable freshness-checked `OperationPlan` values, serializes operation groups, validates current object evidence, and records per-target/aggregate states. VM and Desktop targets dispatch through a bounded rolling pool (`PLAIVID_MAX_CONCURRENCY`, default `3`) under one `begin_mutation`/`end_mutation` barrier; result tuples preserve planned UUID order. PVM `status=failed` replies retain errno/message. A dispatched non-session error with a healthy daemon is isolated to its target; explicit session/daemon failures stop new submissions, in-flight calls settle, and never-dispatched targets become `NOT_STARTED`. No automatic retry occurs.
- `application/session.py` validates/resumes a cached session, performs explicit login only under the argv-risk gate, and atomically stores tokens in a private owner-controlled directory/file. It rejects symlinked/unsafe cache paths, never saves passwords, evicts another session, or guesses a credential transport.
- `infrastructure/process.py` uses argv without a shell, bounded output/deadlines, an allowlisted default child environment, POSIX process-session isolation, and process-group cleanup on timeout. Fake descendant cleanup is tested; target `sudo`/PVM wrapper behavior remains **PENDING MANUAL PVM VALIDATION**. Diagnostics avoid raw argv/output and redact common secret forms.
- `infrastructure/pvm/adapter.py` adapts only repository-evidenced local PVM commands. `parsers.py` are pure and report missing, malformed, conflicting, and unavailable values without manufacturing healthy defaults.
- `infrastructure/audit.py` uses SQLite read-only URI mode, bounded queries, and schema checks.
- `presentation/cli.py` provides one-shot reads, six lifecycle commands, stable exit categories, and JSON representations. Help/version do not create a runtime or invoke a provider.
- `presentation/tui.py` presents Overview (default) and Virtual Machines as two primary Textual pages, with secondary on-demand read-only Audit access. Blocking application operations use Textual workers. One active-view timer controls demand; Overview local samples default to 3s, Host status (`sball show`) defaults to 2s (`PLAIVID_HOST_STATUS_INTERVAL`), and the batched PVM dashboard/inventory cadence is >=18s. VM selection is retained by UUID; unchanged table rows and cards are updated without clearing the screen. `application/overview.py` owns due/health/history state; `presentation/overview.py` formats snapshots but never calls a provider. The 1–60s UI control adjusts Overview local cadence only and does not change operation freshness policy.
- `infrastructure/local_monitor.py` reads the local machine's `/proc` and physical NIC sysfs counters; `infrastructure/pvm/overview.py` parses only specified dashboard identity/raw RAM paths and intentionally rejects an unverified NIC-list schema. These are *not* verified deployed schemas. Top-VM metric units and individual VDI inventory are not captured in the repository and remain N/A until owner validation. No Container dashboard collection exists. `docs/MONITORING_DASHBOARD.md` lists the acceptance gates.

## Read model and source truth

Object records originate from the batched object query; process evidence originates from the existing local `pvm-running-vms` helper. They are correlated by canonical UUID. A process-only row is not silently treated as a defined PVM object, and missing monitoring fields remain unavailable rather than zero. A disagreement remains visible and blocks mutation of that record.

Sball status retains the literal `sball_state` field. In particular, `quorate` means the Sball-reported value is Quorate; the application does not promote it into a claim that every member or service is healthy.

Inventory, host status, host metrics, local-host metrics, PVM dashboard, physical NIC discovery/counters, detail, and tap mapping are separate collection sections. Errors in one section retain its own last-good value/status and do not erase another section. Displaying last-good data never changes its stale/unavailable label.

## Operation admission and uncertainty

A mutation binds an action and ordered canonical UUID set to the displayed inventory generation. Single-target admission requires a current object section, an unambiguous current record, and freshness within the configured age (or a short single-target default derived from the refresh interval). Bulk requires a configured `PLAIVID_MAX_INVENTORY_AGE_SECONDS`, complete inventory, and a full resolved UUID set. No action confirmation is required; the current generation is checked internally at dispatch.

Targets dispatch through the configured bounded worker window; final outcomes remain in the planned UUID order. A documented `status=success` reply is represented as `SUCCEEDED` (command acceptance, not proof of guest completion); `status=failed` is `FAILED` with errno/message; exceptions and unrecognised statuses after dispatch remain `OUTCOME_UNKNOWN`. With a healthy daemon, non-session errors including target disk/storage errors do not block scheduling sibling targets. Explicit session/daemon errors stop new submissions, allow in-flight calls to settle, and mark only never-dispatched targets `NOT_STARTED`. A local failure proven before child launch is distinct. No automatic retry or final-state claim is made. `COMMAND_ACCEPTED_UNCONFIRMED` is retained as a domain category and is not produced by the current mapping.

## Security boundaries

The existing `sbell` interface places username/password XML or session token in command arguments. This exposure has not been verified safe. `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` is a default-deny operator acknowledgement, not a mitigation. The implementation does not invent stdin, environment, descriptor, file, SSH, or remote alternatives. See `docs/REAL_PVM_VALIDATION.md` for owner-run host verification; all such items remain **PENDING MANUAL PVM VALIDATION**.

## Test strategy and contract status

Unit and integration tests use synthetic XML/text, fake gateways, fake child runners, temporary SQLite files, and Textual Pilot. These validate local logic only. No PVM host or production system has been contacted. The exact request/response contract, credential argv exposure in the target environment, lifecycle acceptance/completion behavior, metric-field availability, and target platform permissions remain subject to the owner-run checklist and are **PENDING MANUAL PVM VALIDATION**.

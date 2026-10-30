# Plaivid CLI/TUI architecture

This describes the current implementation, not the earlier dynamic command/action plugin design. The application is Linux-local and calls only the configured local `sbell` and `pvm-running-vms` programs. It does not use SSH or an application-owned telemetry database. Legacy `actions/`, `commands/`, and root-level runtime modules remain in the checkout for historical reference; the new console and module entry points do not route through them, and they are excluded from active Ruff/Pyright checks rather than mechanically rewritten.

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
- `application/operations.py` creates immutable freshness-checked `OperationPlan` values, serializes lifecycle submissions, validates current object evidence and approval, records per-target and aggregate states, marks inventory stale, and requests reconciliation. No PVM acceptance/completion contract is verified: every response after dispatch is `OUTCOME_UNKNOWN`, including a positive-looking envelope. Bulk stops and marks remaining targets `NOT_STARTED`; no automatic retry occurs.
- `application/session.py` validates/resumes a cached session, performs explicit login only under the argv-risk gate, and atomically stores tokens in a private owner-controlled directory/file. It rejects symlinked/unsafe cache paths, never saves passwords, evicts another session, or guesses a credential transport.
- `infrastructure/process.py` uses argv without a shell, bounded output/deadlines, an allowlisted default child environment, POSIX process-session isolation, and process-group cleanup on timeout. Fake descendant cleanup is tested; target `sudo`/PVM wrapper behavior remains **PENDING MANUAL PVM VALIDATION**. Diagnostics avoid raw argv/output and redact common secret forms.
- `infrastructure/pvm/adapter.py` adapts only repository-evidenced local PVM commands. `parsers.py` are pure and report missing, malformed, conflicting, and unavailable values without manufacturing healthy defaults.
- `infrastructure/audit.py` uses SQLite read-only URI mode, bounded queries, and schema checks.
- `cli.py` provides one-shot reads, six lifecycle commands, stable exit categories, and JSON representations. Help/version do not create a runtime or invoke a provider.
- `tui.py` uses Textual for rendering and widgets. Blocking application operations use Textual workers. Fleet/Host live views request periodic collection; Audit reads on tab entry or explicit refresh only. VM selection is retained by UUID.

## Read model and source truth

Object records originate from the batched object query; process evidence originates from the existing local `pvm-running-vms` helper. They are correlated by canonical UUID. A process-only row is not silently treated as a defined PVM object, and missing monitoring fields remain unavailable rather than zero. A disagreement remains visible and blocks mutation of that record.

Sball status retains the literal `sball_state` field. In particular, `quorate` means the Sball-reported value is Quorate; the application does not promote it into a claim that every member or service is healthy.

Inventory, host status, host metrics, detail, and tap mapping are separate collection sections. Errors in one section retain its own last-good value/status and do not erase another section. Displaying last-good data never changes its stale/unavailable label.

## Operation admission and uncertainty

A mutation binds an action and ordered canonical UUID set to the displayed inventory generation. Single-target admission requires a current object section, an unambiguous current record, and freshness within the configured age (or a short single-target default derived from the refresh interval). Bulk requires a configured `PLAIVID_MAX_INVENTORY_AGE_SECONDS`, complete inventory, and exact approval. The confirmation phrase is `ACTION UUID[,UUID...]`; the current generation is checked internally at dispatch.

Targets dispatch sequentially in the resolved order. With no verified acceptance contract, every reply or exception after dispatch is `OUTCOME_UNKNOWN`; this stops bulk dispatch and marks all remaining entries `NOT_STARTED`. A local failure proven before child launch is distinct. No automatic retry or final-state claim is made. `COMMAND_ACCEPTED_UNCONFIRMED` is retained as a domain category but is not inferred from the current PVM response text.

## Security boundaries

The existing `sbell` interface places username/password XML or session token in command arguments. This exposure has not been verified safe. `PLAIVID_ALLOW_CREDENTIAL_ARGV=1` is a default-deny operator acknowledgement, not a mitigation. The implementation does not invent stdin, environment, descriptor, file, SSH, or remote alternatives. See `docs/REAL_PVM_VALIDATION.md` for owner-run host verification; all such items remain **PENDING MANUAL PVM VALIDATION**.

## Test strategy and contract status

Unit and integration tests use synthetic XML/text, fake gateways, fake child runners, temporary SQLite files, and Textual Pilot. These validate local logic only. No PVM host or production system has been contacted. The exact request/response contract, credential argv exposure in the target environment, lifecycle acceptance/completion behavior, metric-field availability, and target platform permissions remain subject to the owner-run checklist and are **PENDING MANUAL PVM VALIDATION**.

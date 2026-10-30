# ADR 0013 — Error Taxonomy and Operation Outcomes

- **Status:** Proposed
- **Date:** 2026-10-30
- **Decision owner:** Application architecture owner; operations/support owner approves user-visible diagnostics and logging.

## Context and evidence

- **Repository fact:** transport launch/timeout/parse problems raise `TransportError`; PVM XML failures are a separate `Response.ok == False` path (`transport.py:27–63, 66–107`). Callers sometimes suppress errors, turn them into dictionaries, or reduce bulk failures to VM names.
- **Repository fact:** application state currently cannot distinguish empty data, first-load failure, stale last-good data, unsupported fields, and partial collection consistently.
- **Repository fact:** bulk operation catches exceptions and drops exception details (`orchestrator.py:157–176`).

## Decision proposal

Represent failures and outcomes as typed values at each boundary. Do not use one undifferentiated string/exception for transport, collection, application policy and mutation outcomes.

### Error categories

At minimum distinguish:

1. **Configuration/executable:** invalid command configuration, executable not found, permission/privilege setup failure.
2. **Process lifecycle:** spawn failure, timeout, cancellation requested, signal/exit failure, child cleanup failure.
3. **Protocol/parse:** empty/unexpected output, malformed XML, invalid/missing required field, unsupported schema/format.
4. **PVM response:** PVM errno/status with safe module/command context; retain errno/action ID where available without exposing secrets/raw payload.
5. **Authorization/session:** missing/expired token, denied command, login failure, session cap/recovery failure.
6. **Collection quality:** unavailable, partial, stale, unsupported, malformed, and valid-empty data as distinct states (section representation owned by ADR 0005).
7. **Application policy/input:** unknown/ambiguous selector, incomplete target resolution, invalid action state, confirmation declined, policy denied.
8. **Presentation/operation lifecycle:** worker failure, user cancellation, shutdown, and operation outcome unknown after dispatch.

Exact enum names and mapping of documented errno values remain open until target behavior is confirmed.

### Operation outcomes

For each requested operation and target, provide an outcome at least from: `succeeded`, `failed` (definite), `not_started`/`rejected`, `cancelled_before_dispatch`, and `outcome_unknown` (may have executed). A bulk result is a collection of per-target outcomes plus an overall `succeeded`, `failed`, or `partial` summary; it must not hide error causes. Do not equate subprocess nonzero status with a PVM response failure until the real sbell contract is verified.

### User and diagnostic channels

- User display is concise, actionable, and includes freshness/partial status where relevant.
- Diagnostics include safe operation/correlation ID, source/category, duration, PVM errno/exit status as appropriate, and redacted context.
- Never log password, token, login XML containing secrets, full unreviewed payloads, or sensitive command arguments.
- Preserve original error chaining internally for debugging, but sanitize at the user/log boundary.
- Retry policy is not owned here: classification informs decisions; ADR 0007 forbids blind mutation retries and ADR 0014 owns collection scheduling/backoff.

## Consequences

- UI and tests can distinguish failure from absence and partial success.
- The typed model requires explicit mapping and can expose current inconsistency; mappings need fixtures and target verification.
- Unclear or absent PVM response/exit semantics remain visible as unknown rather than guessed.

## Validation required

Fake executable cases for all process/parse paths; redacted PVM response fixtures; test mixed bulk outcomes, unknown mutation timeout, cancellation before/after dispatch, stale/empty/unsupported collection values, and log redaction. Confirm supported PVM errno, exit-code and action-ID semantics on a controlled target.

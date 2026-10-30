# ADR 0005 — Section Snapshots and In-Memory State Store

- **Status:** Proposed
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Application/domain architecture owner.

## Context and evidence

- **Repository fact:** `App` holds mutable host and VM fields; there are no per-source timestamps, last-good values, or explicit partial-collection states (`orchestrator.py:34–43, 68–79`).
- **Repository fact:** host, metrics, inventory and detail results use unrelated dictionaries/objects. Some failed inventory refreshes replace current data with `[]`.
- No app-owned database or persisted monitoring history requirement has been confirmed (persistence distinction: ADR 0008).

## Decision

Model collected state as independently managed **sections**—at minimum local host/status, host metrics, VM inventory, and on-demand VM detail—with their own lifecycle. A published immutable snapshot can aggregate sections for a screen, but it must not collapse their independent collection outcomes.

Each section envelope records:

- `status`: never-collected, current, stale, failed-without-value, or unsupported (the final enum/names remain to be validated).
- `last_attempt_at` and `last_success_at` as wall-clock timestamps for display/diagnostics.
- An in-process monotonic success/attempt time for reliable age and timeout calculations during this process lifetime; do not persist monotonic clock values across restarts.
- `stale_since`/computed age, source identity, and a safe error summary when relevant.
- The last successfully normalized value, if one exists.

A successful empty result is distinct from not collected, unsupported, and failed. A section failure retains that section's last good value and marks it stale; other sections in the same collection may still update successfully. First-poll failure has no last-good value and must display unavailable, not an empty or healthy result. UI consumers are told the timestamp/freshness of each section, including when a screen combines differently aged sections.

Use a bounded **in-memory** store for current state and only bounded metric samples required by approved trend/rate features. Snapshot publication is atomic at the application-state boundary, but individual section timestamps remain visible. Persistence of preferences/session secrets is not monitoring state and is addressed separately in ADR 0008.

## Consequences

- Partial collection is representable without discarding valid data or fabricating zeroes.
- Snapshot schema, equality, status vocabulary and stale-time presentation must be defined before implementation.
- Bounded history has explicit memory/retention limits; app restart loses transient telemetry by design unless a future persistence requirement is approved.

## Validation required

Fake-provider tests for initial/repeated/partial failures, empty vs missing data, recovery from stale state, clock behavior, mixed timestamps, snapshot publication and memory bounds. Benchmark Pydantic/immutable representation for actual upper-bound inventory.

## Ownership boundary

This ADR defines **state representation and retention**. ADR 0014 defines scheduling/cadence and freshness policy/thresholds. ADR 0004 defines logical batch composition and read coalescing. ADR 0007 defines execution/worker lifecycle.

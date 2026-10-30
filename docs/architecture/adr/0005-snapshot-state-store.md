# ADR 0005 — Section Snapshots and Last-Good State

- **Status:** Implemented locally; numeric freshness policy remains owner-configured
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Application architecture owner.

## Context and evidence

- **Repository fact:** current `App.host` and `App.vms` are mutable and have no source-specific timestamps or partial-result lifecycle (`orchestrator.py:34–43, 68–79`). Some failures replace usable values with an error/empty result.
- No app-owned database or persisted monitoring-history requirement is established (ADR 0008).

## Decision

Represent each independently collected section—at minimum defined-object inventory, running-process evidence, local node/Sball status, host metrics, and on-demand detail—with its own value and lifecycle. A view may combine sections but must preserve their source and freshness distinctions.

Each section carries a last-good normalized value if one exists, source identity, a status that distinguishes never-collected/current/partial/stale/failed-without-value/unsupported, last attempt and last success wall-clock times, a safe error/quality summary, and in-process monotonic times for reliable age calculations. Exact status names can be finalized during implementation; the distinctions cannot be collapsed. A successful empty result is distinct from failure or unsupported data.

A failed section retains its own last-good value and becomes stale/unavailable; other sections from the same collection can still publish independently. A failed `pvm-running-vms` enrichment must never invalidate a successful `user/objects` inventory. First collection failure has no last-good value and is displayed unavailable, not empty or healthy. Fresh object inventory does not refresh helper-derived fields, and vice versa.

`CollectionCoordinator` in the single `application/` package owns publication of section snapshots and last-good retention. Hold them in a concrete bounded in-memory value/container inside that coordinator; there is **no SnapshotStore port or second store service**. ADR 0011 assigns ownership; ADR 0014 owns due/freshness policy. Wall time is for display/diagnostics; monotonic age is process-local and is not persisted across restarts.

Keep only bounded metric samples required by an approved rate/trend feature. Current monitoring snapshots and UI state are not persisted. Session credential storage and the external read-only PVM audit DB are distinct concerns (ADR 0008).

## Consequences

- Partial collection cannot turn into a false empty inventory, zero metric, or fabricated healthy status.
- Section ages may differ in one screen and must be shown or otherwise made clear.
- App restart loses transient telemetry; no database is implied.
- The concrete in-memory state must remain simple; no pluggable store abstraction is justified by current requirements.

## Validation required

Fake-provider tests for first/repeated/partial failures, successful empty data, recovery, independent timestamps, duplicate/invalid data quality, freshness-only updates, stale publication rejection and bounded history. Benchmark representation for expected and upper-bound inventory. No target-host semantics are claimed by this ADR.

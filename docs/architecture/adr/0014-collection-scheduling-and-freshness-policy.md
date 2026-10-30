# ADR 0014 — Collection Scheduling and Freshness Policy

- **Status:** Implemented locally; host cadence/freshness budgets remain pending owner approval
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Product/application architecture owner; PVM operations owner approves load/freshness budgets.

## Context and evidence

- **Repository fact:** the current overview has a three-second default refresh interval and repeats collection in its loop (`commands/overview.py:19–23, 32–56`); `metrics_snapshot()` separately calls `monitoring/metrics` and `sball/show` (`monitoring.py:87–175`).
- No accepted per-section freshness SLA, PVM load budget, supported VM upper bound, or collection coordinator exists in current source.

## Decision proposal

One `Application.CollectionCoordinator` owns refresh cadence and single-flight request admission for the whole app (ADR 0011). It schedules by logical data section/request key defined in ADR 0004. There is no separate scheduler package and no independent timer policy in screens. ADR 0005 owns the per-section value/status/timestamps and last-good retention; this ADR owns when collection is due and the age at which a section is considered stale.

### Scheduling rules

- Collect only sections needed for the active view or an explicit one-shot request. Detail, license, and audit data are on demand unless a confirmed requirement changes that.
- A TUI timer may ask the coordinator for a refresh only while its visible monitoring/dashboard view is active. The interval must be visible/configured by product policy and bounded by measured host cost. A redraw, resize, focus, sort, or filter is not a collection request.
- The non-TTY CLI never starts a TUI, polling loop, sleep-to-gather-rates pass, hidden background refresh, or timer. A read command performs one bounded collection and exits; help/version/config-only commands perform no PVM collection. See the first Change boundary in `07-validated-architecture.md`.
- If a refresh is active, the coordinator shares an identical in-flight result or retains at most one “refresh again” intent. It drops obsolete timer ticks; it never creates an unbounded queue.
- Start with serialized read-only PVM calls. Any concurrency increase needs PVM evidence and measured benefit. Mutation admission/order belongs to the `OperationCoordinator` (ADR 0011/0012); execution mechanics are ADR 0007.
- Repeated read failures do not create faster retry loops. Any bounded backoff is a coordinator policy requiring explicit values/tests; do not add generic retry middleware.

### Freshness rules

- Each section has its own last attempt/success, age and status as defined in ADR 0005. Object inventory and process-list enrichment do not share freshness.
- Product owner must set maximum acceptable age by section before action eligibility or release defaults depend on it. Until set, show source age/status; do not label old data current or use stale/partial inventory to approve destructive bulk work.
- A section becoming stale does not invalidate another section. Last-good remains available with a stale marker; first-poll failure remains unavailable.
- Use wall time for displayed timestamps and process-local monotonic time for age/cadence. Do not interpret Sball host time or a wall-clock change as proof of freshness.
- `sball_state=quorate` remains the valid signal that Sball reports Quorate, with its own source/time; it does not establish full membership or universal node health (ADR 0009).

## Ownership boundaries

- **ADR 0004:** data sources, logical inventory batch, UUID merge/quality semantics, and canonical request identity.
- **ADR 0014:** one coordinator's refresh cadence, demand/active-view policy, stale thresholds and retry pacing.
- **ADR 0005:** section state shape, freshness metadata, partial/last-good publication and bounded samples; publication is executed by the CollectionCoordinator, not a separate store port.
- **ADR 0007:** bounded execution mechanics. CollectionCoordinator and OperationCoordinator own their application work lifetimes; Infrastructure owns OS process lifetime (ADR 0011).
- **ADR 0012:** mutation freshness gate and action confirmation; mutation requests do not use the polling schedule.

## Consequences

- Refreshes no longer arise independently from each widget or from a non-TTY view.
- Inventory, process enrichment, metrics, and status can be visibly different ages.
- Numerical intervals, maximum ages, failure backoff values and resource budgets remain unresolved until target/user evidence exists.

## Validation required

Measure call counts/latency/CPU on supported PVM cohorts; agree per-section freshness and active-view behavior; test slow/overlapping/failing fake-provider requests, coalescing, one pending intent, no queue storm, and no stale publication. No PVM host behavior or timing is claimed verified.

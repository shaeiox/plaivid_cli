# ADR 0014 — Collection Scheduling and Freshness Policy

- **Status:** Proposed
- **Date:** 2026-10-30
- **Decision owner:** Product/application architecture owner; PVM operations owner approves load/freshness budgets.

## Context and evidence

- **Repository fact:** interactive refresh is synchronous; overview polls several sources repeatedly, with a default UI refresh interval of three seconds (`commands/overview.py:19–23, 32–56`). `metrics_snapshot()` itself calls both `monitoring/metrics` and `sball/show` (`monitoring.py:87–175`).
- No approved freshness SLA, PVM command latency/CPU budget, supported VM upper bound, central scheduler, or in-flight request coalescing currently exists.
- **Important signal:** `sball_state=quorate` is a valid indication that Sball reports the cluster as Quorate. It is not evidence that every node is healthy/reachable or that complete membership is available (ADR 0009).

## Decision proposal

Application owns one scheduler/poll policy per running app. Screens express interest in data; they do not start independent polling loops. Scheduling is per logical section/dataset, with a configurable policy chosen from product freshness needs and measured local PVM cost. No numeric intervals or stale thresholds are accepted by this ADR.

### Scheduling rules

- Collect only sections needed for the active view or explicit user command. Initial dashboard load may request inventory and host status; detail, license, and audit reads are on demand unless product requirements say otherwise.
- Separate metrics, inventory/enrichment, and slower/auxiliary data cadence where users permit different freshness. A UI redraw, resize, sort, or focus change does not itself trigger PVM collection.
- Do not queue unbounded timer ticks. If a refresh is still in flight, coalesce another identical request or retain at most one “refresh again” intent; drop obsolete periodic ticks.
- Use a conservative serialized read-only execution policy initially. Read concurrency requires PVM evidence and measured benefit. Mutation ordering/execution is separate (ADR 0007/0012).
- After repeated read failure, do not spin faster than the configured cadence. A bounded backoff policy may be added only with explicit values and tests; do not add generic retry middleware. User-requested refresh can be distinguished from scheduled retry.

### Freshness rules

- Each section carries its own latest attempt, latest success, age and status in the form owned by ADR 0005.
- Product owner sets per-section maximum acceptable age and stale presentation before release. Until those values exist, show age/status transparently but do not infer that old data is acceptable or current.
- A section becoming stale must not invalidate a different section. Last-good values remain visible with a stale indicator; first-load errors remain unavailable.
- Record collection time from an appropriate wall clock for display/audit and monotonic elapsed time for in-process scheduling. Clock/host-time discrepancies are not used to silently bless freshness.
- Sball's `quorate` status may be displayed as “Sball reports Quorate” with its own timestamp. It cannot be promoted to “all nodes healthy” based on this field alone.

## Ownership boundaries / overlap resolution

- **ADR 0004:** logical dataset composition, one batched VM object query plus running-list merge by UUID, no N+1 detail requests, and identity of requests that can share in-flight reads.
- **ADR 0014 (this ADR):** which data is due/needed, poll cadence, backoff/freshness thresholds, and active-view policy. It invokes logical requests defined by ADR 0004.
- **ADR 0005:** section result representation, timestamps/status fields, last-good retention, partial snapshot publication and bounded history.
- **ADR 0007:** bounded worker/process execution, cancellation, cleanup, and concurrency limits at execution time. Scheduler must honor those limits.

This division avoids four competing implementations of “refresh” or “freshness”.

## Consequences

- Keeps a dashboard refresh from implicitly multiplying local subprocess calls.
- Freshness becomes explicit per view/section instead of global or silently mixed.
- Actual intervals and stale behavior cannot be finalized without a user SLA and PVM measurements.

## Validation required

Measure current and proposed call counts/latency/CPU at target inventory sizes; establish acceptable freshness per section with users; exercise slow, overlapping and repeatedly failing fake-provider calls; verify coalescing and no queued refresh storm; validate active-view transitions and explicit refresh behavior on Textual.

# 05 — Data Collection, Snapshot and State Architecture

**Status:** Validated design direction, not implementation. It is constrained to Linux and local PVM access in this phase; future remote providers are only an extension point.

## Current state

- `vms.inventory()` performs an all-VM XML query then a separate `pvm-running-vms` process and merges results (`vms.py:64–149`).
- `monitoring.metrics_snapshot()` calls `monitoring/metrics` and then `sball/show` (`monitoring.py:87–175`).
- `App.refresh()` separately fetches host status and inventory (`orchestrator.py:68–79`).
- The overview repeats metrics plus host-status and inventory per tick; it also queries tap mapping once at entry (`commands/overview.py:19–42`). The two sbell metrics/host calls and two inventory sources mean four source operations per overview refresh, plus tap-map request at entry.
- Data is stored as mutable `App.host` and `App.vms`; refresh errors sometimes replace values with an error/empty result. There is no freshness marker, last-success timestamp, snapshot history, diff model, dirty tracker, or request coalescer.
- The overview derives network rates by comparing two raw counter dictionaries (`render.py:194–207`), but state ownership and reset behavior are implicit.

## Proposed pipeline

```text
Local PVM Adapter / Collector
        │ source results + status + timestamps
        ▼
Normalizer + Schema Validation
        │ immutable normalized NodeSnapshot
        ▼
In-memory Snapshot Store (last successful value per data section)
        │ old snapshot + new snapshot
        ▼
Change Detector (domain-level values, not terminal cells)
        │ typed changes / current freshness
        ▼
Application state + events / read models
        │ changed widgets and notifications
        ▼
Textual renderer (owns terminal diff rendering)
```

Keep this as a small modular monolith with explicit Python modules/interfaces; do not introduce distributed queues, a broker, or a generalized telemetry platform for one local PVM process.

### Collector and adapter

- Create a single application-facing collector operation that returns a typed **partial snapshot result** for the local PVM. Its internal orchestration owns command selection, cadence, cancellation, timeout, and duplicate in-flight request control.
- Wrap the **existing** integrations behind a narrow local adapter (name proposal: `LocalPvmProvider`): batched `user/objects` inventory, `pvm-running-vms` enrichment, `sball/show`, `monitoring/metrics`, and on-demand detail/license methods only where required. This adapter is the sole place that knows sbell argv/XML and local helper output formats.
- Preserve the all-VM `user/objects` query as the inventory batch. Merge the separate running-list result by UUID, as current `vms.inventory()` does. Do not perform detail requests for every VM: request selected detail only when the user opens it.
- Consolidate the host status fields currently fetched twice for an overview into one normalized collection result wherever a single already-supported request can supply them. The existing parser indicates `monitoring/metrics` does not contain `sball/show` load/sball fields, so one extra local call may remain unless validated interface evidence changes that fact.
- Avoid additional calls for a view that does not use the data. Fetch license only for health if it remains required. Refresh inventory less frequently than high-level host metrics only if UX requirements accept that freshness difference.

### Normalization and models

- XML and the `pvm-running-vms` text table are untrusted/versioned input. Parse at the adapter boundary, validate required IDs and numeric ranges, normalize PVM state aliases, and retain field-level missing/unsupported information rather than inventing defaults.
- Define an immutable normalized snapshot containing local-node identity, collection timestamp, inventory, metrics, and explicit source/status metadata. Distinguish “known empty list” from “not collected”, “failed”, “unsupported”, and “stale”.
- Prefer one consistent typed schema for published snapshots. Pydantic is a candidate for boundary validation; benchmark validation cost with representative and upper-bound VM counts. Do not retain both mutable dictionaries and redundant validated copies throughout the view tree.
- Make derived values (e.g. rates from byte counters) a deterministic pure transform using sample timestamps; detect counter resets/interface replacement instead of silently treating them as zero throughput.

### Snapshot store and failure behavior

- Start with an **in-memory** store holding the last successful value and last attempt metadata per section. Persistent SQL storage is not needed to draw a current dashboard and has not been justified by product requirements.
- On a collection failure, retain the last valid section, update `last_attempt`, error, and `stale_since`/age, and publish the failure separately. Never replace valid inventory with an empty list merely because one poll failed.
- Render stale age and an unobtrusive error/stale indicator; make it clear when a view combines samples from different collection times. For a first collection failure, show unavailable, not an empty/healthy state.
- Keep bounded history only for metrics needed for trends/rates/alerts, with explicit sample count and retention. No unbounded per-refresh snapshot history.

### Collection cadence and duplicate suppression

- Model collection categories explicitly (inventory, host metrics, detail, license), with configurable but conservative intervals determined by measurement and user requirements. Poll only while a relevant view is active unless a confirmed requirement calls for background refresh.
- Coalesce concurrent requests for the same category/host: one in-flight collection result is shared among waiting consumers. Do not queue a backlog of obsolete refreshes; discard/replace a pending refresh when a newer request supersedes it.
- Use one scheduler/refresh owner, not independent timers in every widget. Include timeout, bounded work and cancellation semantics. A dashboard redraw must not cause another collection.
- Start with **serialized** sbell access until target evidence demonstrates concurrent calls are safe and beneficial. If read-only collection is later parallelized, cap concurrency and measure daemon load/latency. Never overlap state-changing action calls with a blind retry or duplicate action.
- Separate data freshness policy from render frequency: the screen may redraw for input/resize without making a host command, and a collector may update only changed state without forcing every view to rerender.

## Async execution and operation lifecycle

Textual owns an async UI event loop. Current sbell calls are blocking subprocess `communicate()` calls. Execute blocking provider operations in a worker thread or use a carefully tested asynchronous subprocess adapter; do not call them on the UI event loop. A thread-worker approach is a reasonable initial prototype because it can wrap existing blocking code with limited change, but cancellation cannot be assumed to stop a subprocess: retain timeout/process cleanup in the adapter. Use async subprocess only if platform/runtime and `sudo` behavior are verified and tests show a clear benefit.

- Read-only collection requests can be coalesced and replaced when obsolete.
- Mutating actions should enter an explicit serialized operation queue, show pending/running/result per target, and require explicit user intent. On cancellation/timeout, report **outcome unknown** if the remote/local PVM command may have executed; do not automatically resubmit.
- Bulk operations should have per-target result objects and an explicit policy for continuing after an individual failure. Preserve every failure reason and show the final partial-success summary.

## Change detection, dirty state and rendering

- Use a domain-level equality/change detector to avoid emitting application events or rebuilding unchanged read models. It must compare normalized values, not timestamps that change on every fetch.
- Textual's own renderer should calculate terminal-cell changes. Do not add custom ANSI dirty-cell tracking unless profiling proves the framework's differential render path is insufficient.
- Update stable widgets with changed rows/sections. For large tables, benchmark updates, sorting, filtering and selection restoration. Use paging/windowing if the PVM inventory exceeds practical Textual `DataTable` memory/latency.
- Keep current snapshot state authoritative. UI selection/focus, filters, and navigation state are UI state; do not mutate the collected domain snapshot to represent presentation sorting.

## Performance validation targets (to be agreed)

Before selecting intervals or table implementation, measure on representative PVM hardware:

- Per-command wall time and CPU; total calls and CPU per refresh.
- Textual idle/refresh CPU and resident memory at representative/upper-bound VM counts.
- XML parse and normalization time; snapshot diff time; table update time.
- Memory growth under sustained monitoring and bounded metric-history policy.
- Behavior when a command hangs, returns malformed XML, exits nonzero with output, or a section repeatedly fails.

No numeric budgets are currently approved. Set budgets from user-visible freshness needs and measured PVM overhead rather than inventing them.

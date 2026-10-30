# 05 — Data Collection, Snapshot and State Architecture

**Status:** Proposed design; no implementation or target-host validation. PVM evidence limits are in `04-pvm-interface-analysis.md` and ADR 0004.

## Current implementation facts

- `vms.inventory()` performs one all-VM object query and a separate `pvm-running-vms` invocation, then merges records (`vms.py:64–149`). It can overwrite object state based on process-list presence (`vms.py:119–132`) and can fall back to a `/proc` scan for uptime (`vms.py:136–149, 201–241`). These are current code behaviors, not the target contract.
- `monitoring.metrics_snapshot()` calls `monitoring/metrics` and `sball/show` (`monitoring.py:87–175`). `App.refresh()` separately fetches host status and inventory (`orchestrator.py:68–79`). Overview repeats these sources each loop and separately queries tap mapping on entry (`commands/overview.py:19–42`).
- Current state is mutable `App.host`/`App.vms`, without source-specific time, partial states or last-good retention. A failed refresh can replace useful data with an error/empty value.
- **Evidence correction:** no new target-host output was captured. Repository examples are documentation evidence only; they do not verify fields or merge semantics on a supported PVM host.

## Single-owner design

```text
Presentation (CLI/TUI) -> Application.CollectionCoordinator -> LocalPvmProvider port
                             │                         │
                             │ section state             └-> Infrastructure local adapter/process runner
                             │ last-good publication
                             └-> typed application result -> Presentation

Application.OperationCoordinator -> provider action port -> Infrastructure
Bootstrap constructs and owns application start/stop; there is no separate scheduler or store port.
```

The sole `CollectionCoordinator` in `application/collection.py` owns refresh cadence, active-view demand, single-flight admission, bounded read-work lifetime, logical result assembly, per-section last-good publication, and stale-result rejection. Its simple concrete in-memory section values are not exposed behind a SnapshotStore interface.

The sole `OperationCoordinator` in `application/operations.py` owns mutation admission, serial operation lifecycle, operation state, per-target outcomes and mutation-worker lifetime. Infrastructure's process runner independently owns each operating-system child from spawn to bounded cleanup/reap; it does not own refresh cadence or mutation policy. Bootstrap is the only composition root and creates/shuts down both coordinators and the local provider. Detailed boundary ownership is ADR 0011; collection batching is ADR 0004; worker mechanics are ADR 0007; mutation policy is ADR 0012.

Screens can request reads and observe results, but do not spawn independent pollers or own long-lived provider workers. A Textual timer is only a visible request source for the collection coordinator, not a second scheduling policy. No event bus, scheduler package, generic plugin framework, or snapshot-store port is proposed.

## Local source contract

- Defined objects and running-process listing are distinct facts with independent source status/time. The object query is the all-VM logical batch; process rows are separately collected evidence merged only by canonical UUID.
- Detail is fetched only for a selected VM. Never issue N+1 detail queries for inventory. Reuse tap/NIC fields only where supported version fixtures prove presence.
- `/proc` scanning is documented as a current optional uptime fallback, **excluded from default and periodic collection**. No process-table scan is added without separate approved need and measured cost.
- Conflicts, duplicates, invalid/unmatched records and source-specific partial failure follow ADR 0004. A failed enrichment source cannot discard or invalidate a successful object inventory.
- Host metrics and Sball status remain separate unless verified response fields prove they can be supplied together. Do not fabricate zero or healthy values for missing fields.

## Normalization and section snapshots

Infrastructure parses the current sources to normalized typed values at the boundary. The published snapshot contains section values plus source, success/attempt timestamps, partial/unsupported/error state and freshness. Keep one published representation; do not create repeated mutable-dictionary and DTO copies.

Each section independently distinguishes never-collected, valid empty, current, partial, stale, failed-without-value and unsupported. It retains its own last-good value and timestamps. CollectionCoordinator publishes a successful section even when a sibling section fails; a failed running-list enrichment cannot invalidate object inventory. Age uses in-process monotonic time; wall time is for displayed timestamps/diagnostics. `sball_state=quorate` is preserved as “Sball reports Quorate” with its own timestamp, not a claim of complete membership or all-node health.

Do not persist monitoring snapshots by default. Bound any sample history to data and duration required by an approved trend/rate feature. Session token storage is separate and unresolved (ADR 0008/0012); the PVM audit database remains an externally owned read-only source.

## Scheduling and failures

CollectionCoordinator collects only sections requested by the active view or explicit CLI command. It coalesces identical in-flight logical requests using the identity from ADR 0004 and permits at most one pending refresh intent; obsolete periodic ticks are dropped. Redraw, resize, sorting, focus and formatting do not collect data. Use conservative serialized PVM reads until target evidence supports another bound.

Refresh cadence and per-section stale thresholds are not numerically approved. ADR 0014 owns those policy values. Failed collection retains last-good data and records the failure/age; no prior good data means unavailable. One source failure neither invalidates nor refreshes another. A read begun before mutation for affected UUIDs cannot publish over the newer operation generation; see ADRs 0007, 0012 and 0013.

## Semantic changes and rendering

Compare normalized section values at the Application level to avoid unnecessary read-model/widget updates; freshness/error transitions remain changes even when data fields are equal. Textual, if accepted after prototype, owns terminal-cell differential rendering. Do not add custom dirty-cell tracking. Stable UUID row keys preserve selection. Application semantic comparison and terminal rendering are separate (ADR 0006).

## Validation before implementation/release

Use fake providers and fixture-backed parsers for independent success/failure, object/process conflicts, duplicate/invalid/unmatched rows, freshness, last-good retention, stale-result rejection and bounded memory. Target captures are required to establish supported source fields/state meanings. Measure command count, command wall time/CPU, XML normalization, memory, refresh load and inventory scale on approved PVM cohorts before setting cadence or budgets. No numeric freshness/resource SLA is invented here.

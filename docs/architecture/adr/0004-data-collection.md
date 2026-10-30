# ADR 0004 — Logical Batch Collection and Inventory Merge

- **Status:** Proposed
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Application/data architecture owner; PVM maintainer confirms source contracts.

## Context and evidence

- **Repository fact:** `vms.list_all()` performs one `user/objects` query for all typed VM objects (`vms.py:15–17, 64–91`). `vms.inventory()` separately executes `pvm-running-vms` and merges by lower-cased UUID (`vms.py:114–149`). VM detail issues an on-demand `user/objects` query (`vms.py:267–339`).
- **Repository fact:** overview makes a separate tap-map `user/objects` query once per entry and repeats metrics/status/inventory source calls each tick (`commands/overview.py:19–42`, `monitoring.py:87–175`).
- **Unverified:** host-side query cost, full field availability, scalability, output stability, or atomic consistency of these interfaces. No PVM host was inspected.

## Decision

Define collection batches by **logical dataset**, not by requiring one physical command to contain every field. The initial logical VM inventory collection is:

1. One batched `user/objects` request for all authorized VM objects and fields required by the inventory.
2. One `pvm-running-vms` result for live running-process fields that the object query does not currently supply.
3. Normalize UUIDs to one canonical comparison form and merge both results by UUID. Record source and partial/missing enrichment status. Do not infer that this combined result is atomic.

Fetch full VM detail only for the selected VM. **No N+1 VM queries:** inventory, dashboard, sorting, and aggregate calculations must not trigger one detail request per VM. If the current batched query lacks a field, either accept it as unavailable, establish a supported bulk source, or make detail explicitly on-demand; do not silently issue per-VM calls.

Coalesce identical in-flight logical read requests: consumers requesting the same dataset, parameters and current local PVM context share one in-flight result. Collector scheduling decides whether/when work is due (ADR 0014); this ADR owns what forms a logical batch and duplicate-read identity. Mutating operations are not coalesced as reads and are covered by ADRs 0007/0012.

## Consequences

- “Batch” means one query for the full inventory plus the separately required running list; it does not claim a single PVM command or transactional snapshot.
- UUID merge tolerates source ordering differences and permits explicit unmatched running entries, but duplicate/invalid UUID policy must be defined.
- Per-VM details remain lazy, avoiding an N+1 pattern.
- The collector may still require multiple source calls for host metrics, status, license, or detail.

## Validation required

Capture representative redacted results for each supported PVM version; verify all-field query size/performance/permissions, stable UUIDs and duplicate behavior, helper row format, object/running set discrepancies, and concurrent repeated-read behavior. Do not invent a new command or structured output mode.

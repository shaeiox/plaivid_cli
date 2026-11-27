# ADR 0004 — Logical Batch Collection and Inventory Contract

- **Status:** Implemented locally; PVM source/schema contracts remain pending manual validation
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Application architecture owner; PVM maintainer validates source contracts.

## Context and evidence

- **Repository fact:** `vms.list_all()` performs one all-object `user/objects` query; `vms.inventory()` separately reads `pvm-running-vms` and merges by lower-cased UUID (`vms.py:64–149`).
- **Repository fact:** the helper's fields are a process-list observation; object state is a different source. Current code can overwrite object state when a helper row exists (`vms.py:119–132`) and adds helper-only UUIDs as VM objects (`vms.py:123–129`), despite its comment. `vms.inventory()` also has a Linux `/proc` uptime fallback (`vms.py:136–149, 201–241`).
- **Evidence limit:** repository examples and source are not newly captured target-host output. Field completeness, state semantics, format stability and performance remain unverified on supported PVM hosts.

## Decision

### Logical batch and source facts

The logical VM inventory is composed from independently sourced results:

1. One batched `user/objects` query supplies authorized defined-object records, including the VM object's reported configuration/state fields when present.
2. One `pvm-running-vms` invocation supplies rows observed in the running-process listing and its helper-reported live fields (PID/uptime/port/CPU/memory/name/UUID as parsed by current code).
3. Compare/merge only by a validated canonical UUID. Preserve each source's successful/partial/failed status and freshness separately. This is not an atomic PVM transaction and neither source is a substitute for the other.

The `user/objects` query is the inventory batch. Do not issue detail queries per VM: selected detail remains on demand. Tap/NIC facts may be reused from the inventory response **only after redacted fixtures for each supported PVM version prove the required fields are present**. Otherwise the derived view is unavailable or a separately collected section, not an assumed cached fact.

The `/proc` scan in current `vms.proc_uptimes()` is **not in the default design**. Do not perform process-table scans as a routine fallback. Reconsider only through a separately approved requirement and measured host-overhead/privacy review.

### Merge and data-quality semantics

- **State disagreement:** keep object-reported VM state and process-list presence as separate facts. A helper row does not overwrite object state; it indicates that a process row was observed. A present helper row can be retained as separate evidence. Treat a missing helper row as negative evidence only when the process source is complete/current; partial, truncated, failed, or unavailable helper results cannot create an absence-based conflict. Do not silently choose a combined `started` state.
- **Duplicate UUID:** after canonicalization, duplicate object UUIDs make that UUID ambiguous and are excluded from actionable resolution; mark the object section partial and report a data-quality issue. Duplicate helper rows do not select an arbitrary winner; mark that UUID's process enrichment ambiguous/partial. Retain unaffected valid records.
- **Invalid records:** missing/malformed UUID, invalid required fields, or an unparseable row is not silently converted to a healthy default or an empty inventory. Exclude the invalid record, retain valid siblings, and mark that source result partial with a bounded diagnostic/count. If the source result itself cannot be trusted, do not publish it as a complete empty result.
- **Unmatched process row:** retain as unmatched process evidence with source/time and a safe diagnostic; do not fabricate a defined/actionable VM object from it. Possible causes (permission filtering, inventory race, invalid row) are not inferred as fact.
- **Partial collection:** successful object inventory remains publishable if running-list collection/parsing fails. The failed enrichment cannot clear, invalidate, or relabel the object inventory. Truncated helper output is partial even if its retained prefix parses. A partial helper list never proves absence. Conversely, a successful helper result does not create a complete defined-object inventory when `user/objects` failed; expose the two results independently.
- **Source freshness:** object and process sections each carry their own last attempt, last success and freshness status (shape/retention in ADR 0005). A recent object query does not make helper fields fresh; a failed helper must leave its own last-good enrichment stale/unavailable while the new object data can still publish.

`CollectionCoordinator` is the single owner of collection admission and publication (ADR 0011). This ADR specifies the logical batch and request identity: same local context, dataset and parameters are the same read request. The coordinator coalesces identical in-flight reads; screens do not start separate collections. Cadence/freshness policy is ADR 0014. Mutation is not a collection read (ADRs 0007/0012).

## Consequences

- One object query plus one helper invocation is a logical batch, not a single command or a transactional view.
- Source conflicts and partial data are visible instead of being collapsed into a misleading state.
- Inventory scale does not create N+1 detail queries or routine `/proc` scans.
- Local object permissions may hide VMs; unmatched rows remain evidence and are not automatically safe action targets.

## Validation required

Obtain redacted captures/fixtures for each supported PVM version, then verify query fields, parser formats, UUID normalization, duplicate/invalid/unmatched behavior, state disagreements, permission filtering, independent failures/freshness and call cost. Existing repository examples are not capture fixtures. Do not invent new commands, batch fields, idempotency, or source authority beyond verified evidence.

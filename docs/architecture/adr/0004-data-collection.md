# ADR 0004 — Local PVM Data Collection

- **Status:** Proposed; PVM behavior unverified
- **Date:** 2026-10-30

## Context

Current inventory is one `user/objects` XML query plus a separate `pvm-running-vms` process. Overview also calls `monitoring/metrics` and `sball/show` each cycle. There is no scheduler, batching abstraction, deduplication or source freshness model.

## Proposal

Use one in-process collector coordinating a narrow local PVM adapter. Batch defined-VM fields with the existing `user/objects` query, merge the running list by UUID, fetch VM details only on demand, and share in-flight reads among consumers. Begin sequentially with bounded timeouts; use separate cadence per data section only after freshness/overhead requirements are measured. Serialize mutations and never retry them generically.

## Consequences

- Reduces duplicate work and avoids independent screen polling loops.
- Batching is limited by verified interfaces: the existing all-VM query does not remove the second running-list source or prove cluster-wide completeness.
- Any asynchronous or parallel collection remains an explicit tested optimization, not a default assumption.

## Validation required

Capture supported PVM responses, measure each command/daemon cost and test read-only concurrency safety. Confirm what fields can be batched and supported collection intervals with PVM maintainers.

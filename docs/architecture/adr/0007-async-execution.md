# ADR 0007 — Bounded Worker and Subprocess Lifecycle

- **Status:** Proposed; execution mechanism open
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Application/platform architecture owner; PVM owner confirms process contract.

## Context and evidence

- **Repository fact:** current `transport._run()` blocks in `Popen.communicate(timeout=...)`; on timeout it calls `kill()` on the direct process and raises without an explicit wait/reap (`transport.py:66–77`). Current default command timeout is 30 seconds (`config.py:19–20`).
- **Proposal:** Textual has an async UI lifecycle, so blocking process work must not run on its event loop.
- **Unverified:** whether `sudo sbell` launches descendants, how it handles signals, whether local PVM calls can run concurrently, and whether cancellation stops a PVM-side operation.

## Decision

Initially isolate existing blocking local-provider calls in a **bounded worker executor** owned by the collector/application bootstrap. The exact executor API is open to a prototype. Do not call blocking `sbell` or file/database work on the UI event loop. Do not create an unbounded thread per refresh or independent worker pool per widget.

Worker lifecycle requirements:

- Set a finite concurrency bound and bounded pending work. Prefer one in-flight read for a given logical request; share its result per ADR 0004. Obsolete periodic refreshes may be coalesced/dropped instead of queued.
- Serialize VM-changing operations. They have explicit operation IDs and per-target outcomes; they are not ordinary refresh work.
- On shutdown, stop accepting work, signal cancellable reads, wait a bounded period, then clean remaining child processes according to a tested process policy. The owner must ensure pipes are drained/closed and children are waited/reaped.
- Apply a per-operation timeout. Process-group termination, if needed, must be implemented only after target behavior and platform semantics are tested; killing a wrapper alone may not stop descendants.
- Surface worker exceptions as typed application outcomes, not uncaught UI-loop exceptions. Do not allow a worker to mutate presentation widgets directly; publish a result/event for the UI thread.

### Cancellation and ambiguous mutation outcome

Cancellation of a UI task does **not** prove that an OS child or PVM operation stopped. For reads, cancellation may stop waiting while underlying work is cleaned up; do not start duplicate work until in-flight ownership is resolved. For mutations, if timeout/cancellation happens after dispatch and there is no verified cancellation/transaction contract, report `outcome_unknown`, retain the operation ID, and refresh/read authoritative state before offering a retry. Never blindly retry a mutation.

Prototype an async subprocess implementation only if it demonstrably improves cancellation/cleanup and is compatible with Python target, `sudo`, signals, and packaged Linux behavior. Otherwise a carefully bounded thread wrapper around a reliable process helper is simpler.

## Consequences

- UI responsiveness is decoupled from external command latency, but PVM read concurrency remains low and measured.
- Thread cancellation is cooperative; subprocess cleanup must be explicit.
- Unknown operation outcomes require an application error/result model (ADR 0013) and safe action policy (ADR 0012).

## Validation required

Fake process tests for timeout, nonzero exit with output, large stdout/stderr, grandchildren, signal handling, reaping, cancellation, worker shutdown, queue saturation, duplicate coalescing, and mutation unknown outcomes. Verify with a controlled PVM host before relying on any signal/exit semantics.

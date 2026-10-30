# ADR 0007 — Bounded Worker and Subprocess Lifecycle

- **Status:** Implemented locally; target wrapper/process behavior remains pending manual validation
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Application/platform architecture owner; PVM owner confirms process contract.

## Context and evidence

- **Repository fact:** current `transport._run()` blocks in `Popen.communicate(timeout=...)`; on timeout it kills the direct process without explicit wait/reap (`transport.py:66–77`). The default command timeout is 30 seconds (`config.py:19–20`).
- **Proposal:** Textual has an async UI lifecycle; blocking local PVM calls must not execute on that event loop.
- **Unverified:** `sudo sbell` descendant/signal behavior, PVM concurrency safety, and whether command cancellation can stop a PVM-side operation.

## Decision

Use bounded, app-lifetime-owned work; no thread/task per widget and no separate executor/scheduler framework.

- **Read work:** `Application.CollectionCoordinator` owns admission and lifetime of one bounded read-worker lane. At most one active read per configured bound and one pending refresh intent per identical logical key; duplicate in-flight requests share a result. Screens can stop waiting when they close, but do not own or destroy the underlying process.
- **Mutation work:** `Application.OperationCoordinator` owns mutation admission, serialization, operation result state, and lifetime of dispatched mutation work. A modal/screen closing or a user navigating away cannot discard a dispatched operation's result tracking. Mutations are not canceled or retried by canceling a UI task.
- **OS processes:** the Infrastructure runner owns each child from spawn through bounded pipe drain, deadline, and reap. On POSIX it starts a new session and kills the isolated process group on timeout/reader cleanup; the fake grandchild regression test verifies that local behavior. This does not prove how a target `sudo`/PVM wrapper behaves. Output is bounded, argv is used without a shell, and the inherited child environment is allowlisted by default.
- **Bootstrap:** sole composition root constructs and closes the coordinators/provider and initiates orderly shutdown. It does not implement another queue, cadence, or operation state machine (ADR 0011).
- Textual receives results on its UI thread through its own supported worker/message mechanism; it does not receive direct widget mutations from background threads.

Per-command deadlines and output caps must be selected from tests/host measurements. A logical collection may have an overall deadline in addition to individual process deadlines; implement only one clear timeout owner per level and report which elapsed. On shutdown, stop admission, allow bounded completion/cleanup, and report unresolved dispatched mutations as unknown rather than silently dropping them.

### Cancellation and read/mutation ordering

Cancellation of a UI wait is not proof that a thread, child process, or PVM operation stopped. For a read, do not admit a duplicate while its underlying request remains active; an obsolete completion must not publish over a newer collection generation. For a mutation, timeout/cancellation after dispatch is `OUTCOME_UNKNOWN` unless verified evidence establishes the result. The OperationCoordinator serializes mutations and establishes a per-target generation/barrier with the CollectionCoordinator: pre-mutation reads for affected UUIDs cannot publish after the barrier; reads affecting those UUIDs wait until post-operation reconciliation or are explicitly marked stale. Post-operation readback can confirm an observed state but absence of change does not prove the command was not accepted. Exact outcome rules are ADR 0012/0013.

Do not automatically retry mutations. Async subprocess may be prototyped only if it improves process cleanup/cancellation and is verified with target `sudo`, signals, and packaging. A bounded thread lane around a correct process runner is the simpler initial candidate.

## Consequences

- UI responsiveness is separate from PVM concurrency; initial source calls remain serialized until safe concurrency is evidenced.
- Thread cancellation is cooperative; process lifetime remains Infrastructure-owned.
- Application-level unknown outcomes survive navigation and shutdown reporting.

## Validation required

Fake-process tests for spawn, timeout, output cap/draining, nonzero with output, children/descendants, signal handling, wait/reap, worker shutdown, queue saturation, duplicate coalescing, stale generation rejection, and unknown mutations. Confirm process/sudo semantics with a controlled supported host before relying on them. No live behavior is verified by this ADR.

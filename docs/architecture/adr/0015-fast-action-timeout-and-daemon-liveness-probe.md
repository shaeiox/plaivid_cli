# ADR 0015 — Two-Phase Fast Action Trigger, Daemon Liveness Probe, and Task Board `SKIPPED` Semantics

- **Status:** Implemented locally; host timing budgets remain pending manual PVM validation
- **Date:** 2026-11-08
- **Decision owner:** Application/platform architecture owner; PVM operations owner confirms host timeout budgets
- **Related:** [ADR 0007](0007-async-execution.md), [ADR 0012](0012-security-and-mutation-safety.md), [ADR 0013](0013-error-taxonomy-and-operation-outcomes.md)

## Context and problem

1. **Undifferentiated 30s subprocess ceiling:** Previously, all `sbell` invocations—fast read queries (`sball/show`, `user/objects`) and VM lifecycle actions (`vm/stop` graceful guest ACPI shutdown)—shared `PLAIVID_CMD_TIMEOUT` (`30.0s`). When VM #1 in a 100-VM batch hung during guest shutdown, waiting 30s stalled batch throughput, and killing the local `sbell` client produced a generic `PVM_PROCESS_ERROR` mapped to `OUTCOME_UNKNOWN` (`errno=None`).
2. **Over-broad batch abort on per-target timeout:** Because `OUTCOME_UNKNOWN` lacked a timeout error code and `errno` was `None`, the batch policy treated one slow guest VM identically to a broken session, immediately aborting VMs #2..#100. Conversely, blindly continuing on *every* timeout without checking daemon health would stall a 100-VM batch for `100 × timeout` when `sballd` itself was offline or wedged.
3. **Misleading Task Board states:** `OperationState.NOT_STARTED` was collapsed onto `TaskStatus.REJECTED` (`⊘ REJECTED`), queued targets could be shown as `▶ RUNNING` before an actual dispatch began, and generic progress strings overwrote authoritative `TargetOutcome.message` details.

## Decision

Adopt a **Two-Phase Fast Trigger + Daemon Liveness Probe + Scoped Fault Isolation** architecture across `plaivid_cli`:

### 1. Decoupled fast action timeout (`PLAIVID_ACTION_TIMEOUT`)

- Add `Settings.action_timeout` configured via `PLAIVID_ACTION_TIMEOUT` (default: **`10.0` seconds**) for VM and Virtual Desktop lifecycle actions (`vm/start`, `vm/stop`, `vm/reset`, `vm/pause`, `vm/resume`, `vm/kill`), while retaining `PLAIVID_CMD_TIMEOUT` (**`30.0` seconds**) for read/inventory commands.
- Thread optional `timeout: float | None = None` through `SbellClient.call()` and pass `self._action_timeout` from `LocalPvmAdapter.dispatch_action()`.
- Catch `ProcessTimeout` explicitly in `LocalPvmAdapter._call()` and raise `AppError(ErrorKind.PROCESS, ..., code="PVM_COMMAND_TIMEOUT")`, retaining `code` on `TargetOutcome`.

### 2. Fast 2.0s daemon liveness probe (`is_daemon_alive`)

- Implement `LocalPvmAdapter.is_daemon_alive(timeout: float = 2.0, *, token: str | None = None) -> bool` using a bounded `2.0s` `sbell user whoami` probe.
- Lifecycle targets are dispatched by the bounded rolling pool configured with `PLAIVID_MAX_CONCURRENCY` (default `3`); clean success (`SUCCEEDED`) does not incur a liveness probe. Each batch retains one operation-level mutation barrier and planned-order result reporting.
- When a target returns `PVM_COMMAND_TIMEOUT` or an error (`FAILED` / `OUTCOME_UNKNOWN`), invoke `is_daemon_alive(timeout=2.0)`:
  - **Daemon Alive (`True`):**
    - On `PVM_COMMAND_TIMEOUT`: record `OUTCOME_UNKNOWN` on that target with message `"command timed out (10s), daemon healthy"` (never auto-retry it), but continue scheduling unrelated targets.
    - On a dispatched non-session rejection, including VM-state or disk/storage errors: record `FAILED` for that target and continue scheduling siblings.
    - On explicit session/contract errors (`errno` 39/40/106/107/108/137/185, `PROCESS_START_FAILED`, or another classified session code): stop submitting new targets. Cancel futures not yet running, allow in-flight calls to settle, and mark only never-dispatched targets `NOT_STARTED`.
  - **Daemon Offline (`False`):**
    - Set the current target to `OperationState.FAILED` (`code="DAEMON_OFFLINE"`, detail `"Daemon Offline"` / `"command timed out (10s): Daemon Offline"`).
    - Set the shared stop event; no further target is submitted. Allow already-running calls to settle, mark only undispatched/cancelled-before-start targets `NOT_STARTED` with message `"Daemon Offline"`, and skip post-operation reconciliation against a dead daemon.

### 3. Truthful Task Board vocabulary and parallel progress

- Add `TaskStatus.SKIPPED = "SKIPPED"` in `domain/models/tasks.py`, map `OperationState.NOT_STARTED -> TaskStatus.SKIPPED`, and render it in `TaskViewFooter` as `– SKIPPED` in `muted` palette style (reserving `⊘ REJECTED` for true policy/admission rejections and pre-dispatch cancellations).
- Keep admitted batch targets in `TaskStatus.QUEUED` (`· QUEUED`, `started_at=None`) until `_dispatch_one()` actively begins dispatching that specific target (`OperationState.RUNNING` → `▶ RUNNING`), so only the in-flight target ticks an elapsed clock.
- Forward authoritative outcome details (`outcome.message`) through `report_progress()` into `TaskManager.progress()` so `TaskViewFooter` displays `"command timed out (10s), daemon healthy"`, `"Daemon Offline"`, or redacted PVM `errno` details verbatim.

## Consequences

- Sending lifecycle triggers across large batches is bounded by `10s` per hung guest rather than `30s`, and one hung guest OS no longer aborts healthy siblings.
- A dead or wedged `sballd` daemon is detected within `≤ 12s` (`10s` action trigger + `2s` liveness probe) when a worker encounters it. No new targets are submitted after detection; the at-most-`max_concurrency` in-flight targets settle, and later undispatched targets receive clear `– SKIPPED · Daemon Offline` rows.
- `OUTCOME_UNKNOWN` remains top-precedence in `OperationResult.state` whenever any target timed out while `sballd` was healthy, preventing silent blind retries.

## Validation

Covered by unit and Textual Pilot tests in `tests/unit/test_fast_trigger_and_liveness.py`, `tests/unit/test_pvm_adapter.py`, `tests/unit/test_config.py`, `tests/unit/test_operation_progress_sink.py`, and `tests/unit/test_task_manager.py`. Real-host `sballd` timing remains **PENDING MANUAL PVM VALIDATION**.

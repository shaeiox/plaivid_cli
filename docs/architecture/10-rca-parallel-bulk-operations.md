# RCA — Bulk Operation Concurrency and Target-Scoped Fault Isolation

**Status:** Audit complete; no implementation changes made  
**Date:** 2026-11-10  
**Scope:** VM and Desktop bulk dispatch, mutation barriers, sbell/PVM adapter, failure-scope policy, task status mapping  
**Review basis:** repository source, unit tests, ADRs, and `docs/SBELL-SABAD.md`. No live PVM host was contacted.

## Executive findings

1. **The current bulk executor is intentionally serial at two levels.** A shared, process-local `threading.Lock` (`OperationCoordinator._lane`) encloses the entire operation, and each executor's loop calls `_dispatch_one()` synchronously for one target before advancing. VM and Desktop operations share that lock. Removing only the loop's sequential behavior or only the lock is not a safe parallelization plan.
2. **The local Python invocation path appears structurally capable of concurrent calls, but PVM concurrency safety is not established.** `SbellClient` has no mutable per-call state, and each `ProcessRunner.run()` owns its child, pipes, captures, and drain threads. The protocol reference documents one-command-per-target request shapes and a UNIX-socket route to `sballd`, but neither it nor the gateway contract promises that concurrent requests on the same session are safe, ordered, or isolated. No local remote-`sabad` gateway implementation exists in this repository. Therefore ten simultaneous `vm/start` calls are **not yet validated as safe**.
3. **There is no repository-evidenced disk-failure errno or disk-specific `AppError` code.** `TARGET_SCOPED_ERRNOS` contains only `146` (documented as a VM-state rejection). The classifier treats every other or missing errno as session-scoped by default. A disk error represented by a different, unrecognized errno therefore aborts a batch. The actual disk errno must be captured from a version-matched, approved PVM run before naming or allowlisting it; do not guess it or reclassify generic `40`.
4. **`SKIPPED` has a narrow origin.** In operation execution, it is the task-board mapping of `OperationState.NOT_STARTED`, emitted only for targets remaining after a bulk stop condition. Stale plans do not produce `NOT_STARTED`: they throw before the loop and the TUI abandons the tasks as `REJECTED` instead.
5. **A parallel dispatcher must define what “abort” means.** Already-dispatched commands cannot be recalled. A bounded rolling window can stop *new scheduling* after a session/daemon failure, but it must collect and report all commands already in flight; only targets never submitted become `NOT_STARTED`/`SKIPPED`.

---

## 1. Concurrency architecture and bottleneck

### 1.1 Exact serialization points

**VM path — `plaivid_cli/application/operations/coordinator.py`:**

- `__init__` creates one plain `threading.Lock` at line 73 and passes the same lock to `DesktopOperationExecutor` (lines 75–76).
- `execute()` holds it around the entire `_execute_locked()` call (lines 140–153). This includes plan revalidation, mutation setup, every target dispatch, barrier teardown, and post-operation inventory reconciliation.
- `_execute_locked()` starts one `for record in targets` loop (line 199). It synchronously calls `_dispatch_one()` and waits for the call to return before the next iteration (line 217). The work ultimately reaches `PvmGateway.dispatch_action()` (line 309), the local adapter, `SbellClient.call()`, and blocking `ProcessRunner.run()`.

**Desktop path — `plaivid_cli/application/operations/desktop_executor.py`:**

- `execute()` uses the same injected `_lane` for the entire operation (lines 75–79).
- Its `for item in targets` loop likewise calls `_dispatch_one()` synchronously, one target at a time (lines 99–127; exact line numbers may move with edits).

Thus the lock serializes **operation groups against each other**, while the loops serialize **targets within each group**. The lock itself is not the only bulk bottleneck. Removing it without changing the loops leaves a sequential batch; changing the loops without controlling operation admission and collection barriers allows competing mutations to invalidate plans or interleave.

The Textual worker keeps this blocking path off the UI event loop; the issue is batch throughput, not a UI-thread deadlock. Existing ADR 0012 and ADR 0013 explicitly specify deterministic sequential execution. The requested behavior is therefore a deliberate architecture/policy change and those records should be amended before implementation.

### 1.2 Mutation-generation barrier constraints

The collection barrier is batch-scoped today:

- `begin_mutation()` validates the plan's expected inventory/desktop generation and freshness under the collection lock, then increments generation/epoch and marks the target UUIDs mutating (`application/collection/coordinator.py`, approximately lines 94–165).
- `end_mutation()` increments generation again, clears the target set, marks the relevant inventory stale, and eventually allows pending reads to proceed (approximately lines 167–190).
- The plan is checked both against a newly created plan and immediately at `begin_mutation`; a stale plan raises before any target dispatch.

**Safe initial parallelization boundary:** retain a single operation-group admission/lane and call `begin_mutation()` exactly once for the full immutable target UUID set. Parallelize only the per-target trigger calls *inside that one barrier*. Await all submitted work before one `end_mutation()`, and then reconcile once. Do not have each worker independently open/close a barrier: that would churn the generation while sibling workers are still starting, cause stale-plan races, and could publish or admit reads at the wrong point.

Preserve the same checks for target identity, full/fresh bulk inventory, action, order, and plan generation. Keep VM and Desktop operations serialized against one another in the first phase unless a separate cross-operation concurrency design proves safe. `close()` currently sets the closing event and waits for the shared lane; its shutdown contract must continue to wait for the bounded worker group and child processes.

### 1.3 sbell / `sballd` concurrency evidence

| Layer | Evidence in repository | What it establishes (and does not establish) |
|---|---|---|
| `PvmGateway` (`application/ports.py`) | Synchronous `dispatch_action(token, action, uuid)` method; no concurrency/thread-safety clause | A single call contract only; no guarantee for simultaneous calls or session sharing. |
| `LocalPvmAdapter` | Calls `SbellClient` for each action; no dispatch mutex | Adapter does not serialize individual command calls itself. This is not proof the daemon is safe. |
| `SbellClient` (`infrastructure/pvm/sbell.py`) | Each `call()` builds local argv, runs it, parses its own result; no mutable request state | The wrapper is structurally reentrant if its runner is safe. It does not document `sbell` socket behavior under concurrent processes. |
| `ProcessRunner` (`infrastructure/process.py`) | Each run creates a separate `Popen`, pipes, `_Capture` objects and drain threads; shared configuration is read-only during `run()` | Python subprocess/capture bookkeeping is per invocation. This says nothing about concurrent requests inside `sballd` or PVM state. |
| `docs/SBELL-SABAD.md` | Describes `sbell` as communicating with `sballd` over a UNIX socket/framed XML; each VM lifecycle command is a separate request with a target key | Confirms the request shape is per target; does not specify request serialization, daemon reentrancy, same-token parallelism, ordering, idempotency, or command side-effect isolation. |
| Remote path | Docs describe `sabad` as an HTTP API; no remote adapter/client implementation is present under `infrastructure/pvm` | Cannot audit remote HTTP client concurrency from this checkout. Server-side semantics remain unknown. |

**Conclusion:** the subprocess layer is plausibly callable from threads, but the end-to-end remote daemon contract is unproven. Do not claim “sbell/sballd safely handles 10 simultaneous starts” from the current source. Establish that with the PVM owner and controlled, version-matched validation (suggested rollout in §4).

### 1.4 Recommended concurrency model

Use a **bounded rolling worker window**, initially a small configurable limit (for example, 2–3 in-flight targets, subject to PVM-owner approval), rather than firing every target into an unbounded `ThreadPoolExecutor`.

- Maintain one supervisor for the batch. It owns the plan order, outstanding futures, stop/circuit-breaker state, and result aggregation.
- Submit per-target calls through a bounded executor; report each target `RUNNING` immediately before its actual dispatch, not when the entire batch is admitted.
- Associate every future with its UUID and store each result by UUID; return final outcomes in the deterministic resolved UUID order even though completion order is nondeterministic.
- On a target-scoped disk/state rejection or a healthy-daemon timeout, continue filling the window according to policy. A timeout stays `OUTCOME_UNKNOWN`; never retry it automatically.
- On a session/contract/daemon failure, stop submitting new targets, allow already-submitted calls to settle under their bounded timeouts, preserve their actual outcomes, and mark only never-submitted UUIDs `NOT_STARTED` with the stop reason.
- Use a thread-safe callback/TaskManager path for progress. `TaskManager` uses a lock and is designed for worker updates, but every target's transitions need race/order tests (especially terminal states and operation finish).
- Make shutdown wait for the worker pool and reaped child processes, with no orphaned futures or target rows left queued.

This changes the semantics of sequential fail-fast: a failure can be discovered while other targets are already in flight. The policy and UI must explicitly distinguish “not scheduled,” “dispatched/in flight,” “failed,” and “unknown”; it is impossible to promise zero additional dispatches after a failure that arrives concurrently.

---

## 2. Disk failure root cause and classification

### 2.1 Existing failure pipeline

`SbellClient.call()` parses the XML failure envelope and retains `description/errno` and `description/what` (`infrastructure/pvm/sbell.py`, lines 94–111). `LocalPvmAdapter.dispatch_action()` returns that information as a `PvmReply`. The coordinator turns a `status == "failed"` reply into a `TargetOutcome(FAILED, dispatched=True, errno=reply.errno)` (`application/operations/coordinator.py`, approximately lines 344–363).

`domain/policies.py` currently defines:

```text
TARGET_SCOPED_ERRNOS = {"146"}
```

The protocol reference identifies errno 146 as “VM '<name>' is ...”, a VM-state error from `mid=vm` (for example, attempting start on a running VM). A failed reply with errno 146 can continue only when the daemon liveness check succeeds. `classify_failure()` checks membership in the target set and otherwise returns its default, `FailureScope.SESSION`. `is_target_scoped_error()` also requires the command to have been dispatched and the daemon to be alive; an action timeout is separately target-scoped when the daemon is healthy.

Consequently, an errno that identifies a **single VM's bad/corrupt/unavailable disk** but is not `146` is not recognized as target scoped. It falls through to session scope, so `outcome_stops_batch()` returns true and the executor records every later target as `NOT_STARTED`. This is conservative fail-closed behavior, but over-broad for a verified per-VM storage failure.

### 2.2 Exact errno/code answer and evidence gap

The repository does **not** document a disk-failure errno, disk-specific `AppError` code, or captured failure fixture. `docs/SBELL-SABAD.md` lists errno 39, 40, 106, 107, 108, 137, 146, and 185; it does not describe a disk error. The only target-scoped errno today is 146. There is no basis in this checkout to identify a correct numeric disk errno.

Therefore the actionable finding is:

- **Do not add a guessed number.** Obtain an authorized, version-matched PVM response fixture for a disposable VM disk-failure case, including `mid`, `errno`, `what`, action, PVM version, and whether the daemon remains responsive.
- If the failure is a PVM `<status>failed</status>` response with a verified target-specific errno, add that exact errno to `TARGET_SCOPED_ERRNOS` and test its continuation. Keep it conditional on `dispatched=True` and healthy daemon, just like errno 146.
- If PVM reports it as an application error rather than an errno-bearing response, define and classify a **specific, structured target-scoped error code** at the adapter/domain boundary. Do not special-case generic `ErrorKind.PVM_RESPONSE`, `PROCESS`, `PVM_COMMAND_TIMEOUT`, or a human-readable message: those may represent session/wire failures or an unknown side effect.
- `errno 40` is documented as a malformed parameter/key extraction failure before object resolution and is currently session/contract scoped. It is not a defensible proxy for disk failure.

The likely architectural root cause is not that “disk errors are inherently session errors,” but that the allowlist recognizes only errno 146 and defaults unknown error numbers/codes to session scope. Confirm the actual PVM failure contract before changing that policy.

---

## 3. Exact `SKIPPED` / bulk-abort conditions

### 3.1 State mapping and emission point

- `OperationState.NOT_STARTED` maps to `TaskStatus.SKIPPED` in `domain/models/tasks.py`.
- In both VM and Desktop executors, `NOT_STARTED` is appended and reported only for each remaining loop target after `stop_reason` has been set. `TaskManager.progress()` converts it to `SKIPPED`; final `TaskManager.finish()` also maps an outcome's `NOT_STARTED` to `SKIPPED`.
- This loop behavior is conditional on `is_bulk=True`. A single-target request has no tail to skip.
- Ordinary admission refusals, explicit pre-dispatch cancellation, stale plans, and task abandonment do not currently create `NOT_STARTED` outcomes and therefore are **not** `SKIPPED` (they normally become `REJECTED`).

### 3.2 Conditions that currently set a stop reason (and skip the undispatched tail)

The common policy is `outcome_stops_batch()` in `domain/policies.py`; the current `stop_states` are `FAILED`, `REJECTED`, and `OUTCOME_UNKNOWN`. A bulk abort occurs when a stop-state outcome is **not** recognized as target-scoped, or when daemon liveness is false.

- **Daemon offline/unresponsive:** after a failed/unknown result or action timeout, `_dispatch_one()` probes `is_daemon_alive()`. If it returns false, the outcome is converted to `FAILED` with `code="DAEMON_OFFLINE"`. The batch stop reason is `Daemon Offline`; remaining targets get `NOT_STARTED`/`SKIPPED` with that message. The executor avoids the post-loop read reconciliation in this case.
- **Session/authorization/contract errno:** any dispatched failure errno other than the target-scoped allowlist is session-scoped and stops the batch. The explicitly documented set is 39 (unauthorized/expired session), 40 (permission/malformed params), 106 (bad module), 107 (bad command), 108 (local sbell socket permission), 137 (bad credentials), and 185 (session cap). In practice, the classifier's complement rule means any other unrecognized or missing errno also stops.
- **Target-scoped-looking errno without proven isolation:** errno 146 only continues if it was dispatched and the daemon liveness probe is healthy. If the daemon is offline, the offline condition wins and the tail is skipped. Any future target errno must satisfy the same gates.
- **Per-target timeout with daemon offline:** a `PVM_COMMAND_TIMEOUT` initially becomes an uncertain result. If the liveness probe is false, it is rewritten to daemon-offline `FAILED`, aborting the tail. With a healthy daemon the timeout remains `OUTCOME_UNKNOWN` but is specifically target-scoped, so the loop continues; it does **not** itself create skipped rows.
- **Local process could not start:** `PROCESS_START_FAILED` yields `FAILED` with `dispatched=False`. It cannot be target-scoped, so the batch stops and remaining targets are skipped.
- **Pre-dispatch policy rejection during the loop:** a policy `AppError` becomes `REJECTED`, `dispatched=False`. The classifier rejects target scope for undispatched outcomes, so a bulk tail is skipped.
- **Other AppError / transport failure after dispatch:** generic non-policy/non-spawn `AppError` is represented as `OUTCOME_UNKNOWN`, and an arbitrary exception becomes `OUTCOME_UNKNOWN`. A non-timeout unknown is not target-scoped and stops the bulk. Examples include transport interruption, invalid/missing response details, and unrecognized reply status.
- **PVM failure with an unrecognized errno:** it is a `FAILED` target outcome but defaults to session scope; the remainder is skipped. This is the path implicated by a disk-specific errno not currently allowlisted.

In all these cases, the triggering target is recorded as its own `FAILED`, `REJECTED`, or `OUTCOME_UNKNOWN` result; only later, not-yet-dispatched targets receive `NOT_STARTED`.

### 3.3 Similar symptoms that do not currently map to `SKIPPED`

- **Stale/mismatched plan or changed/expired inventory:** plan comparison fails or `begin_mutation()` raises `CollectionSuperseded` before entering the loop. The operation raises `AppError` (`OPERATION_PLAN_STALE` for the VM freshness-barrier case); the TUI calls `TaskManager.abandon()`, which marks admitted rows `REJECTED`. No executor-produced `NOT_STARTED` result exists.
- **Bulk preflight/selection validation failure:** no operation batch enters the dispatch loop. A TUI error is shown; no `NOT_STARTED`-to-`SKIPPED` mapping occurs.
- **Admission `BUSY`, `CONFLICT`, or `DUPLICATE`:** request is refused before execution; no per-target task outcomes are generated for that request.
- **Explicit cancellation before any dispatch:** `cancel()` creates `CANCELLED_BEFORE_DISPATCH`, which maps to `REJECTED`, not `SKIPPED`.
- **Session ends before a worker starts / worker is abandoned:** `TaskManager.abandon()` assigns `REJECTED`, not `SKIPPED`.
- **Target-scoped errno 146 with a healthy daemon, or a timeout with a healthy daemon:** both continue; no tail is skipped solely because of those results.

---

## 4. Implementation plan (proposal; no code changed)

### Phase 0 — policy and contract decisions

1. Amend ADR 0012/0013 (and relevant validation checklist) to replace “sequential” with the approved bounded concurrency model and define fail-fast behavior in the presence of already-in-flight requests.
2. Ask the PVM owner whether `sbell`/`sballd` and any `sabad` deployment support concurrent lifecycle requests using one authenticated session; request supported concurrency limits, ordering/transaction guarantees, response correlation, and load expectations.
3. Capture the disk-failure response on an approved disposable VM and record PVM version, `mid`, `errno`, `what`, action, daemon-health observation, and authoritative per-VM effect. Decide whether it is a documented target errno or a specific structured error code. Do not infer from prose alone.
4. Set an initial concurrency cap and rollout/kill switch; no unbounded pool and no automatic retry.

### Phase 1 — isolate a batch supervisor from target calls

5. Refactor shared VM/Desktop execution policy into one supervisor abstraction or helper to prevent duplicated loops drifting. It should own plan validation, deterministic order, target outcomes, stop reason, progress, and aggregate result.
6. Preserve one operation-level lane and one `begin_mutation(full_target_set)` / `end_mutation(full_target_set)` pair around the complete batch. Revalidate the immutable plan and begin the barrier before submitting work. Keep reconciliation after all in-flight work settles.
7. Add a bounded executor/rolling dispatch window. Submit only up to the configured maximum; when a future completes, classify it before deciding whether to submit another. For a stop-scoped error, stop future submissions, wait for already-submitted calls, and mark only the undispatched tail `NOT_STARTED`.
8. Emit per-target progress at actual start and completion. Store outcomes keyed by UUID; present final results in planned order while allowing live completion events to arrive in completion order. Ensure callbacks and task rows remain safe under concurrent completion.
9. Preserve `OUTCOME_UNKNOWN` for any ambiguous post-dispatch result, never retry automatically, and keep failure/success aggregates honest. Ensure terminal task updates cannot be overwritten by late progress.

### Phase 2 — structured failure isolation

10. Add the validated disk-specific errno to `TARGET_SCOPED_ERRNOS` only if the PVM fixture proves it belongs to the target and daemon/session remain healthy. If it is a distinct `AppError`, add an explicit structured code-to-scope mapping instead. Keep unknown errors fail-closed.
11. Retain current liveness behavior: daemon-offline overrides a target errno; healthy-daemon action timeout remains target-scoped but `OUTCOME_UNKNOWN`; session, process-start, policy/undispatched, and non-timeout transport failures stop scheduling.
12. Make the stop reason observable on every undispatched target and distinguish these from commands already submitted when the stop condition was observed.

### Phase 3 — test and host validation

13. Unit-test the actual max-in-flight ceiling, no dispatch beyond the rolling window after a stop, outcomes for already-in-flight requests, mixed success/disk-failure continuation, unknown timeout behavior, per-UUID progress ordering, deterministic final result ordering, and no leaked worker/process on shutdown.
14. Run identical policy tests against VM and Desktop paths. Add stale-plan tests proving no dispatch begins and preserving the current `REJECTED` (not `SKIPPED`) semantics.
15. Validate on an owner-approved, version-matched disposable PVM host: first two concurrent targets, then gradually larger bounded counts; verify all responses correlate to the right UUID, no cross-target contamination, daemon/session health, state and disk effects independently, logs/resource pressure, and behavior when one target fails while others are in flight. Increase the cap only with recorded evidence.
16. Keep production concurrency disabled or at one until those tests and owner approval pass. The repository's synthetic tests alone cannot establish `sballd` concurrency safety.

---

## 5. Risk/decision summary

| Risk | Why it matters | Control |
|---|---|---|
| Daemon request handling is not concurrency-safe | Current protocol docs do not promise thread-safe same-session dispatch | Owner confirmation and staged live validation; low cap/feature gate |
| Session failure discovered after other commands start | Parallel work cannot be recalled and may mutate additional VMs | Rolling window; stop new submissions only; accurately report in-flight outcomes |
| Incorrect errno classified as target-local | Could continue hammering a broken session or misreport a system failure | Require captured versioned response; unknown codes remain fail-closed |
| Generation barrier closed too early | Affected reads could publish during mutations or queued plans become stale | One operation-scoped barrier held through every future and reconciliation boundary |
| Task status races | A late progress event could conflict with a final/skip state | Per-target state machine tests and terminal-state guards |
| Nondeterministic completion order | UI and CLI output can appear to reorder the selected target list | UUID-keyed future map; planned-order final result, explicit live order semantics |

**Bottom line:** the sequential behavior is directly caused by the shared operation lock plus synchronous per-target loops and is also the current ADR policy. The disk failure is being treated as session-scoped because only errno 146 is target-scoped and all unknown errno values fail closed; the specific disk errno is not documented in this repository. The safe direction is bounded intra-batch concurrency under one unchanged plan/barrier, backed by PVM concurrency evidence and a verified disk-error classification—not simply deleting `_lane` or launching every selected VM at once.

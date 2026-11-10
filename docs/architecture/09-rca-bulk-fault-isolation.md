# RCA — Bulk action fault isolation (stop-on-first-error)

**Status:** Original sequential-engine RCA; scoped error isolation was implemented in §10. Bounded parallel dispatch was implemented on 2026-11-10; its active contract supersedes the sequential-loop descriptions below (see ADRs 0007, 0012, and 0013 and `docs/architecture/10-rca-parallel-bulk-operations.md`).
**Date:** 2026-11-08
**Scope:** `application/operations/coordinator.py`, `application/operations/desktop_executor.py`,
`infrastructure/pvm/`, `docs/SBELL-SABAD.md`, ADR 0012/0013
**Verdict up front:** the behaviour you describe is real, but it is **not a defect**.
It is an explicit, documented, test-pinned safety policy. Changing it is a
**policy reversal with genuine blast risk**, not a bug fix. Details and a safe
path are in §6–§8.

---

## 1. Executive summary

| Question asked | Finding |
| --- | --- |
| Does the loop break early? | **Yes.** One flag, `stop_bulk`, in each executor. |
| Is it caused by an unhandled exception? | **No.** Every dispatch path is already exception-trapped and converted to a `TargetOutcome`; the loop cannot escape via an exception (§4). |
| Is there a hardcoded stop-on-first policy? | **Yes, and it is deliberate.** ADR 0012 line 37 and ADR 0013 line 45 mandate it verbatim. |
| Can we just flip the flag? | **No.** Three concrete hazards, one of which can *silently lose an operator's start request* (§6). |

The reported symptom is accurate. The proposed expected behaviour is a product
decision that contradicts two accepted ADRs and four tests.

---

## 2. Where the loop stops — exact locations

### 2.1 VM path — `OperationCoordinator._execute_locked`

`application/operations/coordinator.py:203-223`

```python
203:        stop_bulk = False
204:        try:
205:            for record in targets:
206:                if stop_bulk:
207:                    outcomes.append(
208:                        TargetOutcome(
209:                            record.uuid,
210:                            OperationState.NOT_STARTED,
211:                            "not dispatched after an earlier definite failure or unknown outcome",
212:                        )
213:                    )
214:                    _report(on_progress, record.uuid, OperationState.NOT_STARTED)
215:                    continue
216:                outcomes.append(self._dispatch_one(token, action, record, on_progress=on_progress))
217:                outcome = outcomes[-1]
218:                if outcome.state in {
219:                    OperationState.FAILED,
220:                    OperationState.REJECTED,
221:                    OperationState.OUTCOME_UNKNOWN,
222:                }:
223:                    stop_bulk = is_bulk          # ← the only thing that aborts a batch
```

### 2.2 VDI path — `DesktopOperationExecutor.execute`

`application/operations/desktop_executor.py:110-130` — a line-for-line duplicate:

```python
110:            stop_bulk = False
111:            try:
112:                for item in targets:
113:                    if stop_bulk:
114:                        outcomes.append(
115:                            TargetOutcome(
116:                                item.uuid,
117:                                OperationState.NOT_STARTED,
118:                                "not dispatched after earlier failure or unknown outcome",
119:                            )
120:                        )
121:                        _report(on_progress, item.uuid, OperationState.NOT_STARTED)
122:                        continue
123:                    outcome = self._dispatch_one(token, action, item, on_progress=on_progress)
124:                    outcomes.append(outcome)
125:                    if outcome.state in {
126:                        OperationState.FAILED,
127:                        OperationState.REJECTED,
128:                        OperationState.OUTCOME_UNKNOWN,
129:                    }:
130:                        stop_bulk = is_bulk          # ← same policy, duplicated
```

**Mechanics:** `stop_bulk` is set only when `is_bulk` is true, so a single-target
action is unaffected. Once set, every remaining iteration takes the `continue`
branch, so no further `dispatch_action` call is made and the target is recorded
`NOT_STARTED`. The loop is never *broken* via `break`; it drains the remaining
targets purely to emit `NOT_STARTED` rows — which is why the footer shows a full
roster rather than a truncated one.

**Duplication note:** the two blocks are identical in intent but separately
maintained. Any fix must land in both, or they will diverge silently.

---

## 3. The top-level abort path (a different mechanism)

Before any per-target loop runs, two guards raise **out of the whole operation**:

`coordinator.py:196-202` (VM) and `desktop_executor.py:103-107` (VDI):

```python
except CollectionSuperseded as exc:
    raise AppError(
        ErrorKind.POLICY,
        "inventory changed or expired immediately before dispatch; review a new plan",
        code="OPERATION_PLAN_STALE",
    ) from exc
```

This is the `begin_mutation` freshness barrier. It is **batch-scoped by design**
and must *not* be relaxed (see §6.2) — relaxing it would dispatch against
evidence the operator never reviewed. Worth knowing because it produces a
similar-looking "nothing else ran" symptom but for a legitimate, unrelated
reason.

---

## 4. `sbell` gateway and exception audit — no unhandled exception aborts the loop

Traced end to end. **Every** failure mode is already converted into a typed
`TargetOutcome`; nothing propagates to the loop.

| Layer | Failure | Handling | Escapes to loop? |
| --- | --- | --- | --- |
| `ProcessRunner.run` | `OSError` on spawn | → `ProcessStartError` (`process.py:131-132`) | No |
| `ProcessRunner.run` | timeout / non-zero exit | → `ProcessError` | No |
| `SbellClient.call` | argv/credential policy | → `AppError(POLICY)` | No |
| `LocalPvmAdapter._call` | `ProcessStartError` | → `AppError(PROCESS, code=PROCESS_START_FAILED)` (`local.py:83-84`) | No |
| `LocalPvmAdapter._call` | `ProcessError` | → `AppError(PROCESS, code=PVM_PROCESS_ERROR)` (`local.py:85-86`) | No |
| `LocalPvmAdapter.dispatch_action` | `<status>failed</status>` | → `PvmReply(status="failed", errno, message)` — **no raise** (`local.py:264-266`) | No |
| `OperationCoordinator._dispatch_outcome` | `AppError(POLICY)` | → `REJECTED`, `dispatched=False` (`coordinator.py:263-267`) | No |
| `OperationCoordinator._dispatch_outcome` | `AppError(PROCESS, PROCESS_START_FAILED)` | → `FAILED`, `dispatched=False` (`coordinator.py:268-270`) | No |
| `OperationCoordinator._dispatch_outcome` | any other `AppError` | → `OUTCOME_UNKNOWN`, `dispatched=True` (`coordinator.py:271-273`) | No |
| `OperationCoordinator._dispatch_outcome` | bare `Exception` | → `OUTCOME_UNKNOWN`, `dispatched=True` (`coordinator.py:275-281`) | No |
| `OperationCoordinator._dispatch_outcome` | `status == "success"` | → `SUCCEEDED` (`coordinator.py:284-289`) | No |
| `OperationCoordinator._dispatch_outcome` | `status == "failed"` | → `FAILED` (`coordinator.py:290-296`) | No |
| `OperationCoordinator._dispatch_outcome` | any other status | → `OUTCOME_UNKNOWN` (`coordinator.py:297-303`) | No |

**Conclusion for task 2:** the outer loop never aborts because of an exception.
The abort is purely the `stop_bulk` assignment at `coordinator.py:223` /
`desktop_executor.py:130`. There is no missing `try/except` to add. Any "fix the
error handling" framing is a misdiagnosis of this specific symptom.

One nuance worth recording: `on_progress` sink exceptions are already swallowed
by `_report()` (`coordinator.py:37-42`), so a TUI bug cannot break a bulk either.
That boundary is correct and should be preserved.

---

## 5. Outcome taxonomy and policy audit

### 5.1 It is policy, stated verbatim in two ADRs

**ADR 0012 — Security and Mutation Safety Policy, line 37:**

> "Process the deterministic resolved UUID order **sequentially. Stop on the first
> definite failure, rejection, or `OUTCOME_UNKNOWN`; mark every remaining target
> `NOT_STARTED`.** A positive-looking response without a verified acceptance
> contract is `OUTCOME_UNKNOWN` and stops the sequence. `COMMAND_ACCEPTED_UNCONFIRMED`
> may be used only after owner evidence proves acceptance; **continuation policy
> must then be explicitly approved**. No automatic retry is permitted."

**ADR 0013 — Error Taxonomy, line 45:**

> "The implementation policy is **sequential and fail-closed**: stop on the first
> definite failure, rejection, or `OUTCOME_UNKNOWN`; every remaining resolved
> target after a stop is `NOT_STARTED`."

Both are marked *Accepted/Implemented*, not provisional. The code is a faithful
implementation of the written policy — the audit finds **no drift** between
specification and implementation.

### 5.2 `operations/results.py` contains no abort logic

`results.py` is pure reporting. `aggregate_state()` (`results.py:8-31`) applies a
precedence order to the outcome tuple *after* the loop, and `_aggregate_message()`
(`results.py:33-49`) only formats counts. Neither can influence the loop. The
`NOT_STARTED` → `PARTIAL` mapping at `results.py:28-29` is what makes an aborted
bulk report as `PARTIAL` rather than `FAILED`.

### 5.3 The behaviour is protected by four tests

| Test | Pins |
| --- | --- |
| `test_application_operations.py:255-267` `…stays_unknown_and_stops_bulk` | asserts `targets[1:]` are all `NOT_STARTED` and only one dispatch occurred |
| `test_virtual_desktops.py:250` | asserts `[FAILED, NOT_STARTED]` |
| `test_virtual_desktops.py:324` | asserts `[OUTCOME_UNKNOWN, NOT_STARTED]` |
| `test_operation_progress_sink.py:112,139` | asserts the *progress sink* reports `NOT_STARTED` for the tail |

These are not incidental assertions; they are the executable form of the ADR.
Flipping the flag requires rewriting all four, which is the signal that this is a
behavioural reversal.

### 5.4 Why the policy exists — and where it is over-broad

The `sbell` documentation supplies the reasoning, and also reveals the flaw in
applying it uniformly.

`docs/SBELL-SABAD.md` §3 documents one request per command:

| Command | params body |
| --- | --- |
| `vm/stop` | `<vm_key>UUID</vm_key>` (bare, **no** `<params>`) |
| `vm/kill` | `<vm_key>UUID</vm_key>` |
| `vm/reset` | `<vm_key>UUID</vm_key>` |
| `vm/pause` | `<vm_key>UUID</vm_key>` |
| `vm/resume` | `<vm_key>UUID</vm_key>` |
| `vm/start` | `<vm_start>…</vm_start>` |

Confirmed by `_action_params(action, uuid)` (`adapter/local.py:264-266`) and
ADR 0012: *"Initially execute one target per supported action invocation; no PVM
bulk command/idempotency guarantee is assumed."*

Because there is no batch transaction, **batches are already isolated at the PVM
level**. All targets share exactly one thing: the session token. So the policy is
only defensible for failures that indicate the *session or the wire is dead*, and
is over-broad for failures that are *target-scoped*.

The errno catalogue in §3 lets us separate them:

| errno | `what` | Scope | Continue? |
| --- | --- | --- | --- |
| 146 | `VM '<name>' is …` (e.g. start on a running VM), `mid=vm` | **Target** — PVM answered cleanly about this VM | **Yes.** This is the common case in a bulk stop: some VMs are already stopped. |
| 39 | `UnAuthorized` | **Session** | No — every remaining call fails identically. |
| 185 | `sessions exceeds the threshold` | **Session** | No — needs eviction (`SBELL-SABAD.md` §6). |
| 137 | `Username/Password is not correct` | **Credential** | No. |
| 40 | `Permission denied` (usually malformed params) | **Contract** | No — the request shape is wrong for every target. |
| 106 / 107 | Bad module / bad command | **Contract** | No. |
| 108 | UNIX socket permission | **Host** | No. |
| `PROCESS_START_FAILED` | executable/sudo unavailable, `dispatched=False` | **Host** | No — nothing was sent. |
| `OUTCOME_UNKNOWN` | transport died mid-call | **Indeterminate** | Debatable — see §6.3. |

This scoping is the substance of the RCA: **the current code collapses
target-scoped and session-scoped failures into one decision**, and that
collapsing — not the existence of a stop policy — is the real defect.

---

## 6. Fix strategy — three hazards that rule out the naive change

The smallest change that satisfies the literal request is deleting the
`stop_bulk` assignment at the two lines named in §2. **Do not do that.** It
introduces these:

### 6.1 Hazard A (most serious): a session-agnostic continue can strand an operator's request

If the loop continues past a `REJECTED` caused by `OPERATION_PLAN_STALE`, or past
`NOT_STARTED` rows left over from an earlier partial run, the operator pressed
**START** and the VM never started — with the board showing a tidy per-target
list that suggests each target was individually considered. For `KILL`/`RESET`
a stranded request is an availability incident: the operator believes a wedged
VM is being killed.

Note `_begin_action`/`desktop_action_requested` do **not** filter out targets
already claimed by another in-flight operation, so `REJECTED` rows are reachable
in ordinary use — this is not hypothetical.

### 6.2 Hazard B: the freshness barrier is correctly batch-scoped

`begin_mutation` is taken once for the whole batch (`coordinator.py:180-186`).
While it is held, `CollectionCoordinator.begin_mutation` bumps `_generation`
(`collection/coordinator.py:155`). If the loop continues to target C after
target A failed, C is dispatched while the batch barrier is still open — that is
fine — but the *aggrieved* case is `OPERATION_PLAN_STALE` from the guard in §3,
which is deliberately all-or-nothing. A fix must **not** touch that guard.

### 6.3 Hazard C: `OUTCOME_UNKNOWN` continuation can double-dispatch

If a transport failure leaves the VM in an unknown state and the operator later
retries the same target, the app cannot distinguish "never arrived" from
"arrived and applied". Continuing *within* the batch is safe (different targets),
but the aggregate must keep `OUTCOME_UNKNOWN` prominent so nobody re-runs the
batch blindly. `aggregate_state` already gives `OUTCOME_UNKNOWN` top precedence
(`results.py:13-14`) — that must be preserved.

### 6.4 Proposed strategy: scoped continuation (recommended)

Replace the single boolean with a **stop reason** classifier, applied per
outcome:

```
for each target:
    if stop_reason is not None:
        record NOT_STARTED(reason=stop_reason); continue
    outcome = dispatch_one(...)
    record outcome
    if outcome is target_scoped_failure:      # errno 146, plain REJECTED from PVM
        continue                               # ← isolation achieved
    if outcome is session_or_contract_failure: # 39/40/106/107/108/137/185, POLICY, PROCESS_START_FAILED
        stop_reason = "session/contract failure stopped the batch"
```

Two properties this preserves that the naive fix loses:
1. target-scoped failures continue — the requested isolation;
2. session-scoped failures still fail fast, so we do not hammer a dead token
   `n` times and we do not leave a stranded-request illusion.

This requires threading the `errno` into `TargetOutcome`. Today
`_dispatch_outcome` folds errno into a message string only
(`coordinator.py:290-296`), so the classifier cannot see it — **this is the single
most important missing piece of information in the current design.**

### 6.5 Exact edit points (for the follow-up change, not now)

| # | File / lines | Change |
| --- | --- | --- |
| 1 | `domain/models/operations.py:38-42` `TargetOutcome` | add `errno: str \| None = None` so scope is classifiable |
| 2 | `domain/models/tasks.py` / `enums.py` | add a `StopScope` (or reuse `ErrorKind`) enum: `TARGET` / `SESSION` / `CONTRACT` / `HOST` / `INDETERMINATE` |
| 3 | `coordinator.py:290-296` | carry `reply.errno` into the outcome instead of only formatting it |
| 4 | `coordinator.py:263-273` | classify `AppError` into a scope alongside the state |
| 5 | **`coordinator.py:203, 218-223`** | replace `stop_bulk` bool with `stop_scope`; continue on `TARGET` |
| 6 | **`desktop_executor.py:110, 125-130`** | same change — duplicated policy must stay in lockstep |
| 7 | `results.py:8-31` | keep precedence; confirm a mixed batch yields `PARTIAL`, not `FAILED` |
| 8 | ADR 0012 line 37, ADR 0013 line 45 | **amend** to describe scoped continuation; supersede both lines |
| 9 | tests at §5.3, plus new `test_bulk_continues_after_target_scoped_failure` | rewrite assertions to the new contract |

### 6.6 Cheaper alternative if a full classifier is unwanted

If product wants the literal behaviour with minimum machinery, gate the
continuation on the existing `dispatched` flag plus `errno`:

- continue when `dispatched is True` and `errno` is a documented target-state
  error (146 only, today);
- stop otherwise.

This is a ~10-line change in two places and needs no new enum, but it is less
expressive and will need revisiting when more target-scoped errnos are verified.

Whatever is chosen, the ADRs must be amended **first** — the code currently
matches the written policy, and shipping code that contradicts its own ADR is
how this class of defect recurs.

---

## 7. Risk register for the change

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Continuing past a dead session hammers PVM `n` times | Medium | Session-scoped stop list (§5.4) |
| Operator's request stranded while board shows a tidy list | **High** | Never continue on `OPERATION_PLAN_STALE`; distinguish "attempted" from "skipped" visibly |
| `OUTCOME_UNKNOWN` target re-run blindly later | High | Preserve `OUTCOME_UNKNOWN` precedence in `aggregate_state` |
| Two duplicated loops drift apart | Medium | Change both in one commit; add a test asserting VM and VDI paths behave identically |
| ADR/code divergence | Medium | Amend ADR 0012/0013 before merging code |
| Assume errno 146 means "not executed" | Medium | `SBELL-SABAD.md` does not verify PVM-side effect; keep outcome honest, do not claim `FAILED` proves non-execution |

---

## 8. What is *not* claimed

- No live PVM host was contacted. The errno 146 scoping is inferred from
  `SBELL-SABAD.md` §3, not from a captured bulk run.
- Whether PVM applies a partially-failed batch atomically is **unknown and not
  documented**; the analysis assumes per-request independence, which the
  one-target-per-command request shape supports but does not prove.
- Whether continuing after `OUTCOME_UNKNOWN` is safe depends on PVM-side
  idempotency, which ADR 0012 explicitly says **must not be assumed**.

## 9. Recommendation

1. **Treat this as a policy change, not a bug fix.** Open a decision record
   amending ADR 0012 line 37 and ADR 0013 line 45.
2. **Implement scoped continuation (§6.4)**, not a bare flag flip. The
   target-scoped vs session-scoped split is what makes batch isolation safe.
3. **Do the plumbing first** — `TargetOutcome.errno` (§6.5 item 1) — because
   without it the classifier is guessing from message strings.
4. **Keep the `OPERATION_PLAN_STALE` guard all-or-nothing.** It protects the
   operator's reviewed evidence, not the batch loop.

---

## 10. Implementation record

Scoped continuation was approved and implemented.

| Step | Change |
| --- | --- |
| ADRs | ADR 0012 line 37 and ADR 0013 line 45 rewritten to describe target-scoped continuation, session-scoped abort, and the fail-closed rule for unrecognised `errno`. ADR 0013 gained a scope/behaviour/`NOT_STARTED` reporting table. |
| Error plumbing | `AppError.errno` added (default `None`, so all existing call sites are unchanged); populated from the PVM envelope in `LocalPvmAdapter._require_read` and `login`. `TargetOutcome.errno` added and populated from both the `PvmReply` and the `AppError` paths. |
| Classifier | `domain/policies.py`: `FailureScope`, `TARGET_SCOPED_ERRNOS` (`146`), `SESSION_SCOPED_ERRNOS` (`39/40/106/107/108/137/185`), `classify_failure()`, `is_target_scoped_error()`, `outcome_stops_batch()`, `batch_stop_reason()`, `bulk_must_stop()`. Pure domain functions; no I/O. |
| Loops | `stop_bulk: bool` replaced by `stop_reason: str \| None` in both `coordinator.py` and `desktop_executor.py`, delegating to `outcome_stops_batch()` and `batch_stop_reason()`. |
| Reporting | `NOT_STARTED` targets now carry the stop reason instead of a fixed sentence, so an operator can distinguish "batch aborted by a session failure" from "batch aborted by an unknown outcome". |
| Tests | `test_failure_scope_policy.py` added (31 tests); `test_application_operations.py`, `test_virtual_desktops.py`, and `test_operation_progress_sink.py` updated to cover both target-scoped continuation and session-scoped batch aborts. |

### Deliberate decisions

- **`is_target_scoped_error` requires `dispatched=True`.** A `PROCESS_START_FAILED` that happens to carry an
  `errno` is still a host failure, not a target-state failure.
- **The classifier fails closed.** Only errnos on the target-scoped list continue. Everything else — including a
  brand-new errno nobody has classified — stops the batch.
- **`OUTCOME_UNKNOWN` still aborts.** The RCA flagged this as Hazard C; the approved scope covered target-state
  rejections only, so continuation past an unverified outcome remains blocked pending an owner decision.
- **The `OPERATION_PLAN_STALE` guard is untouched.** It stays all-or-nothing for the whole batch.

### Known limitation

The repository still does not retain the `<mid>` element from the `sbell` failure envelope
(`SBELL-SABAD.md` §3 identifies `mid=vm` vs `mid=actrepo`), so scope is inferred from `errno` alone. If a future
capture shows the same errno raised by both a target module and `actrepo`, classify on `mid` as well. This is a
refinement, not a contradiction: `errno` 146 is documented as coming from `mid=vm`, and every session-scoped
errno in the table is raised before object resolution.

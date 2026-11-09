# 08 — Background Task Manager & Task View Footer

**Status:** Implemented (Phases 1–5 complete; see §10)
**Date:** 2026-11-08
**Scope:** `plaivid_cli.presentation.tui`, `plaivid_cli.application.operations`, `plaivid_cli.domain.models`
**Related:** ADR 0007 (bounded worker & subprocess lifecycle), ADR 0012 (mutation safety), ADR 0013 (outcome taxonomy), ADR 0014 (collection scheduling/freshness)

---

## 0. TL;DR — two premises in the request need correcting before design

The request states that "executing actions might block the UI". **This is not true of the current code.** Both lifecycle paths already run inside Textual threaded workers:

| Path | Evidence |
| --- | --- |
| VM bulk actions | `presentation/tui/pages/virtual_machines/operations.py:75` — `@work(thread=True, group="operation", exclusive=False)` |
| Desktop actions | `presentation/tui/pages/virtual_desktops/controller.py:207` — `@work(thread=True, group="desktop-operation", exclusive=False)` |

The real gaps are different, and they are worth more than a rewrite of the threading model:

1. **No per-target deduplication.** Admission is a single boolean, `self._operation_active` (`presentation/tui/app.py:104`). It blocks *every* second action anywhere in the app, including an unrelated VM, and it does not identify *what* is running.
2. **Head-of-line blocking instead of idempotency.** A 40-VM bulk `stop` makes a single-VM `start` on an untouched host impossible. The reverse (double-submitting the same `(Action.START, uuid)` from two tabs) is refused only by accident, with a generic message.
3. **Status is transient, per-page, and lossy.** Results are pushed through `call_from_thread` into two unrelated `Static` widgets (`#action-status`, `#desktop-action-status`); the next message overwrites the previous one, switching tabs hides the other page's status, and `_clear_session_view()` (`presentation/tui/session.py:90+`) wipes it on session change.
4. **No per-target progress.** `OperationCoordinator._execute_locked` loops targets internally (`application/operations/coordinator.py:180-181`) and returns only when the whole bulk finishes. Requirement 3 (real-time Queued/Running/Success/Failed per task) **cannot** be satisfied by the current coordinator contract — it needs a progress channel. This is the largest actual code change in the whole feature.
5. **A latent correctness trap for naive "background queue" designs.** See §3.1 — implementations that queue frozen `OperationPlan` objects will fail with `OPERATION_PLAN_STALE` by design.

**Recommendation:** build the registry, progress channel, and footer (requirements 2–4) exactly as asked; implement requirement 1 as *"already non-blocking — formalize it"* rather than re-architecting execution. Do **not** introduce multiprocessing (§8.2).

---

## 1. Audit of the current dispatcher

### 1.1 Thread ownership map

```
UI thread (asyncio)                         worker thread (Textual @work(thread=True))
─────────────────────                       ─────────────────────────────────────────
Select.Changed
  └─ _begin_action()                 ops.py:26
       ├─ _operation_active check     ops.py:27
       ├─ resolve_targets()           (UI thread — see Caveat A, §1.2)
       ├─ operations.create_plan()    (UI thread — see Caveat A, §1.2)
       └─ _launch_operation()         ops.py:60
            ├─ _operation_active=True ops.py:70
            └─ _execute_action() ────────────►  operations.execute(token, ...)
                                                    │  application/operations/coordinator.py:113
                                                    ├─ with self._lane:        (:125)
                                                    ├─ create_plan() re-validate
                                                    ├─ collection.begin_mutation()
                                                    ├─ for record in targets:  (:180)
                                                    │     └─ _dispatch_one()   (:218)
                                                    │          └─ PvmGateway.dispatch_action()
                                                    │               └─ SbellClient.call()
                                                    │                    └─ ProcessRunner.run()
                                                    │                         └─ Popen + wait(timeout)
                                                    ├─ collection.end_mutation()
                                                    └─ collection.collect_once("inventory")
                                                 returns OperationResult
                ◄────────────────────────────────
            call_from_thread(_show_operation)   ops.py:101
            call_from_thread(_request_refresh)  ops.py:102
            finally: call_from_thread(_operation_finished)  ops.py:105
```

`DesktopOperationExecutor.execute()` (`application/operations/desktop_executor.py:59`) is structurally identical: same `_lane`, same sequential loop, same `begin_mutation`/`end_mutation`, calling the very same `_dispatch_one` that `OperationCoordinator` passes in at construction (`coordinator.py:66-68`).

### 1.2 Is the Textual main thread blocked? — No, with two caveats

* **Dispatch, API calls, and subprocess waits are off the UI loop.** `ProcessRunner.run()` blocks in `child.wait(timeout=deadline)` (`infrastructure/process.py:159`) with a default 30 s deadline (`config.py:93`, `PLAIVID_CMD_TIMEOUT`). For a bulk of *n* targets, the worker thread can block for up to `n × 30 s`. The event loop keeps processing input throughout; this is already verified by `tests/unit/test_cli_and_tui.py::test_tui_navigation_remains_responsive_during_slow_collection`.
* **Caveat A — unavoidable UI-thread work remains.** Target resolution and plan construction happen on the UI thread (`ops.py:47`, `ops.py:52`). Both are pure CPU over an in-memory snapshot, but `create_plan` → `_build_plan` reads `self._collection.snapshot` (`planner.py:56`), and `CollectionCoordinator.snapshot` takes the collection `RLock` (`collection/coordinator.py:49-51`). That lock is only held during publishing (`_collect`, `coordinator.py:260-270`), never across the subprocess call, so contention is bounded to microseconds. **Acceptable. Leave it on the UI thread** — the freshness gate must see the same generation the operator saw, and moving it to the worker would let the plan drift from the reviewed selection.
* **Caveat B — `@work(..., exclusive=False)` plus a boolean is a fragile pair.** Nothing structurally prevents a second worker group from starting if `_operation_active` is ever reset early or set late. Two concurrent workers would both block on `_lane` (a non-reentrant `threading.Lock`, `coordinator.py:64`), and the loser would then fail validation — see §3.1.

### 1.3 How the dispatcher talks to `PvmGateway`

There is no queue, no broker, and no retry. The path is a direct synchronous call made on the worker thread:

```
OperationCoordinator._dispatch_one()            coordinator.py:218
  └─ PvmGateway.dispatch_action(token, action, uuid)   ports.py:40
       └─ LocalPvmAdapter.dispatch_action()            adapter/local.py:264
            └─ self._call("vm", action.value, _action_params(...), token)
                 └─ SbellClient.call()                 pvm/sbell.py:56
                      └─ ProcessRunner.run(argv)       infrastructure/process.py:107
                           → Popen(shell=False, new session) → bounded drain → wait/reap
```

Error translation is already normalized at the boundary (`adapter/local.py:83-86` maps `ProcessStartError`/`ProcessError` to `AppError` with codes), and `_dispatch_one` converts every failure into a typed `TargetOutcome` — `REJECTED`, `FAILED`, or `OUTCOME_UNKNOWN` (`coordinator.py:218-256`). **This is excellent for our purposes:** the outcome vocabulary we need for the footer already exists (`OperationState`, `domain/models/enums.py:33-45`) and already distinguishes "failed" from "unknown", which the footer must not collapse.

### 1.4 What is actually missing (gap list)

| # | Gap | Evidence | Impact on the new requirements |
| --- | --- | --- | --- |
| G1 | Global boolean admission, not per-`(action, uuid)` | `app.py:104`, `ops.py:27,67`, `controller.py:164,198` | Req. 2 unimplementable as stated |
| G2 | Blocks unrelated work (head-of-line) | `ops.py:27` | Operator friction; the footer makes it visible |
| G3 | Logout also gated on the same boolean | `session.py:60` | Coupling; registry should answer "any mutation in flight?" |
| G4 | No per-target progress events | `coordinator.py:180-181`, `desktop_executor.py:99-120` | Req. 3 (live per-target rows) blocked |
| G5 | Status delivery is `call_from_thread` into page-local `Static`s | `ops.py:98-105`, `controller.py:230-235` | No central history; lost on tab switch / session change |
| G6 | `call_from_thread` raises if the app stopped | `textual/app.py:1041-1047`; swallowed at `ops.py:105-109` | Shutdown races; message-based path returns `False` instead |
| G7 | Desktop path duplicates all of the above | `controller.py:159-252` | Two divergent implementations to keep in sync |
| G8 | Error text not redacted on every path before display | `ops.py:118,122` and `controller.py:205` redact, other paths do not; ad-hoc | Centralize redaction in the footer |

---

## 2. Design goals & non-goals

**Goals**

- G-A: UI thread never waits on PVM, and never mutates a widget from a foreign thread.
- G-B: Admission is per-target and idempotent, decided synchronously on the UI thread, with an immediate operator-visible answer.
- G-C: One append-only, scrollable, centrally-owned task record — independent of which tab is active.
- G-D: All cross-thread updates flow through typed Textual `Message` subclasses.
- G-E: Zero behavioural change to the CLI (`presentation/cli/operations.py:67` calls `execute()` directly and must keep working).
- G-F: No new dependency; no new executor/queue framework (ADR 0007: "no separate executor/scheduler framework").

**Non-goals**

- Parallel PVM mutation. ADR 0007/0012 keep mutations serialized behind `_lane` until host concurrency is evidenced.
- Cancelling a dispatched mutation. ADR 0007: cancellation of a UI wait is not proof the operation stopped.
- Automatic retry (forbidden by ADR 0012).
- Cross-process task coordination.

---

## 3. Task registry design

### 3.1 The stale-plan trap (read this before choosing a queue)

`OperationPlan` is a *frozen* admission token: `(action, target_uuids, inventory_generation, inventory_succeeded_at, is_bulk, freshness_limit_seconds)` (`domain/models/operations.py:27-35`). Both executors recompute the plan on entry and demand exact equality, otherwise they raise `OPERATION_PLAN_STALE` (`coordinator.py:139-158`, `desktop_executor.py:73-84`).

Now note `begin_mutation` bumps `self._generation` (`collection/coordinator.py:155`) and `end_mutation` bumps it again (`:177`). **Therefore task A completing invalidates the generation baked into task B's frozen plan.** A naive implementation — "accept both, queue B, run when A finishes" — deterministically fails B with:

> `inventory changed or expired immediately before dispatch; review a new plan`

This is by design (ADR 0012: never dispatch against a plan whose evidence moved). Two ways forward:

| Model | Admission | Consequence |
| --- | --- | --- |
| **B — Reject on conflict (recommended, Phase 1–3)** | At most one mutation group in flight. Identical `(action, uuid)` ⇒ silent no-op. Different work ⇒ immediate, explicit refusal with the blocking task named. | Preserves every existing safety invariant. Plan is always fresh at dispatch. Zero changes to `OperationCoordinator`. Matches ADR 0012. |
| **A — Intent queue (optional, later)** | Queue *intent* (`action`, `selectors`), never a `OperationPlan`. A single drain worker re-plans inside the worker thread immediately before dispatch. | Enables "queue my start behind that bulk stop". Requires moving `create_plan` into the worker and re-deriving `TargetSelection` from a fresh snapshot, plus a UI affordance for "my queued plan went stale — re-review". Significantly more risk; needs its own ADR. |

The rest of this document specifies **Model B**, because it fully satisfies requirements 1–4 while adding no new dispatch semantics. The footer is designed so Model A can be added later without touching it (a `QUEUED` row simply becomes reachable).

### 3.2 Where the registry lives (and why it must be in `domain`)

An architecture test forbids TUI *component* modules from importing the application layer:

> `tests/unit/test_architecture_boundaries.py:103-104` — `forbidden_imports = _forbidden("tui") | {"plaivid_cli.application", "subprocess"}` applied to every file under `presentation/tui/components/**`.

A `TaskViewFooter` living in `presentation/tui/components/` therefore **cannot** import `TaskManager` or `TaskRecord` from `plaivid_cli.application`. Solution: put the plain value objects in the domain layer, which every layer may import.

```
domain/models/tasks.py            ← TaskKey, TaskStatus, TaskRecord, TaskEvent  (no Textual, no I/O)
        ▲                    ▲
        │                    │
application/operations/      presentation/tui/components/
  task_registry.py             task_footer.py     (renders TaskRecord only)
  (TaskManager: admission,
   pruning, listener fan-out)
        ▲
        │ listener protocol (plain callable, NOT a Textual import)
presentation/tui/app.py  →  builds Messages, posts them
```

`TaskManager` has **no Textual dependency** — it notifies a `Callable[[TaskEvent], None]`. That keeps it unit-testable headless (consistent with the existing 146-test suite style) and keeps the layer rule intact. The listener supplied by `PlaividTui` is a one-liner that calls `self.post_message(...)` (proven thread-safe, §5.1).

### 3.3 Data structures

```python
# plaivid_cli/domain/models/tasks.py          (sketch — signatures only)

class TaskStatus(StrEnum):
    QUEUED = "QUEUED"          # admitted, not yet on the wire
    RUNNING = "RUNNING"        # dispatching to PvmGateway
    SUCCEEDED = "SUCCEEDED"    # PVM accepted the command (not proof of completion)
    FAILED = "FAILED"          # PVM reported failure
    REJECTED = "REJECTED"      # policy refusal / not dispatched
    UNKNOWN = "UNKNOWN"        # OUTCOME_UNKNOWN — must never render as "failed"

@dataclass(frozen=True, slots=True)
class TargetRef:
    uuid: str                  # canonical_uuid() normalized; the identity
    label: str = ""            # redacted display name; never used for identity

@dataclass(frozen=True, slots=True)
class TaskKey:
    action: Action
    target_uuid: str           # == TargetRef.uuid

@dataclass(slots=True)
class TaskRecord:
    task_id: str               # uuid4, stable row key for the footer DataTable
    key: TaskKey
    operation_id: str          # groups all targets of one bulk submission
    status: TaskStatus
    message: str = ""          # already redacted
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
```

```python
# plaivid_cli/application/operations/task_registry.py     (sketch)

class Admission(StrEnum):
    ADMITTED = "admitted"
    DUPLICATE = "duplicate"        # identical (action, uuid) already live → ignore
    CONFLICT = "conflict"          # different action on a claimed target → refuse
    BUSY = "busy"                  # Model B: another mutation group holds the lane

class TaskManager:
    """Thread-safe, per-target admission and lifecycle board."""

    def __init__(self, listener: Callable[[TaskEvent], None] | None = None,
                 *, history_limit: int = 200) -> None: ...

    def admit(self, action: Action, targets: Sequence[TargetRef],
              operation_id: str) -> Admission: ...        # UI thread; synchronous, O(n); no I/O
    def start(self, operation_id: str) -> None: ...      # worker thread
    def progress(self, uuid: str, state: OperationState, message: str) -> None: ...  # worker
    def finish(self, operation_id: str, result: OperationResult) -> None: ...        # worker
    def abandon(self, operation_id: str, reason: str) -> None: ...                   # worker/exception
    def any_active(self) -> bool: ...                    # replaces _operation_active (G3)
    def records(self) -> tuple[TaskRecord, ...]: ...     # snapshot for the footer
    def reset(self) -> None: ...                         # session change
```

**Concurrency rules**

- One `threading.Lock` guards `_live: dict[TaskKey, TaskRecord]` and `_history: deque[TaskRecord]`.
- `admit()` runs on the UI thread and completes in a lock acquisition — no I/O, no `.result()`. It is *the only* writer of new live keys, so admission decisions are totally ordered with respect to operator input; there is no race between two submissions.
- `progress()`/`finish()` run on worker threads, keyed by `operation_id` + canonical UUID, so they cannot collide with an admission.
- Terminal transitions remove the key from `_live` and push a copy into `_history` (bounded, `history_limit`). A key is only reusable after it left `_live`.
- Callbacks are invoked **outside** the lock to avoid re-entrancy deadlock if a listener ever queries the registry.

### 3.4 Admission algorithm (the answer to requirement 2)

```
admit(action, targets, operation_id):
    for each target in targets:                       # deterministic order
        key = TaskKey(action, canonical_uuid(target))
        if key in _live:
            return DUPLICATE                          # exact same (action, uuid) live → ignore
        if any(live.key.target_uuid == key.target_uuid for live in _live):
            return CONFLICT                           # e.g. START live, STOP requested
    if _live and model_b: return BUSY                 # one mutation group at a time
    insert all keys as QUEUED; emit TaskDispatched per key
    return ADMITTED
```

- **`DUPLICATE` is a silent no-op** and satisfies the literal requirement: *"if `(Action.START, VM_UUID_1)` is running, ignore new requests for it."* It must still produce **feedback** — a non-blocking toast/status line ("Already running") — because silently swallowing a keystroke reads as a broken UI.
- **`CONFLICT` is a superset check.** Without it, a `STOP` in flight and a `START` request would both be admitted and serialized behind `_lane`, producing a nonsensical state transition sequence on the same VM. Same-target/different-action must be refused, and the message should name the conflicting action.
- Both are **all-or-nothing across the request**: a bulk of 5 where 1 UUID is live is rejected as a whole, never partially dispatched (ADR 0012: reject the entire request rather than act on a subset).
- `BUSY` preserves today's behaviour (`"An operation is already in progress."`, asserted by `tests/unit/test_cli_and_tui.py:361`) so that test keeps passing almost verbatim.

### 3.5 Ownership and lifecycle

- `TaskManager` is constructed in `PlaividTui.__init__` (per app instance), **not** in `Bootstrap`. ADR 0007 says bootstrap owns long-lived *mutation* state; this registry is view/admission state scoped to one TUI session. The CLI path is untouched (G-E).
- On `_session_ended()` / `_session_ready()`: call `reset()`, which emits a single `TaskRegistryReset` so the footer clears. Do not silently keep rows from a dead token.
- Prefer deriving `_operation_active` (see `app.py:104`, `session.py:60`, `ops.py:27,67`, `controller.py:164,198`) from `manager.any_active()`. Keep a thin read-only property named `_operation_active` during Phase 1 so `tests/unit/test_cli_and_tui.py:355` (`tui._operation_active = True`) does not break; convert it to a real property with a setter that seeds the registry in the *same* phase, or update the test deliberately.

---

## 4. UI component design — `TaskViewFooter`

### 4.1 Widget choice: `DataTable`, not `RichLog`

| Option | In-place status change | Scroll | Row identity | Verdict |
| --- | --- | --- | --- | --- |
| `RichLog` | No — append-only; a `QUEUED→RUNNING→SUCCEEDED` sequence becomes 3 duplicate lines | Native, auto-scroll | None | Rejected (fails "real-time status") |
| `Static` + manual render | Yes | No | n/a | Rejected (fails "scrollable") |
| **`DataTable`** | **Yes — `update_cell(row_key, col, value)`** | Native, `max-height` + cursor | Row key = `task_id` | **Selected** |

`DataTable` also gives keyboard cursor movement for free, which matters for the "no mouse on a serial console" case. It must be a plain `DataTable` subclass — **not** named `CheckableTable`, because `tests/unit/test_architecture_boundaries.py:112-121` asserts exactly one `CheckableTable` definition exists in the package.

### 4.2 Placement in the existing layout (`presentation/tui/layout.py:24-55`)

Current shell flow inside `Vertical#shell`:

```
#topbar            height 2
#login-box         VerticalScroll, display toggled
#tabs              TabbedContent, height 1fr   ← the only flexible child
#notice            height 1
Footer             height 1                    ← asserted by tests/unit/test_tui_theme.py:76
```

Insert the footer **between `#notice` and `Footer`**, in normal flow:

```python
yield Static("1 Overview · 2 Virtual Machines · …", id="notice")
yield TaskViewFooter()          # NEW — sits above the key-hint Footer
yield Footer()
```

```css
TaskViewFooter, #task-footer {
    height: 5;            /* collapsed default; 3 when only idle rows, 10 when expanded */
    max-height: 50%;
    display: none;        /* hidden until the first task exists */
    border-top: solid $p-border;
    background: $p-panel;
    scrollbar-color: $p-border;
}
#task-footer.-visible { display: block; }
```

**Why flow, not `dock: bottom`.** `#shell` is a `Vertical` with a `1fr` tab area. A docked child would be positioned relative to the *screen* and overlay `#notice`/`Footer` (both height 1, both asserted by tests). Flow placement lets Textual shrink the `1fr` region instead, which is exactly the layout behaviour we want. `max-height: 50%` prevents the footer from eating the whole screen at 40 rows.

**Layout-budget check** (must be verified, not assumed): at 80×40 the tab area currently gets ≈35 rows; a 5-row footer leaves ≈30. `#fleet-table` has `min-height: 8` and `#desktop-list` `min-height: 13` (`styles.py`), so 30 is safe — but the existing 80/120-column regression test (`test_tui_theme.py::test_both_pages_use_custom_theme_and_visible_controls_at_80_and_120`) must be re-run, and `display: none` when idle keeps the status quo byte-for-byte for the login screen.

### 4.3 Component contract

```python
# plaivid_cli/presentation/tui/components/task_footer.py      (sketch)

class TaskViewFooter(DataTable):
    """Scrollable, centrally-owned task status board. Presentation-only."""

    class TaskSelected(Message):            # optional: Enter on a row → jump to target
        def __init__(self, footer: TaskViewFooter, task_id: str) -> None: ...

    def on_mount(self) -> None: ...          # add_columns("time","action","target","state","detail")
    def apply_event(self, event: TaskEvent) -> None: ...   # upsert by task_id, then _fit()
    def clear_board(self) -> None: ...
    def _fit(self) -> None: ...              # toggle .-visible, clamp cursor, keep bottom pinned
```

- Accepts **only domain value objects** (`TaskRecord`, `TaskEvent`) — satisfies §3.2's boundary rule.
- Applies `redact_text()` (`domain/redaction.py`) to every message before insertion. Redaction is a documented repo invariant (ADR 0012); centralizing it here closes gap G8.
- Elapsed time needs a repaint. Do **not** reuse the existing 0.5 s `_tick` (`refresh.py:70`); instead let only this widget run `set_interval(1.0, self._refresh_elapsed)` and **pause it when no row is `RUNNING`** — a dormant footer must cost zero.
- Renders `UNKNOWN` distinctly from `FAILED` (e.g. `?` marker + warning colour). Collapsing them would violate ADR 0013 and the "do not retry until reconciled" contract in `operations/results.py:45`.

### 4.4 Footer row model

| time | action | target | state | detail |
| --- | --- | --- | --- | --- |
| 10:42:03 | START | vm-alpha | RUNNING | dispatching… |
| 10:42:04 | STOP | desktop-7f3a… | SUCCEEDED | PVM accepted vm/stop |
| 10:42:05 | KILL | vm-zulu | UNKNOWN | do not retry until reconciled |

Targets show `target_label` truncated with the first 8 hex chars of the UUID as a stable suffix, so identity is always recoverable without hovering.

---

## 5. Message flow (requirement 4)

### 5.1 Why `Message`, not `call_from_thread`

Both are legal from a worker thread, but only one degrades gracefully:

- `App.call_from_thread` **raises `RuntimeError`** when the app is not running (`textual/app.py:1041-1047`). The current code must wrap its `finally` in `try/except RuntimeError` (`ops.py:105-109`, `controller.py:233-237`) — a smell that grows with every new callback.
- `MessagePump.post_message` is explicitly thread-safe and **returns `False`** when the pump is closing (`textual 0.47 message_pump.py:750-762`; identical in 8.x at `message_pump.py:875-888` — verified against both the project floor `textual>=0.47` and current 8.2.8). Textual's own `call_from_thread` docstring recommends it: *"Consider using post_message which is also thread-safe."*

Rule for the new code: **worker threads may only call `post_message` and `TaskManager`; never `call_from_thread`, never touch a widget or `self._*` view state.**

### 5.2 Message catalogue (`presentation/tui/messages.py`)

| Message | Emitted when | Thread | Handler effect |
| --- | --- | --- | --- |
| `TaskDispatched(task_id, key, operation_id)` | `admit()` inserted a `QUEUED` row | UI (admission is synchronous) | insert row, reveal footer |
| `TaskStarted(task_id)` | worker picks the target up, before `_dispatch_one` | worker | `QUEUED→RUNNING`, start elapsed clock |
| `TaskProgress(task_id, state, message)` | optional mid-flight detail (retry-free, e.g. "dispatching…") | worker | update detail cell only |
| `TaskCompleted(task_id, status, message)` | `TargetOutcome` is `SUCCEEDED` (and `COMMAND_ACCEPTED_UNCONFIRMED`) | worker | row → terminal, freeze elapsed |
| `TaskFailed(task_id, status, message)` | `FAILED` / `REJECTED` / `NOT_STARTED` / `CANCELLED_BEFORE_DISPATCH` | worker | row → terminal with error colour |
| `TaskUnknown(task_id, message)` | `OUTCOME_UNKNOWN` | worker | row → terminal with **warning** colour + "reconcile" hint |
| `TaskAdmissionRefused(action, targets, reason)` | `admit()` returned `DUPLICATE` / `CONFLICT` / `BUSY` | UI | inline status line only; **no row** |
| `TaskRegistryReset` | session end / logout | UI | clear table, hide footer |

All subclass `textual.message.Message`, carry only immutable domain values + primitives (no widget references — that is the classic leaked-handler bug), and are handled on `PlaividTui` with `@on(...)`, which delegates one line each to `TaskViewFooter.apply_event`. Following the existing pattern (`app.py:187-251`), the decorated handlers must live on the concrete `PlaividTui` class, not inside a mixin.

`TaskUnknown` is deliberately **not** folded into `TaskFailed`: ADR 0013 forbids promoting an uncertain outcome to a definite one, and the operator must see the difference.

### 5.3 End-to-end sequence (bulk STOP of 3 VMs)

```
UI thread                                worker thread                    TaskManager
─────────                                ─────────────                    ───────────
Select.Changed("stop")
 ├ admit(STOP, [u1,u2,u3]) ────────────────────────────────────────────►  lock
 │                                                                        all keys free
 │  ◄──────────── ADMITTED, 3× TaskDispatched ─────────────────────────
 ├ post TaskDispatched ×3  (self, UI thread)
 ├ start _execute_action ───────────────►
 │                                        operations.execute(token,...)
 │                                        ├ begin_mutation
 │                                        ├ on_progress(u1, DISPATCHING) ─► TaskStarted(u1)
 │  ◄── post TaskStarted ──────────────────┘                        ─► update row
 │                                        ├ dispatch_action(STOP,u1)  [~subprocess]
 │                                        ├ on_progress(u1, SUCCEEDED) ──► TaskCompleted(u1)
 │  ◄── post TaskCompleted ────────────────┘
 │                                        ├ … u2 → FAILED … u3 → NOT_STARTED (stop_bulk)
 │                                        ├ end_mutation / collect_once
 │                                        └ returns OperationResult ───► finish(op_id, result)
 │  ◄── post TaskCompleted/Failed ─────────┘
 ├ (optional) _request_refresh()
 └ footer pins to newest row; elapsed clock stops when nothing is RUNNING
```

Message ordering is guaranteed per-pump; the footer therefore applies events strictly in emission order and no reconciliation logic is needed.

### 5.4 The one change needed inside `OperationCoordinator`

Requirement 3 cannot be met without it (gap G4). Add a keyword-only, optional, backwards-compatible hook — the CLI passes nothing (`cli/operations.py:67`):

```python
ProgressSink = Callable[[str, OperationState], None]   # (target_uuid, state)

def execute(..., *, is_bulk: bool, plan: OperationPlan | None = None,
            on_progress: ProgressSink | None = None) -> OperationResult: ...

def execute_desktop(..., *, is_bulk: bool, plan: OperationPlan,
                    on_progress: ProgressSink | None = None) -> OperationResult: ...
```

`DesktopOperationExecutor` receives the sink through `execute()` (it already owns its loop) rather than storing mutable per-call state on the instance — the lane guarantees one execution at a time, but avoiding the attribute keeps re-entrancy obvious. `_dispatch_one` gains the same optional parameter, defaulting to `None`, so its behaviour and every existing test are unchanged.

No event is emitted for `OUTCOME_UNKNOWN` promotion: the sink forwards the raw `TargetOutcome.state` and the presentation layer maps it (§5.2).

---

## 6. File-level change map

| File | Action | Notes |
| --- | --- | --- |
| `domain/models/tasks.py` | **new** | `TargetRef`, `TaskKey`, `TaskStatus`, `TaskRecord`, `TaskEvent`; imports `domain` only |
| `domain/models/__init__.py` | edit | re-export |
| `application/operations/task_registry.py` | **new** | `TaskManager`, `Admission`; pure stdlib |
| `application/operations/coordinator.py` | edit | optional `on_progress` in `execute`, `execute_desktop`, `_dispatch_one` |
| `application/operations/desktop_executor.py` | edit | thread `on_progress` through its loop |
| `presentation/tui/components/task_footer.py` | **new** | `TaskViewFooter(DataTable)`; imports domain only |
| `presentation/tui/components/__init__.py` | edit | export |
| `presentation/tui/messages.py` | **new** | the eight `Message` subclasses |
| `presentation/tui/layout.py` | edit | yield `TaskViewFooter()` above `Footer` |
| `presentation/tui/styles.py` | edit | `#task-footer` rules + `.-visible` |
| `presentation/tui/app.py` | edit | construct `TaskManager`, listener → `post_message`, `@on` handlers, replace `_operation_active` |
| `pages/virtual_machines/operations.py` | edit | admit via manager; stop using the boolean |
| `pages/virtual_desktops/controller.py` | edit | same; delete duplicated status plumbing |
| `presentation/tui/session.py` | edit | `reset()` on session change; `any_active()` for the logout gate |
| `docs/architecture/adr/0015-task-admission-and-deduplication.md` | **new (Phase 4)** | record Model B, and why Model A is deferred |
| `docs/architecture/08-…(this file)` | — | design of record |

---

## 7. Implementation plan

Each phase is independently reviewable, independently shippable, and leaves the suite green.

### Phase 0 — Baseline (½ day)
- Run `python -m pytest -q --ignore=tests/smoke.py`, `ruff`, `pyright` to capture the current baseline (README claims 146 passing).
- Add a failing-first test proving the double-dispatch gap: submit the same `(STOP, UUID_A)` twice within one event-loop turn and assert `provider.dispatched` has length 2 today. This test *is* the acceptance criterion for requirement 2.
- **Risk:** none. **Exit:** gap reproduced in a test.

### Phase 1 — Domain models + `TaskManager` (1–1.5 days)
- `domain/models/tasks.py`, `application/operations/task_registry.py`.
- Headless tests: exact-duplicate ⇒ `DUPLICATE` and no new key; different-action-same-target ⇒ `CONFLICT`; partial bulk overlap ⇒ whole request refused; terminal transition frees the key; `history_limit` pruning; 10 threads hammering `progress()` while the main thread calls `records()` (no lock errors, no lost updates).
- Do **not** wire into the TUI yet.
- **Exit:** registry proven, existing suite untouched.

### Phase 2 — Progress channel in the application layer (1 day)
- Add `on_progress` to `OperationCoordinator`/`DesktopOperationExecutor` (§5.4).
- Tests with `FakeProvider`: one sink call before and one after each target; sink exceptions must not abort a bulk (wrap in `try/except Exception: pass` — a view bug must never corrupt a mutation).
- **Exit:** CLI behaviour byte-identical; `test_application_operations.py` green.

### Phase 3 — `TaskViewFooter` + messages + layout (2 days)
- Widget, messages, compose, CSS, `@on` handlers.
- Manual/pilot checks: reveal on first task; scroll with `↑/↓` and `PgUp/PgDn`; hidden and zero-cost when idle; 80×40 and 120×40; 16/256/truecolor/no-color.
- Re-run `test_tui_theme.py` and `test_group_palette.py`; adjust the height budget assertion deliberately if the footer changes pre-existing regions.
- **Exit:** footer renders synthetic events in a `run_test()` harness without any real provider.

### Phase 4 — Cut over both controllers (1.5 days)
- `_begin_action`/`desktop_action_requested` call `manager.admit(...)`; on refusal show the reason and return **without** `_operation_active` bookkeeping.
- Keep `#action-status` / `#desktop-action-status` for the long-form last-result sentence (they carry detail the grid cannot) — do not delete them in the same PR; a separate cleanup can retire them once the footer has been used for a release.
- Delete the duplicated `try/finally call_from_thread(_…_finished)` scaffolding in favour of `manager.finish()` + one message.
- Update `test_tui_blocks_duplicate_operation_and_logout_while_operation_is_active` to seed the registry instead of poking `_operation_active`, or keep a compatibility property.
- **Exit:** every `provider.dispatched` assertion still passes; the Phase-0 double-dispatch test now passes.

### Phase 5 — Hardening, docs, ADR (1 day)
- Shutdown test: worker completes after `run_test()` exits ⇒ `post_message` returns `False`, no traceback, no `RuntimeError`.
- Session-change test: logout mid-bulk clears the board and does not resurrect rows.
- Redaction test: a VM named `password=hunter2` must not reach the footer cells.
- ADR 0015, README TUI section, and this document's status → Implemented.

**Total: ~7 working days**, two natural review gates (after Phase 2 — application-layer change; after Phase 4 — UI cutover).

---

## 8. Risks & explicit non-decisions

### 8.1 Risks

| Risk | Mitigation |
| --- | --- |
| Footer steals vertical space at 80×40, breaking the tuned layout | `display: none` when idle; 5-row cap; `max-height: 50%`; expand binding; re-run the 80/120 regression test |
| Elapsed-time repaint adds idle CPU | Interval runs only while a row is `RUNNING` |
| `_operation_active` semantics drift during cutover, allowing two workers | Keep `any_active()` as the single source; assert it in the Phase-0 test |
| Sink exceptions abort a bulk | Guard the sink call in the application layer |
| A reader mistakes `UNKNOWN` for a retryable failure | Distinct glyph + colour; text says "do not retry until reconciled" (matches `operations/results.py:45`) |
| TUI component importing the application layer | Enforced by `test_architecture_boundaries.py`; models live in `domain` (§3.2) |

### 8.2 Rejected alternative: multiprocessing

The request lists multiprocessing as an option. **Rejected** for four concrete reasons: (a) the mutation lane exists to *serialize* dispatch (ADR 0007/0012), so extra processes buy no throughput; (b) the session token and `CollectionCoordinator` mutation barriers are in-process state that would have to be recreated or shipped per process, breaking the generation/freshness gate; (c) `TaskManager` state could not be shared without a `Manager` proxy — reintroducing the very serialization we are trying to observe; (d) `ProcessRunner` already isolates each subprocess with `start_new_session` and bounded reap (`process.py:119-187`), so process-level isolation is already handled where it matters.

### 8.3 Open questions for the product owner

1. **DoS by assertion:** is `BUSY` (one group at a time) acceptable for the fleet sizes you operate, or is Model A (intent queue with in-worker re-planning) required in this release? The footer is identical either way; the difference is whether `QUEUED` is reachable.
2. **Retention:** should the board keep the last 200 terminal rows for a session, or only live ones plus the current session's failures?
3. **Sound:** should `FAILED`/`UNKNOWN` raise Textual's `bell`? (Recommend off by default; terminal-behaviour policy is unverified.)
4. **`ENTER` on a footer row** — jump to the VM/Desktop detail, or no-op? Recommend jump (small, high value), but it couples the footer to both pages' selection code.
5. **Persistence:** audit-style retention of task outcomes to the local DB (`infrastructure/audit.py`) is out of scope here; confirm that PVM-side audit remains the system of record.

### 8.4 What this document does not claim

No live PVM host was accessed. Nothing here is evidence that PVM accepts concurrent or sequential commands from one session, that a `success` reply means completion (ADR 0013 keeps `SUCCEEDED` = "PVM accepted"), or that the footer's appearance has been accepted on a real terminal. All rendering claims are limited to the local Textual test harness.

---

## 9. Appendix — verification notes for reviewers

- `post_message` thread-safety was **verified against both ends of the supported range**, not assumed: `textual==0.47.0` `message_pump.py:750-762` and `textual==8.2.8` `message_pump.py:875-888` both divert to `loop.call_soon_threadsafe(...)` when `self._thread_id != threading.get_ident()`.
- `call_from_thread`'s raise-when-not-running behaviour: `textual/app.py:1041-1047`.
- `_lane` is a plain non-reentrant `threading.Lock` (`coordinator.py:64`), taken by `OperationCoordinator.execute` (`coordinator.py:125`), by `close` (`:73`), and by `DesktopOperationExecutor.execute` (`desktop_executor.py:71`). That single lock is why exactly one mutation — VM or Desktop — can be in flight today.
- Generation bumps that invalidate queued plans: `begin_mutation` (`collection/coordinator.py:155`) and `end_mutation` (`:177`).
- The architecture tests referenced in §3.2 and §4.1 are `tests/unit/test_architecture_boundaries.py:103-121`.

---

## 10. Implementation record (Phases 1–5)

Model B was approved and implemented as designed. Summary of what exists now:

### Delivered modules

| Module | Contents |
| --- | --- |
| `domain/models/tasks.py` | `TargetRef`, `TaskKey`, `TaskStatus`, `TaskRecord`, `TaskEvent`, `task_status_for()` |
| `application/operations/task_registry.py` | `TaskManager`, `Admission` (`ADMITTED`/`DUPLICATE`/`CONFLICT`/`BUSY`) |
| `presentation/tui/messages.py` | `TaskDispatched`, `TaskStarted`, `TaskProgress`, `TaskCompleted`, `TaskFailed`, `TaskUnknown`, `TaskAdmissionRefused`, `TaskRegistryReset`, `OperationFinished` |
| `presentation/tui/components/task_footer.py` | `TaskViewFooter(DataTable)` |
| `application/operations/coordinator.py` | optional `on_progress` on `execute()`, `execute_desktop()`, `_dispatch_one()` |
| `application/operations/desktop_executor.py` | `on_progress` threaded through its dispatch loop |

### Behaviour as shipped

- **Admission** is synchronous on the UI thread and per target. An exact `(action, uuid)` repeat is `DUPLICATE` and dispatches nothing; a different action on a claimed target is `CONFLICT`; unrelated work while a group is in flight is `BUSY` (Model B). Refusals produce **no** task row — only an inline explanation on the page status line.
- **Cross-thread delivery** is `post_message` only. Background threads never call `call_from_thread`, and never touch a widget or view attribute.
- **The footer** is a `DataTable` keyed by `task_id`, hidden (`display: none` plus the `.-visible` class) until the first task exists, so an idle footer costs no layout height. It is placed in normal flow above `Footer`, not docked, so the flexible tab area shrinks instead of the key hints being overlaid.
- **Elapsed clock** runs on a 1 s interval owned by the footer and stops automatically when no row is `QUEUED`/`RUNNING`.
- **`UNKNOWN`** is rendered with its own glyph and the warning colour, never as `FAILED`, and its detail text says "reconcile before retrying".
- **Redaction** is applied in `TaskManager` and again in the footer before any text reaches a cell.
- **Session change** calls `TaskManager.reset()`, which clears live rows and history and hides the board.
- **`_operation_active`** survives as a read-only property delegating to `TaskManager.any_active()`, so the logout gate keeps working without a mutable global.

### Deviations from the design text

1. **`TaskManager` also owns an operation index** (`_by_operation`) so `start`/`progress`/`finish` address one submission without scanning. `progress` looks up by operation id rather than action, which removes an ambiguity the original sketch had when two operations of the same action were live.
2. **`OperationFinished` message added** (not in the original catalogue). It carries the long-form `OperationResult` and a `page` discriminator so the VM and Desktop pages keep their detailed status sentences while the board carries per-target rows.
3. **The Desktop path keeps `_desktop_result_text()`** instead of being deleted outright; retiring the two page status lines is deferred to a separate change once the board has been used for a release.

### Defects found and fixed during integration

1. **Cross-thread message ordering.** A worker-thread `post_message` is routed
   through `loop.call_soon_threadsafe`, so a `TaskCompleted` published from the
   worker could be *delivered after* a `TaskRegistryReset` posted from the UI
   thread, re-creating a row for a session that had already ended. Fixed with a
   monotonic board epoch: each `TaskMessage` carries the epoch it was published
   in, `TaskRegistryReset` increments it first, and handlers discard anything
   older. Covered by `test_late_worker_message_cannot_resurrect_a_cleared_row`.
2. **`OperationFinished` could address widgets that no longer exist.** A late
   completion during shutdown raised `NoMatches` from `#action-status`. The
   handler body is now guarded as a whole, so a straggling message is a no-op.
3. **A stale plan after admission is now visible.** When a periodic refresh
   invalidates the plan between UI-thread admission and worker dispatch, the
   coordinator correctly refuses with `OPERATION_PLAN_STALE`; the board records
   a `REJECTED` row and the controls re-enable, instead of a task lingering in
   `QUEUED`. Covered by `test_stale_plan_after_admission_is_recorded_as_rejected`.

### Verification

- `python -m pytest -q --ignore=tests/smoke.py` → **295 passed** (baseline was 233), stable across five consecutive full-suite runs.
- New tests: `test_task_manager.py` (43), `test_operation_progress_sink.py` (7), `test_task_footer_tui.py` (12).
- `ruff check .` clean; `git diff --check` clean; wheel builds and contains all five new modules.
- Pyright: **312 errors, down from a 315 baseline**; every remaining diagnostic is the pre-existing mixin attribute-resolution pattern, and the new modules are clean. (The project pins Python 3.12; this sandbox has 3.11, so the suite was run under 3.11 with the same dependencies.)

### Pre-existing test flakiness fixed during the work

Three assertions raced fixed `pilot.pause()` durations and failed intermittently once the suite grew. They now wait on the actual condition; the assertions themselves are unchanged in strength:

- `test_virtual_desktops.py` — waits for the initial collection to settle before activating the Desktop tab, because a demand raised while the read lane is busy is legitimately re-issued on a later tick.
- `test_multi_select.py` — waits for the Desktop roster before moving the cursor.
- `test_overview_monitoring.py` — waits for the second session's inventory snapshot.

### Still not claimed

No live PVM host was contacted. Nothing here demonstrates that PVM accepts sequential or concurrent commands from one session, that a `success` reply means completion, or that the footer has been accepted visually on a supported terminal. Those remain **PENDING MANUAL PVM VALIDATION** per `docs/REAL_PVM_VALIDATION.md`.

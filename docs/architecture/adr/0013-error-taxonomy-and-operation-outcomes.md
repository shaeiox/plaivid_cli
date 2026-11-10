# ADR 0013 — Error Taxonomy and Operation Outcomes

- **Status:** Implemented locally; response mapping remains pending manual PVM evidence
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Application architecture owner; CLI/API owner sets stable exit-code contract; support owner approves diagnostics.

## Context and evidence

- **Repository fact:** transport errors (`TransportError`) differ from XML `Response.ok == False`, but callers suppress or flatten failures and one-shot mode returns zero for handled failures (`transport.py:27–107`, `orchestrator.py:354–365`).
- **PVM fact not established:** nonzero process status, XML failure, or success envelope has not been shown to prove whether a mutating command did or did not complete.

## Decision proposal

Represent errors/results as typed outcomes across Infrastructure → Application → Presentation. Preserve causes safely; do not turn error, empty, stale and unsupported into the same value.

### Error categories

At minimum distinguish configuration/executable, process lifecycle, protocol/parse, PVM response, authorization/session, collection quality, application input/policy, worker/shutdown, and operation outcome. Keep PVM status/errno/action ID when present, but do not assume an exit/error proves mutation non-execution unless verified. Exact mappings require target fixtures.

### Per-target mutation outcomes

Use explicit per-target terminal outcomes:

- `NOT_STARTED`: target was in a validated bulk plan but execution stopped before dispatch reached it.
- `REJECTED`: policy/input/freshness/confirmation rejected the operation before dispatch.
- `CANCELLED_BEFORE_DISPATCH`: cancellation occurred before command dispatch.
- `SUCCEEDED`: requested completion is confirmed by a verified command contract or supported readback.
- `FAILED`: definite failure under a verified contract establishes the requested operation did not complete/was not accepted.
- `COMMAND_ACCEPTED_UNCONFIRMED`: response establishes command acceptance only; completion is not verified. This is not success.
- `OUTCOME_UNKNOWN`: command may have been accepted/executed, but acceptance/completion cannot be established. This remains explicit per target and may not be collapsed into `FAILED` or generic `PARTIAL`.

Do not infer PVM's command acceptance/completion semantics from the word `success`, an action ID, exit status or documentation example. The current implementation has no verified acceptance contract, so every returned response after dispatch maps to `OUTCOME_UNKNOWN`; `COMMAND_ACCEPTED_UNCONFIRMED` is reserved for a future evidence-backed mapping. Never retry these outcomes automatically. This local mapping does not establish actual PVM behavior.

### Bulk operation outcomes

Return all per-target outcomes, safe causes, and counts plus one aggregate:

- `SUCCEEDED` only when all requested targets are confirmed complete.
- `FAILED` when execution was attempted and all attempted targets definitively failed, with no unknown/accepted-unconfirmed target.
- `REJECTED` when no target was dispatched and policy/input rejected the request.
- `PARTIAL` when at least one target succeeded and another definitively failed or was not started, with no unknown/accepted-unconfirmed target.
- `COMMAND_ACCEPTED_UNCONFIRMED` if any target has that status and none is `OUTCOME_UNKNOWN`; it remains visible in the overall summary.
- `OUTCOME_UNKNOWN` if any target is unknown; this has precedence over ordinary partial/failure summaries and stays visible in aggregate counts.

The implementation policy uses **bounded parallel dispatch with scoped continuation and daemon liveness probing** (ADR 0007/0012/0015). A rolling worker pool is limited by `PLAIVID_MAX_CONCURRENCY` (default `3`); outcomes retain planned UUID order. With a healthy daemon, a dispatched error is target-scoped unless it is one of the explicit session errnos/codes below, allowing target-specific disk/storage and VM-state failures to remain local. Session/contract failures stop new submissions, cancel work not yet started, and allow already-running calls to settle before the generation barrier closes. `NOT_STARTED`/`SKIPPED` is reserved for targets never dispatched.

| Failure scope | Evidence | Target outcome | Batch behaviour | Remaining targets (Task Board) |
| --- | --- | --- | --- | --- |
| Target state / disk / storage | Dispatched error with healthy daemon; includes `errno` 146 and other non-session errnos | `FAILED` | Continue rolling submissions | Attempted normally |
| Target timeout | `code == PVM_COMMAND_TIMEOUT` + `is_daemon_alive() == True` | `OUTCOME_UNKNOWN` (`command timed out (10s), daemon healthy`) | Continue; never auto-retry timed-out target | Attempted normally |
| Daemon offline | Timeout/error + `is_daemon_alive() == False` | `FAILED` (`Daemon Offline`) | Stop submissions; settle in-flight calls | Never-submitted targets `NOT_STARTED` → `– SKIPPED` (`Daemon Offline`) |
| Session / contract | `errno` 39/40/106/107/108/137/185, `PROCESS_START_FAILED`, other explicit session code, or undispatched failure | `FAILED` / `REJECTED` / `OUTCOME_UNKNOWN` | Stop submissions; cancel work not started; settle in-flight calls | Never-dispatched targets `NOT_STARTED` → `– SKIPPED` |
| Other dispatched unknown | Unexpected status, transport/process error, or unrecognized errno while daemon is healthy | `OUTCOME_UNKNOWN` or `FAILED` | Target-scoped continuation; unknown aggregate precedence retained | Attempted normally |

### Task Board vocabulary (`TaskStatus`)

On the interactive Task Board (`domain/models/tasks.py`, `TaskViewFooter`), each target remains `· QUEUED` until a worker actually begins that target's dispatch (`▶ RUNNING`); targets are not pre-marked running when the batch is admitted. `OperationState.NOT_STARTED` maps to `TaskStatus.SKIPPED` (rendered as `– SKIPPED` in muted style) rather than `⊘ REJECTED`. `REJECTED` is reserved for pre-dispatch policy/admission rejection and explicit cancellation. Per-target terminal outcomes and safe details propagate through `TaskManager.progress()` and render on `TaskViewFooter`.

Each `NOT_STARTED` target carries the reason the batch stopped, so an operator can tell a mixed batch from an aborted one. A mixed batch aggregates to `PARTIAL` when at least one target succeeded (with no `OUTCOME_UNKNOWN`), and to `FAILED` when none did; `OUTCOME_UNKNOWN` keeps its top precedence over both so a timed-out target is never silently re-run.

Response acceptance/completion mapping remains evidence-dependent: a positive-looking envelope must not be treated as proof of guest completion without the verified contract/readback required above. If a response is mapped to `OUTCOME_UNKNOWN`, retain that uncertainty in the aggregate and do not retry the target automatically; it does not by itself prevent scheduling unrelated targets while the daemon is healthy. `COMMAND_ACCEPTED_UNCONFIRMED` still requires an owner decision on its aggregate and continuation semantics.

### Read/mutation freshness and ordering

The OperationCoordinator and CollectionCoordinator establish a target-generation barrier (ADR 0007/0012). A read started before a mutation for affected UUIDs must not publish over the post-mutation generation. Reads for affected targets wait for reconciliation or remain stale while a mutation is active. After dispatch, request a supported readback; readback of a desired state can confirm current state only under an approved contract and does not prove causality. A missing transition is not by itself proof of failure. No unsupported PVM polling/completion command is assumed.

### One-shot CLI exit categories

Propose stable exit categories for one-shot commands; interactive TUI presents typed results and has no per-operation process exit until the app exits.

| Exit code | Category | Meaning |
|---:|---|---|
| `0` | `SUCCESS` | Read completed as requested, or all requested mutations are confirmed complete. Help/version/config-only success also returns zero without collection. |
| `1` | `FAILED` | Definite request/collection failure or all attempted mutations definitely failed. |
| `2` | `REJECTED` | Invalid input, stale/ambiguous target, safety-policy rejection; no mutation dispatched. |
| `3` | `PARTIAL` | Partial read result, or confirmed successes mixed with definite failures/`NOT_STARTED`; no unknown outcome. |
| `4` | `OUTCOME_UNKNOWN` | Any post-dispatch unknown or accepted-but-unconfirmed mutation. This takes precedence over other aggregate categories. |

Exact numeric compatibility remains subject to CLI review, but categories must be stable and truthful. Do not return zero for a handled failure. A read-only non-TTY invocation performs one bounded collection only; no background poll changes its exit/result after output.

## User and diagnostic channels

- User output identifies category, partial/stale sections, per-target counts/reasons, and whether command acceptance or completion is known.
- Diagnostics use a safe operation ID, source/category, elapsed time, and safe PVM errno/exit information. Never log passwords/tokens/login XML or unreviewed full payloads.
- Preserve internal exception chaining; sanitize at display/log boundaries.
- Retry timing is ADR 0014; worker/process mechanics are ADR 0007; mutation admission is ADR 0012.

## Validation required

Fake executable/provider tests for output/exit combinations, definite vs unknown result mapping, partial source collection, bounded worker count, deterministic final ordering, target-scoped continuation for VM-state/disk failures, explicit session/daemon stop-refill behavior, in-flight settlement, remaining `NOT_STARTED` reasons, accepted-unconfirmed aggregation, unknown precedence, and exit categories. Confirm PVM concurrent-dispatch support and response/exit/action-ID/completion semantics with authorized target captures before enabling parallelism against a live deployment.

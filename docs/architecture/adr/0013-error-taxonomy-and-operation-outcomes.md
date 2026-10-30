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
- `REJECTED` when no target was dispatched and policy/input/confirmation rejected the request.
- `PARTIAL` when at least one target succeeded and another definitively failed or was not started, with no unknown/accepted-unconfirmed target.
- `COMMAND_ACCEPTED_UNCONFIRMED` if any target has that status and none is `OUTCOME_UNKNOWN`; it remains visible in the overall summary.
- `OUTCOME_UNKNOWN` if any target is unknown; this has precedence over ordinary partial/failure summaries and stays visible in aggregate counts.

The implementation policy is sequential and fail-closed: stop on the first definite failure, rejection, or `OUTCOME_UNKNOWN`; every remaining resolved target after a stop is `NOT_STARTED`. Since current PVM response semantics are unverified, even a positive-looking response maps to `OUTCOME_UNKNOWN` and stops bulk dispatch. A later evidence-backed `COMMAND_ACCEPTED_UNCONFIRMED` mapping requires an owner decision on whether bulk may continue. ADR 0012 owns that safety policy; this ADR defines reporting. Do not retry automatically.

### Read/mutation freshness and ordering

The OperationCoordinator and CollectionCoordinator establish a target-generation barrier (ADR 0007/0012). A read started before a mutation for affected UUIDs must not publish over the post-mutation generation. Reads for affected targets wait for reconciliation or remain stale while a mutation is active. After dispatch, request a supported readback; readback of a desired state can confirm current state only under an approved contract and does not prove causality. A missing transition is not by itself proof of failure. No unsupported PVM polling/completion command is assumed.

### One-shot CLI exit categories

Propose stable exit categories for one-shot commands; interactive TUI presents typed results and has no per-operation process exit until the app exits.

| Exit code | Category | Meaning |
|---:|---|---|
| `0` | `SUCCESS` | Read completed as requested, or all requested mutations are confirmed complete. Help/version/config-only success also returns zero without collection. |
| `1` | `FAILED` | Definite request/collection failure or all attempted mutations definitely failed. |
| `2` | `REJECTED` | Invalid input, stale/ambiguous target, safety/confirmation rejection; no mutation dispatched. |
| `3` | `PARTIAL` | Partial read result, or confirmed successes mixed with definite failures/`NOT_STARTED`; no unknown outcome. |
| `4` | `OUTCOME_UNKNOWN` | Any post-dispatch unknown or accepted-but-unconfirmed mutation. This takes precedence over other aggregate categories. |

Exact numeric compatibility remains subject to CLI review, but categories must be stable and truthful. Do not return zero for a handled failure. A read-only non-TTY invocation performs one bounded collection only; no background poll changes its exit/result after output.

## User and diagnostic channels

- User output identifies category, partial/stale sections, per-target counts/reasons, and whether command acceptance or completion is known.
- Diagnostics use a safe operation ID, source/category, elapsed time, and safe PVM errno/exit information. Never log passwords/tokens/login XML or unreviewed full payloads.
- Preserve internal exception chaining; sanitize at display/log boundaries.
- Retry timing is ADR 0014; worker/process mechanics are ADR 0007; mutation admission/confirmation is ADR 0012.

## Validation required

Fake executable/provider tests for output/exit combinations, definite vs unknown result mapping, partial source collection, stop-on-first behavior, remaining `NOT_STARTED`, accepted-unconfirmed aggregation, unknown precedence and exit categories. Confirm PVM response/exit/action-ID/completion semantics with authorized target captures before mapping real operations to `SUCCEEDED` or `FAILED`.

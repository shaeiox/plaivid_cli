# ADR 0012 — Security and Mutation Safety Policy

- **Status:** Implemented locally; credential transport/security acceptance and PVM operation semantics remain blocked/pending
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Product/security owner; PVM administrator confirms authorization and supported credential/operation contracts.

## Context and evidence

- **Repository fact:** current Popen uses argv without `shell=True`, but login password XML and session tokens are process arguments (`session.py:80–108`, `transport.py:99–107`).
- **Repository fact:** non-TTY confirmation currently returns true (`orchestrator.py:178–180`); mixed valid/invalid bulk selectors can still execute valid targets (`vms.py:406–420`, `orchestrator.py:133–145`).
- **Unverified:** PVM credential input, process visibility, sudo/authorization, freshness requirements, and whether successful command replies mean acceptance or completion.

## Decision proposal

### Secret and privilege policy

- Treat passwords/tokens as secret from collection through storage, process launch, errors, logs and tests. Never emit them in diagnostics, exception strings, UI status, test output or shell history.
- Preserve argv-based invocation and never use a shell to compose PVM commands. Resolve/validate trusted executable paths and serialize/validate XML safely.
- **Release blocker:** current password/token argv exposure is unresolved. Before host authentication or release, establish and verify an approved PVM-supported credential path or obtain explicit security acceptance of the exposure after target process-visibility review. Do not invent stdin, environment, file-descriptor, or alternate sbell support.
- Keep UI unprivileged where possible; grant only required local PVM command access and verify executable ownership/sudo rules. No client-side role check is authorization; PVM remains authoritative.
- Session-cache design/lifetime is separate from app persistence (ADR 0008). This ADR owns secret protection and mutation policy, not storage technology.

### Canonical target and freshness gate

- Resolve every selector completely before any action. Reject the entire request if a selector is missing, ambiguous, invalid, duplicate/ambiguous UUID, or if only part of the requested set resolves. Do not act on a partial subset.
- Bind interactive confirmation to the exact action, ordered canonical UUID set, and the object-inventory generation/freshness shown to the user—not to row numbers, mutable names, or the selector text `all` alone. If inventory generation, target membership, state evidence, or operation parameters change before dispatch, invalidate confirmation and require a fresh resolution/confirmation.
- Every mutation requires a current, successful, unambiguous object record for each target. A destructive bulk operation additionally requires a complete, non-partial, non-stale object inventory within a product-approved maximum age. No numeric age is approved yet; until one is set, destructive bulk admission is rejected. If object/process evidence disagrees for a target, preserve both facts and reject that target until safe policy/evidence resolves the conflict; a helper row never overwrites object state (ADR 0004/0005/0014).
- Confirmation displays the exact action and canonical targets, including count and a complete inspectable list. No confirmation may silently carry across a refresh or be replayed for a different action/set.

### Risk and confirmation policy for the six actions

These are client safety classifications based on intended operational impact, not claims that PVM command semantics have been live-verified. Exact effects/permissions remain subject to vendor/host evidence. In the first Change, all six mutations are excluded.

| Action | Proposed risk | Interactive TUI confirmation | Bulk confirmation / gate |
|---|---|---|---|
| **Start** | Moderate: can consume host capacity and change VM runtime state | Exact single UUID request is explicit intent; no extra modal. | Always bind confirmation to full UUID set and fresh complete inventory. |
| **Stop** | High: interrupts a workload | Confirm exact action and UUID, including single target. | Same confirmation plus fresh complete inventory; stop on first failure/unknown. |
| **Kill** | Critical: abrupt termination may lose guest work | Strong action-specific confirmation even for one UUID. | Same, show complete set and freshness; stop on first failure/unknown. |
| **Reset** | High: abrupt workload interruption | Confirm exact action and UUID, including single target. | Same confirmation plus fresh complete inventory; stop on first failure/unknown. |
| **Pause** | High: suspends workload progress/availability | Confirm exact action and UUID, including single target. | Same confirmation plus fresh complete inventory; stop on first failure/unknown. |
| **Resume** | Moderate: resumes workload and can consume capacity | Exact single UUID request is explicit intent; no extra modal. | Always bind confirmation to full UUID set and fresh complete inventory. |

These differences do not grant authorization or imply `APPLIES_TO` is reliable. A future command must match a verified PVM contract. Any non-TTY mutation is rejected by default; if unattended mutation is later approved, it must consume an explicit approval bound to the exact action, canonical UUID set, and inventory generation. A generic “yes/force” detached from that plan is insufficient.

### Bulk execution and ordering

- Initially execute one target per supported action invocation; no PVM bulk command/idempotency guarantee is assumed.
- Process the deterministic confirmed UUID order sequentially. Stop on the first definite failure, rejection, or `OUTCOME_UNKNOWN`; mark every remaining target `NOT_STARTED`. A positive-looking response without a verified acceptance contract is `OUTCOME_UNKNOWN` and stops the sequence. `COMMAND_ACCEPTED_UNCONFIRMED` may be used only after owner evidence proves acceptance; continuation policy must then be explicitly approved. No automatic retry is permitted.
- OperationCoordinator owns mutation admission/lifecycle. It serializes mutations and establishes a generation barrier with CollectionCoordinator: pre-mutation reads for affected targets cannot publish after dispatch; affected reads wait for post-operation reconciliation or remain marked stale. The mechanics/worker lifetime are ADR 0007; typed outcomes and exits are ADR 0013.
- A response that only acknowledges command acceptance is not confirmed completion. Report `COMMAND_ACCEPTED_UNCONFIRMED`; mark `SUCCEEDED` only if the verified command contract or subsequent supported readback proves the requested terminal state. If acceptance/completion cannot be established after dispatch, use `OUTCOME_UNKNOWN`. Do not invent polling commands, completion guarantees, idempotency tokens, or automatic retries.
- After dispatch timeout/cancellation/ambiguous response, do not resubmit. Reconcile with an approved read; an observed state can update current state but does not retroactively prove which command caused it.

## Consequences

- Existing unattended destructive workflows are not preserved as implicit consent. First Change is read-only, so no lifecycle operation is implemented there.
- Exact target/freshness requirements intentionally reject stale, partial or conflicted bulk sets rather than risking unintended targets.
- Credential argv exposure blocks authenticated target validation/release until resolved by verified support or explicit security acceptance.

## Unresolved / evidence required

Supported credential input and process visibility; sudo/executable trust; session-cache and eviction/logout policy; per-section age threshold; PVM source-conflict semantics; each action's acceptance/completion response semantics; readback timing; meaning of definite failure; authorization and audit requirements; whether a future non-TTY approval workflow is needed. No PVM idempotency or command-completion behavior is claimed here.

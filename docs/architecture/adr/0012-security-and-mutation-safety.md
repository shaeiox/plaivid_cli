# ADR 0012 — Security and Mutation Safety Policy

- **Status:** Implemented locally; credential transport/security acceptance and PVM operation semantics remain blocked/pending
- **Date:** 2026-10-30 (review correction)
- **Decision owner:** Product/security owner; PVM administrator confirms authorization and supported credential/operation contracts.

## Context and evidence

- **Repository fact:** current Popen uses argv without `shell=True`, but login password XML and session tokens are process arguments (`session.py:80–108`, `transport.py:99–107`).
- **Historical legacy fact:** retired `orchestrator.py` implicitly accepted non-TTY prompts; the supported runtime no longer asks for confirmation. Mixed/invalid selectors are rejected by current code.
- **Unverified:** PVM credential input, process visibility, sudo/authorization, freshness requirements, and whether successful command replies mean acceptance or completion.

## Decision proposal

### Secret and privilege policy

- Treat passwords/tokens as secret from collection through storage, process launch, errors, logs and tests. Never emit them in diagnostics, exception strings, UI status, test output or shell history.
- Preserve argv-based invocation and never use a shell to compose PVM commands. Resolve/validate trusted executable paths and serialize/validate XML safely.
- **Release blocker:** current password/token argv exposure is unresolved. Before host authentication or release, establish and verify an approved PVM-supported credential path or obtain explicit security acceptance of the exposure after target process-visibility review. Do not invent stdin, environment, file-descriptor, or alternate sbell support.
- Keep UI unprivileged where possible; grant only required local PVM command access and verify executable ownership/sudo rules. No client-side role check is authorization; PVM remains authoritative.
- Session-cache design/lifetime is separate from app persistence (ADR 0008). This ADR owns secret protection and mutation policy, not storage technology.

### Canonical target and freshness gate

- Resolve every selector completely before any action. Reject the entire request if a selector is missing, ambiguous, invalid, duplicated, or only partially resolved. Do not act on a partial subset.
- Bind the action and ordered canonical UUID set to a current inventory generation and freshness bound. If generation, target membership or state evidence changes before dispatch, reject the plan and require fresh resolution. No separate confirmation or approval is requested for VM or Lite Desktop actions; choosing a TUI action or issuing a CLI lifecycle command is the operator's intent.
- Every mutation requires a current, unambiguous object record for each target. Bulk also requires complete, non-partial inventory and an explicitly configured positive maximum age. If object/process evidence disagrees, preserve both and reject that VM until resolved (ADRs 0004/0005/0014). A Desktop mutation uses the Desktop section, not a forged VM inventory record.
- The Desktop page displays selected/all scope, count and full target UUIDs; name search never restricts the unfiltered all-target set. There is no modal, phrase, `--approve` flag or other confirmation step.

### Risk classification without confirmation prompts

Risk labels are informational, not authorization or a claim of verified PVM semantics. Start and Resume are moderate; Stop, Reset, Pause are high; Kill is critical. All six may dispatch after explicit action selection and the same inventory/target checks; none has an extra prompt. PVM session authorization remains authoritative. The supplied Lite Desktop request shapes are candidates, not evidence of successful applicability; no live mutation was performed to verify them here.

### Bulk execution and ordering

- Execute one target per supported PVM invocation; no PVM bulk command/idempotency guarantee is assumed. Within a validated batch, dispatch targets through a bounded rolling worker window with `PLAIVID_MAX_CONCURRENCY` (default `3`). Outcomes are always returned in the deterministic planned UUID order even though completion order may differ.
  - **Fast action trigger (`PLAIVID_ACTION_TIMEOUT`, default 10.0s).** Lifecycle mutations (`vm/start`, `vm/stop`, `vm/reset`, `vm/pause`, `vm/resume`, `vm/kill`) use a short trigger deadline rather than waiting for slow guest OS ACPI shutdowns, while read queries retain `PLAIVID_CMD_TIMEOUT` (default 30.0s).
  - **Single batch barrier.** Validate the immutable plan, call `begin_mutation()` exactly once for the complete target set before any work is submitted, and call `end_mutation()` exactly once after every in-flight future settles. A plan cannot be independently revalidated or barrier-opened by worker threads.
  - **Task progress.** A target remains `QUEUED` until a worker picks it up and emits `RUNNING` immediately before that target's dispatch. A queued future successfully cancelled after a batch stop, and every never-submitted target, is `NOT_STARTED` (`SKIPPED`). Already-running requests retain their own settled outcome; they are never mislabeled skipped.
  - **Target-scoped failure or timeout with healthy daemon — continue.** `is_daemon_alive()` must establish that `sballd` is responsive. With a healthy daemon, a dispatched non-session failure is target-scoped unless it carries a specifically listed session errno/code. This includes target VM-state failures (`errno 146`) and target-specific storage/disk failures, even when their errno is not yet known to the client. A `PVM_COMMAND_TIMEOUT` remains `OUTCOME_UNKNOWN`, is never retried, and does not prevent other targets from proceeding.
  - **Session-scoped failure — stop refilling.** Session/authorization/contract errnos 39, 40, 106, 107, 108, 137, and 185, undispatched failures, and `PROCESS_START_FAILED` stop new submissions. The supervisor cancels work not yet started, waits for already-running requests, and marks only undispatched targets `NOT_STARTED` (`SKIPPED`).
  - **Daemon offline — stop refilling immediately.** When a failed/unknown action or timeout is followed by `is_daemon_alive() == False`, the current target is marked `FAILED` with code `DAEMON_OFFLINE`. No additional work is submitted; active siblings settle, and never-dispatched targets are `SKIPPED` with `Daemon Offline`. Skip the post-batch PVM read when daemon unavailability has been established.
  - **Fail-closed session classification.** Explicit session errnos/codes stop the batch; other dispatched errors default to target scope only while daemon liveness is healthy. A daemon-offline sentinel or pre-dispatch result cannot be target-scoped. Classification uses structured errno/code/dispatch/liveness data, never display-message parsing, and is shared by VM and Desktop execution.
- No automatic retry is permitted. `OUTCOME_UNKNOWN` retains aggregate precedence so uncertainty is not hidden by successful siblings. Acceptance/completion interpretation remains subject to the existing evidence requirements in ADR 0013.
- OperationCoordinator owns mutation admission/lifecycle and serializes operation groups through its shared lane. The batch-level generation barrier prevents pre-mutation reads from publishing over mutation state; affected reads wait for post-operation reconciliation or remain marked stale. The bounded worker pool only parallelizes targets inside the same operation and barrier. Worker/process lifetime is ADR 0007; typed outcomes/exits are ADR 0013.
- A response that only acknowledges command acceptance is not confirmed completion. Report `COMMAND_ACCEPTED_UNCONFIRMED`; mark `SUCCEEDED` only if the verified command contract or subsequent supported readback proves the requested terminal state. If acceptance/completion cannot be established after dispatch, use `OUTCOME_UNKNOWN`. Do not invent polling commands, completion guarantees, idempotency tokens, or automatic retries.
- After dispatch timeout/cancellation/ambiguous response, do not resubmit. Reconcile with an approved read; an observed state can update current state but does not retroactively prove which command caused it.

## Consequences

- VM lifecycle CLI commands may run unattended when explicitly invoked with targets; they do not prompt. Operators must control access to their session and automation. The historical first Change was read-only.
- Exact target/freshness requirements intentionally reject stale, partial or conflicted bulk sets rather than risking unintended targets.
- Credential argv exposure blocks authenticated target validation/release until resolved by verified support or explicit security acceptance.

## Unresolved / evidence required

Supported credential input and process visibility; sudo/executable trust; session-cache and eviction/logout policy; per-section age threshold; PVM source-conflict semantics; each action's acceptance/completion response semantics; readback timing; meaning of definite failure; authorization and audit requirements; whether additional deployment-level safeguards are needed. No PVM idempotency or command-completion behavior is claimed here.

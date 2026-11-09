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

- Initially execute one target per supported action invocation; no PVM bulk command/idempotency guarantee is assumed.
- Process the deterministic resolved UUID order sequentially, **isolating each target**. A bulk execution sends one PVM request per target, so the only state shared across the batch is the session.
  - **Target-scoped failure — continue the batch.** A failure that establishes something about *one target* is recorded against that target and the loop proceeds to the next one. This covers PVM VM-state rejections where the PVM answered cleanly about that VM (`errno 146`, "VM '<name>' is ...", e.g. a start on an already running VM, which is routine in a bulk stop). The failure is reported per target and the batch aggregate reflects the mixture (`PARTIAL` when at least one target succeeded).
  - **System/session-scoped failure — abort the batch.** A failure of the session, the credential, the request contract, or the local transport makes every remaining request fail identically, so the batch stops and every remaining target is `NOT_STARTED`. This covers `errno` 39 (UnAuthorized), 40 (permission denied / malformed params), 106/107 (bad module/command), 108 (local sbell permission), 137 (bad credentials), 185 (session cap), `PROCESS_START_FAILED`, and any failure recorded before a request reached PVM. `OUTCOME_UNKNOWN` (including `errno`-less transport failures) aborts, because an unverified outcome must be reconciled before further commands are issued.
  - **Unrecognised `errno` aborts**, i.e. the classifier fails closed. A newly observed error number must not be assumed safe to continue past.
  - Classification uses the `errno` retained on the outcome, never display text. The policy is a pure domain function (`domain/policies.py`), applied identically by the VM and Desktop executors.
- A positive-looking response without a verified acceptance contract is `OUTCOME_UNKNOWN` and stops the sequence. `COMMAND_ACCEPTED_UNCONFIRMED` may be used only after owner evidence proves acceptance; continuation policy for that state must then be explicitly approved. No automatic retry is permitted.
- OperationCoordinator owns mutation admission/lifecycle. It serializes mutations and establishes a generation barrier with CollectionCoordinator: pre-mutation reads for affected targets cannot publish after dispatch; affected reads wait for post-operation reconciliation or remain marked stale. The mechanics/worker lifetime are ADR 0007; typed outcomes and exits are ADR 0013.
- A response that only acknowledges command acceptance is not confirmed completion. Report `COMMAND_ACCEPTED_UNCONFIRMED`; mark `SUCCEEDED` only if the verified command contract or subsequent supported readback proves the requested terminal state. If acceptance/completion cannot be established after dispatch, use `OUTCOME_UNKNOWN`. Do not invent polling commands, completion guarantees, idempotency tokens, or automatic retries.
- After dispatch timeout/cancellation/ambiguous response, do not resubmit. Reconcile with an approved read; an observed state can update current state but does not retroactively prove which command caused it.

## Consequences

- VM lifecycle CLI commands may run unattended when explicitly invoked with targets; they do not prompt. Operators must control access to their session and automation. The historical first Change was read-only.
- Exact target/freshness requirements intentionally reject stale, partial or conflicted bulk sets rather than risking unintended targets.
- Credential argv exposure blocks authenticated target validation/release until resolved by verified support or explicit security acceptance.

## Unresolved / evidence required

Supported credential input and process visibility; sudo/executable trust; session-cache and eviction/logout policy; per-section age threshold; PVM source-conflict semantics; each action's acceptance/completion response semantics; readback timing; meaning of definite failure; authorization and audit requirements; whether additional deployment-level safeguards are needed. No PVM idempotency or command-completion behavior is claimed here.

# ADR 0012 — Security and Mutation Safety Policy

- **Status:** Proposed
- **Date:** 2026-10-30
- **Decision owner:** Product/security owner; PVM administrator confirms authorization and credential constraints.

## Context and evidence

- **Repository fact:** current `Popen` uses argv without `shell=True`, but login password XML and session tokens are passed as process arguments (`session.py:80–108`, `transport.py:99–107`).
- **Repository fact:** non-TTY confirmation returns true (`orchestrator.py:178–180`); mixed valid/invalid bulk selection can still execute valid targets and suppress the selector error (`vms.py:406–420`, `orchestrator.py:133–145`).
- **Repository fact:** PVM session authorization is relied on; the CLI has no independent role model. Action applicability metadata is not enforced by dispatch.
- **Unverified:** PVM-supported secure credential input, host sudo policy, user/process visibility, session invalidation and authorization semantics.

## Decision proposal

### Secrets and privilege

- Treat tokens/passwords as secrets at source. Never include them in logs, exception strings, status text, test output, shell history or diagnostic dumps.
- Preserve argument-list subprocess invocation and never use shell interpolation for PVM calls. Validate executable selection and XML identifiers/serialization.
- Before release, establish a supported password/token delivery mechanism with PVM owners. Until process-argument exposure is assessed/accepted or a supported safer mechanism is verified, credential handling remains a release blocker. Do not invent stdin flags or alternate sbell contracts.
- Run the CLI under the least-privileged user that can invoke only required PVM tools; do not elevate the whole UI unless required. Validate executable ownership, path and sudo rules.
- Credential storage implementation is separately unresolved under ADR 0008; this ADR owns its confidentiality, lifetime and redaction requirements.

### Mutation safety

- Resolve all requested VM targets before dispatch. By default, any unresolved, ambiguous or invalid selector rejects the entire operation; never silently apply to a partial subset.
- Interactive destructive operations require an explicit affirmative confirmation that identifies the action and resolved targets. Display the complete set or a safe paginated/expandable representation with an exact count.
- Non-interactive destructive requests **fail closed by default**. If automation use is later approved, it requires explicit machine-readable intent/force policy, unambiguous target resolution, auditable caller intent, and documented authorization. TTY absence is not consent.
- Serialize mutations initially. Preserve per-target result and safe cause. Do not retry mutations automatically. On a timeout after dispatch, report outcome unknown and refresh/inspect state before any user-directed retry (ADR 0007/0013).
- PVM remains the authorization authority. Local action-state rules can prevent obviously invalid requests and improve UX, but must not be presented as authorization or as a substitute for server enforcement.

## Consequences

- Some existing one-shot destructive workflows will require an explicit confirmation/automation design rather than silently executing.
- Safer all-or-nothing target resolution can reject requests that current code partially executes; this is intentional in the proposal.
- Session cache and command-argument secret risk must be resolved before operational rollout.

## Unresolved / evidence required

PVM credential interface; host process visibility and sudo semantics; PVM role/authorization guarantees; supported automation use cases; confirmation wording and exact behavior; audit/privacy policy; secure session storage; executable allowlist and installation ownership. This ADR is not accepted until product/security owners approve a practical policy.

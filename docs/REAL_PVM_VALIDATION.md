# Real-PVM validation plan (owner-run only)

**Status: PENDING MANUAL PVM VALIDATION.** This document is a plan, not a report of host testing. The implementation session did not connect to a real PVM host, production VM, Sball/PVM cluster, SSH endpoint, or production system. No host commands or lifecycle actions listed below have been run. Local pytest, fake-process tests, synthetic fixtures, and Textual Pilot do not verify the installed PVM contract.

Complete this checklist only by the project owner or an authorized operator, against an approved non-production PVM environment first. Use disposable VMs and an approved maintenance window. Keep vendor/operator guidance available. Do not test an uncertain command against production.

## Preconditions and evidence handling

- **PENDING MANUAL PVM VALIDATION** — Record the PVM/Sball software versions, Linux distribution, Python version, local `sbell` and `pvm-running-vms` executable paths/versions, and operator role. Confirm the package's Python >=3.12 requirement is satisfied.
- **PENDING MANUAL PVM VALIDATION** — Confirm the test host is explicitly authorized, not a production cluster, and has recoverable disposable VMs. Record an owner-approved rollback procedure outside this CLI.
- **PENDING MANUAL PVM VALIDATION** — Review the exact configured local argv and permissions. Do not substitute SSH, remote collection, undocumented `sbell` arguments, or an assumed credential transport.
- **PENDING MANUAL PVM VALIDATION** — Decide whether the known password/token-in-argv exposure is acceptable for the test account and host. Keep the default gate closed unless an authorized owner explicitly accepts this risk. Do not capture or attach raw process listings containing a secret.
- **PENDING MANUAL PVM VALIDATION** — Evidence may include redacted terminal output, sanitized request/response examples, observed state before/after, and timestamps. Remove usernames, passwords, session tokens, JWTs, private IPs, and VM/customer identifiers unless the owner explicitly permits them.

## Local read contract checks

1. **PENDING MANUAL PVM VALIDATION** — With an authorized test session, run the one-shot inventory command on the approved host. Compare the parsed defined objects, UUIDs, names, object states, and quality issues with the authoritative PVM view. Confirm an empty successful inventory is shown as empty, not as a collection failure.
2. **PENDING MANUAL PVM VALIDATION** — Compare `pvm-running-vms` output with process-observation columns. Confirm process rows remain separate from object-store state, unmatched process rows do not create VM objects, and duplicate/conflicting source rows are visible or excluded fail-closed as documented.
3. **PENDING MANUAL PVM VALIDATION** — Run the host view and compare reported `sball_state`, node state, host identity, CPU/RAM/storage, load, and monitoring metrics with approved host tools. Confirm `sball_state=quorate` is displayed as the literal Sball value only; do not interpret it as universal membership or service health.
4. **PENDING MANUAL PVM VALIDATION** — Run detail on one disposable VM and compare UUID, object state, CPU/memory, disks, NICs, console fields, and optional process observations. Verify absent or unsupported fields display unavailable rather than invented zero/healthy values.
5. **PENDING MANUAL PVM VALIDATION** — Inspect the audit view only if the configured SQLite database exists and its schema is approved. Confirm Plaivid opens it read-only, does not create/modify tables, and returns bounded newest-first rows. Unsupported or unavailable schema must leave other views usable.
6. **PENDING MANUAL PVM VALIDATION** — Compare CLI JSON and human output for current, partial, stale, and unavailable cases. Verify status/source/generation/error metadata remains explicit and credentials/tokens are absent.

## Session and security checks

1. **PENDING MANUAL PVM VALIDATION** — Confirm login is blocked with no argv-risk acknowledgement and that the block occurs before any local `sbell` child starts.
2. **PENDING MANUAL PVM VALIDATION** — If the owner approves a controlled test of current `sbell` login, use a disposable least-privilege account and explicitly acknowledge the argv exposure. Verify the installed process-listing/security policy's actual behavior without recording the password or token. Treat any process-visible credential as a security finding, not as acceptable protection.
3. **PENDING MANUAL PVM VALIDATION** — Verify the token cache is under the expected user state directory, directory/file permissions are user-only, no password is persisted, and replacing/removing the cache behaves as documented. Test with non-sensitive test credentials only.
4. **PENDING MANUAL PVM VALIDATION** — Revoke/expire the test session through the approved PVM operator workflow and confirm the CLI reports a login-required condition. Confirm session-cap responses do not delete another session or silently retry login.
5. **PENDING MANUAL PVM VALIDATION** — Verify all expected failure output is redacted, including synthetic or specially designated test values. Do not intentionally inject production secrets into logs.

## Lifecycle operation checks

The local source establishes only the request forms; acceptance and completion semantics remain unverified. Use one disposable VM per case, record its authoritative state before/after independently, and obtain explicit owner approval before each action. Do not batch the initial contract checks.

For each of `start`, `stop`, `kill`, `reset`, `pause`, and `resume`:

1. **PENDING MANUAL PVM VALIDATION** — Verify the expected precondition and current VM identity using the approved PVM operator interface. Confirm the CLI targets the same canonical UUID.
2. **PENDING MANUAL PVM VALIDATION** — Submit one action only after reviewing its action/UUID confirmation. Record the CLI's response and operation state. The current implementation maps every post-dispatch response to `OUTCOME_UNKNOWN`. Only owner/vendor evidence and a reviewed code change may establish a narrower acceptance or completion mapping.
3. **PENDING MANUAL PVM VALIDATION** — Verify actual state change and side effects independently. Confirm that stop/pause/kill/reset semantics, guest data effects, cancellation, and expected recovery match the product's documented contract. Never infer idempotency from one response.
4. **PENDING MANUAL PVM VALIDATION** — Check one intentionally rejected but safe precondition, if and only if the vendor/owner identifies a safe disposable test. Confirm a post-dispatch ambiguous or timeout result is reported as `OUTCOME_UNKNOWN`; reconcile independently and do not retry blindly.
5. **PENDING MANUAL PVM VALIDATION** — Verify `start`/`resume` explicit single-target intent, Stop/Reset/Pause single-target confirmation, and the distinct critical Kill confirmation. Confirm each approval covers the exact action and canonical UUID.

Bulk behavior is intentionally deferred until individual action contracts and inventory assumptions are accepted:

- **PENDING MANUAL PVM VALIDATION** — Confirm bulk remains denied when `PLAIVID_MAX_INVENTORY_AGE_SECONDS` is unset, inventory is partial/stale, a target is ambiguous, or the approval UUID sequence differs.
- **PENDING MANUAL PVM VALIDATION** — On a separately approved disposable test set, verify target order, exact approval phrase, one-at-a-time dispatch, stop-on-unknown behavior, and remainder `NOT_STARTED`. Do not test continuation after an accepted-but-unconfirmed result unless a verified acceptance contract and a separate owner-approved continuation policy have first been documented.
- **PENDING MANUAL PVM VALIDATION** — Verify post-operation collection cannot publish a pre-operation read over newer state and that an outcome-unknown target is reconciled before any operator-directed retry.

## Failure and shutdown checks

- **PENDING MANUAL PVM VALIDATION** — On the approved host, verify behavior for missing local executable, local permission denial, nonzero child exit, bounded output, malformed XML, timeout, session expiry, absent audit database, and orderly TUI shutdown. Use non-production data only.
- **PENDING MANUAL PVM VALIDATION** — Confirm timeouts reap local child processes or report unresolved cleanup; an action timeout after a started request is not presented as definite failure or success.
- **PENDING MANUAL PVM VALIDATION** — Confirm slow local reads do not freeze the TUI and leaving live Fleet/Host views stops irrelevant periodic requests; Audit is read on tab entry or explicit refresh only.

## Unresolved contracts / acceptance record

- **PENDING MANUAL PVM VALIDATION** — Confirm installed `sbell` envelope/status semantics, response `action_id` semantics, and whether any successful response means accepted, completed, or something else.
- **PENDING MANUAL PVM VALIDATION** — Confirm the `user/objects` query/result schema, UUID uniqueness, field names/state vocabulary, detail lookup behavior, and any access-control constraints.
- **PENDING MANUAL PVM VALIDATION** — Confirm `pvm-running-vms` output format and whether its process evidence can be correlated by UUID under all supported versions.
- **PENDING MANUAL PVM VALIDATION** — Confirm `sball/show` meanings and which metrics/storage/network values are authoritative, optional, or unavailable on the deployed version.
- **PENDING MANUAL PVM VALIDATION** — Confirm the six request forms, allowed states, side effects, completion/readback contract, idempotency, and safe retry policy with the product owner/vendor.
- **PENDING MANUAL PVM VALIDATION** — Confirm acceptable credential handling and process-inspection risk for the deployment. No alternative transport is assumed by this code.
- **PENDING MANUAL PVM VALIDATION** — Record an owner decision for each item: accepted, rejected, or follow-up required; include version, timestamp, evidence location, and approver. Keep this plan pending until those decisions are complete.

## Current implementation-only verification

The local suite uses fake providers, fake child runners, synthetic XML/text fixtures, temporary SQLite databases, and Textual Pilot. It tests deterministic parsing, security gates, policy, collection barriers, result states, CLI serialization, and UI mounting. It does not contact any real PVM host. Real-PVM validation remains **PENDING MANUAL PVM VALIDATION**.

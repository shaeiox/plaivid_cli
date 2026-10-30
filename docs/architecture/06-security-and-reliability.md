# 06 — Security and Reliability Findings

**Status:** Source-based risk review; no runtime penetration test, PVM test, or target inspection was performed.

## Prioritized findings

| Priority | Finding | Evidence | Impact / validation |
|---|---|---|---|
| **Critical before operational rollout** | Non-TTY mode implicitly approves destructive operations | `App._confirm()` returns `True` when stdin is not a TTY (`orchestrator.py:178–180`). README claims destructive actions ask for confirmation. | Scripts/pipelines can execute stop/kill/reset without explicit confirmation. Define safe explicit policy (e.g., fail closed unless a deliberate force/confirmation flag is supplied); test TTY and non-TTY paths. |
| **High** | Partial bulk target resolution can execute valid targets while silently discarding invalid selectors | `vms.resolve_many()` returns targets and error together (`vms.py:406–420`); `_run_action()` ignores `errmsg` when targets exist (`orchestrator.py:133–145`). | A typo can produce an unintended subset operation. Validate all selectors and require explicit policy before any mutation; test mixed valid/invalid, duplicate, ambiguous, and empty targets. |
| **High** | Login password and session token are command-line arguments to the sbell child process | XML password is built in `session._login_params()` and passed to `transport.sbell()`; token is appended in `transport.sbell()` (`session.py:80–108`, `transport.py:99–104`). | Local users/process inspection, diagnostics or crash tooling may reveal secrets. Confirm PVM-supported safer input channels; until then minimize lifetime, prevent logging, assess process permissions, and document residual exposure. No undocumented stdin mode should be assumed. |
| **High** | Timeout kills only direct child and does not explicitly reap it | `_run()` kills `p` then raises without `communicate()/wait()` in timeout branch (`transport.py:66–77`). | Child cleanup/resource lifecycle may be incomplete; `sudo` or a wrapper could spawn descendants that remain. Verify on target, ensure process is waited/reaped and define process-group policy. |
| **High** | sbell return code is ignored | `_run()` returns `rc`; `sbell()` unpacks it but never checks it (`transport.py:99–107`). | Nonzero command exit with XML stdout is treated as an ordinary response; empty output without stderr may surface as generic parse failure. Establish observed contract and handle exit status explicitly without masking valid XML error envelopes. |
| **High** | No automated safety or regression tests | Only `tests/smoke.py`, which does not invoke actions; no test config/CI present. | Parser, bulk selector, error, session, renderer, and operation semantics can regress undetected. Build offline tests before adding operational features. |
| **High / product boundary** | Local privileged command model has no verified least-privilege/deployment policy | Default command is `sudo sbell` (`config.py:11–17`); docs say sbell requires root. | Confirm sudo policy, exact executable path/ownership, environment inheritance, and supported user model on PVM. Do not broaden privilege to the whole app process without need. |
| **Medium-high** | Broad catch/suppression can hide partial collection or mutation failures | Inventory enrichment suppresses errors (`vms.py:122–134`); bulk action catches exceptions and stores only failed VM names (`orchestrator.py:157–176`); session cache save/clear suppress filesystem errors (`session.py:36–67`). | User may see stale/incomplete data or lack actionable failure cause. Use explicit typed outcomes and diagnostics; retain/redact per-target error details. |
| **Medium-high** | Session file permission hardening is best-effort and occurs after replacement | `_save()` creates directory using ambient umask, replaces file, then attempts chmod 0600; errors are swallowed (`session.py:36–50`). | Window before chmod and directory permissions/symlink behavior need assessment. Define secure directory/file creation and supported OS semantics; no token should be printed/logged. |
| **Medium** | Collection path can repeat local privileged/API work frequently | `commands/overview.py:32–42`, `monitoring.py:87–175`, `vms.py:114–149`. | Increases local CPU, process churn and PVM daemon requests. Use measured cadence, request coalescing and last-good snapshots. |
| **Medium** | Action applicability metadata is not enforced by dispatch | `actions._Action.applies()` exists (`actions/__init__.py:34–39`), but `_run_action()` does not call it (`orchestrator.py:133–145`). | Invalid-state requests rely on backend rejection; user receives less predictable behavior. Decide whether applicability is UI guidance, local guard, or server-authoritative capability. |
| **Medium** | The local audit reader has separate access and schema assumptions | `logs.py:14, 23–56` opens a fixed default PVM path read-only and queries a `Log` table. | Deployment user may lack read access; schema/version and retention are not validated. Keep read-only, make access failures visible, and avoid logging sensitive message contents. |

## Subprocess and injection analysis

- **Positive, source-verified:** `Popen()` gets a list argv and does not set `shell=True` (`transport.py:66–70`). Ordinary shell metacharacters in params are therefore not shell-expanded by Python's subprocess call.
- `SBELL_CMD` and `RUNNING_VMS_CMD` are split with `shlex.split()` from environment variables (`config.py:14,17`). They allow configuring an executable and fixed argv; they do not pass through a shell, but an untrusted environment/configuration can select a different executable. Establish trusted configuration ownership and preferably resolve/validate executable paths.
- XML parameters are constructed as strings. Login username/password escapes `&`, `<`, and `>` (`session.py:16–17`); VM UUIDs are interpolated into XML/query text (`actions/base.py:43–44`, `vms.py:274–276`). Validate identifiers and serialize XML with an XML API rather than concatenation at an implementation phase. This is XML correctness/injection hardening, distinct from shell injection.
- `pvm-running-vms` output is parsed with a strict regular expression (`vms.py:94–111`). Unrecognized rows are silently skipped. Treat format drift as explicit data-quality status rather than assuming an empty running set.

## Authorization and destructive-action semantics

Current source relies on PVM authorization of the session for commands. There is no client-side role model. Six action modules exist; `stop`, `kill`, and `reset` are marked destructive, but non-TTY confirmation is implicitly accepted. Bulk operation has a single interactive prompt and shows up to eight VM names plus a count. There is no per-target confirmation or dry-run.

Recommended policy to validate: make mutation intent explicit, default unattended execution to fail closed, show a complete or safely paginated resolved target list before action, reject incomplete selector resolution unless user explicitly chooses otherwise, and distinguish timeout/unknown completion from definite failure. Do not blindly retry mutations.

## Error propagation and retries

- Transport launch/timeout/parse errors use `TransportError`; PVM `<response>` failures use `Response.ok == False`. Some APIs convert errors to dictionaries or suppress them, so callers cannot consistently tell “unavailable”, “empty”, and “stale”.
- The only explicit retry is errno-185 login recovery: list existing sessions then retry login once, possibly evicting the first returned session (`session.py:107–123`). Confirm eviction ordering and user consent/policy with PVM owners.
- There are no general retries. Preserve that property until command idempotency, deduplication, and server timeout semantics are documented. A transport timeout after a mutation is an ambiguous outcome, not proof the action did not execute.
- Set timeout per operation based on measured behavior; the current single default is 30 seconds (`config.py:19–20`). Bound output size and collection overlap in a future implementation.

## Audit, diagnostics and resource cleanup

- The app reads PVM audit records but has no application diagnostic logger. The live audit DB does not necessarily capture local parse errors, TUI failures, timeouts, or rejected targets.
- Introduce stdlib logging with a redaction policy before adding `structlog`. Never emit password, token, raw login XML, or full sensitive PVM payload. Include operation ID, safe command name, elapsed time, exit status, PVM errno, and target UUID/name only if policy permits.
- Close SQLite connections in `finally` (current code does); isolate read-only URI/path handling and verify behavior for paths containing URI-sensitive characters (`logs.py:23–27`).
- Ensure subprocesses are waited/reaped, pipes are bounded/consumed, terminal mode is restored after interruption, and workers stop cleanly at app exit. Existing `_wait_or_quit()` has a `finally` restoring termios (`orchestrator.py:291–319`), but this is POSIX-only behavior and must be re-evaluated under Textual.

## Security verification required before operational rollout

1. Confirm supported sbell credential input and privilege model with PVM maintainers; do not guess undocumented alternatives.
2. Inspect process visibility and `sudo` behavior on the supported host; run safe tests with synthetic credentials only.
3. Test timeout, signal, child-process cleanup, malformed XML, nonzero exit plus output, and PVM error envelopes with fake executables.
4. Decide session file ownership/mode/directory and token retention/logout behavior; inspect no secrets in logs, errors, terminal screenshots, or test artifacts.
5. Exercise destructive confirmation, mixed bulk selectors, per-target failures, and uncertain timeout outcomes with a fake provider before any real VM action.

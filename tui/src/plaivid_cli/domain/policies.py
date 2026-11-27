"""Pure operation risk and freshness policies."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from plaivid_cli.domain.models import (
    Action,
    ActionPolicy,
    OperationState,
    RiskLevel,
    TargetOutcome,
)

_POLICIES = {
    Action.START: ActionPolicy(Action.START, RiskLevel.MODERATE),
    Action.STOP: ActionPolicy(Action.STOP, RiskLevel.HIGH),
    Action.KILL: ActionPolicy(Action.KILL, RiskLevel.CRITICAL),
    Action.RESET: ActionPolicy(Action.RESET, RiskLevel.HIGH),
    Action.PAUSE: ActionPolicy(Action.PAUSE, RiskLevel.HIGH),
    Action.RESUME: ActionPolicy(Action.RESUME, RiskLevel.MODERATE),
}


def action_policy(action: Action) -> ActionPolicy:
    return _POLICIES[action]


def bulk_may_dispatch(
    *, action: Action, is_bulk: bool, complete: bool, fresh: bool,
    max_age_seconds: float | None,
) -> bool:
    """Return whether a bulk plan has the required inventory evidence."""
    if not is_bulk:
        return True
    if max_age_seconds is None or max_age_seconds <= 0:
        return False
    if not complete or not fresh:
        return False
    # The caller determines freshness against max_age_seconds; accepting the
    # configured age here ensures no bulk operation bypasses product policy.
    return action in _POLICIES


# --------------------------------------------------------------------------- #
# Failure scope policy (scoped continuation for bulk execution)
# --------------------------------------------------------------------------- #
#
# A bulk operation sends one PVM request per target (docs/SBELL-SABAD.md §4:
# ``vm/stop`` takes a bare ``<vm_key>``, there is no batch command). The only
# state shared by every target in a batch is the session. So the decision that
# matters is whether a failure says something about *one target* or about *the
# session/wire*:
#
# * TARGET scope -> the PVM answered cleanly about this VM (e.g. errno 146
#   "VM is in an invalid state"). Every other target is unaffected, so the batch
#   continues and the failure is reported per target.
# * SESSION scope -> the credential/session/daemon is unusable. Stop scheduling
#   new targets; already-dispatched work is allowed to settle.
# * TARGET scope -> any other error from a dispatched target while the daemon is
#   responsive. This deliberately includes unrecognized PVM errnos so disk and
#   other target-local errors cannot abort unrelated targets.
#
# Explicit session errnos/codes are the fail-closed boundary. Pre-dispatch
# failures are never target-scoped, regardless of any attached errno.

#: sbell errnos that describe one target and must not abort a batch.
TARGET_SCOPED_ERRNOS: frozenset[str] = frozenset(
    {
        "146",  # VM '<name>' is ... (VM-state error, e.g. start on a running VM)
    }
)

#: sbell errnos that make every subsequent request fail. A non-session,
#: dispatched failure falls back to target scope once the daemon is known healthy.
SESSION_SCOPED_ERRNOS: frozenset[str] = frozenset(
    {
        "39",   # UnAuthorized: no/invalid session
        "40",   # Permission denied (usually a malformed params body)
        "106",  # Bad module name
        "107",  # Bad command name
        "108",  # Local sbell permission denied (UNIX socket)
        "137",  # Username/Password is not correct
        "185",  # sessions exceeds the threshold
    }
)


SESSION_SCOPED_CODES: frozenset[str] = frozenset(
    {
        "PROCESS_START_FAILED",
        "DAEMON_OFFLINE",
        "CREDENTIAL_ARGV_ACK_REQUIRED",
        "WORKER_FAILURE",
    }
)


class FailureScope(StrEnum):
    """Whether a per-target failure is local to that target or batch-wide."""

    TARGET = "target"
    SESSION = "session"


#: Error code raised when an action trigger exceeds ``PLAIVID_ACTION_TIMEOUT``.
COMMAND_TIMEOUT_CODE = "PVM_COMMAND_TIMEOUT"

#: Sentinel stop reason used when the fast daemon liveness probe fails.
DAEMON_OFFLINE_REASON = "Daemon Offline"


def classify_failure(
    errno: str | None,
    *,
    code: str | None = None,
    default: FailureScope = FailureScope.TARGET,
) -> FailureScope:
    """Classify a dispatched failure using explicit session identifiers.

    A healthy daemon plus an error that is not known to be session-wide is
    treated as target-scoped. This includes previously unknown PVM errnos, which
    is required to isolate target-specific storage/disk failures. Callers must
    reject undispatched failures and daemon-offline outcomes before this helper.
    """
    if errno is not None and errno.strip() in SESSION_SCOPED_ERRNOS:
        return FailureScope.SESSION
    if code is not None and code.strip() in SESSION_SCOPED_CODES:
        return FailureScope.SESSION
    if errno is not None and errno.strip() in TARGET_SCOPED_ERRNOS:
        return FailureScope.TARGET
    return default


def is_target_scoped_error(outcome: TargetOutcome, *, daemon_alive: bool = True) -> bool:
    """True when a failure is isolated to a dispatched target.

    Session/auth/contract errnos and local process-start failures stop further
    submission. Any other dispatched error is target-scoped only while the
    daemon liveness probe is healthy. Healthy-daemon action timeouts remain
    uncertain but do not block other targets; they are never retried.
    """
    if not daemon_alive or not outcome.dispatched:
        return False
    scope = classify_failure(
        outcome.errno,
        code=outcome.code,
        default=FailureScope.TARGET,
    )
    return scope is FailureScope.TARGET


#: Outcome states that end a batch unless the failure is target-scoped.
STOP_STATES: frozenset[OperationState] = frozenset(
    {
        OperationState.FAILED,
        OperationState.REJECTED,
        OperationState.OUTCOME_UNKNOWN,
    }
)


def outcome_stops_batch(outcome: TargetOutcome, *, daemon_alive: bool = True) -> bool:
    """True when this outcome must abort the rest of a bulk batch."""
    if not daemon_alive:
        return True
    return outcome.state in STOP_STATES and not is_target_scoped_error(
        outcome, daemon_alive=daemon_alive
    )


def batch_stop_reason(outcome: TargetOutcome, *, daemon_alive: bool = True) -> str:
    """Short, operator-safe reason recorded on targets skipped by a stop.

    Shared by both executors so the VM and Desktop paths cannot diverge.
    """
    if not daemon_alive:
        return DAEMON_OFFLINE_REASON
    if outcome.state is OperationState.OUTCOME_UNKNOWN:
        return "earlier target left an unknown outcome that must be reconciled"
    return "an earlier target failed in a way that affects the whole session"


def bulk_must_stop(outcomes: Iterable[TargetOutcome]) -> bool:
    """True if any recorded outcome requires stopping the batch."""
    return any(outcome_stops_batch(outcome) for outcome in outcomes)

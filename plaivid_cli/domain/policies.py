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
# * SESSION scope -> the credential/session is unusable. Every remaining request
#   would fail identically, so the batch stops and the remainder is NOT_STARTED.
#
# ADR 0012/0013 carry the precise rules. Keep this list conservative: an unknown
# or unverified errno is treated as session-scoped so the app fails closed.

#: sbell errnos that describe one target and must not abort a batch.
TARGET_SCOPED_ERRNOS: frozenset[str] = frozenset(
    {
        "146",  # VM '<name>' is ... (VM-state error, e.g. start on a running VM)
    }
)

#: sbell errnos that make every subsequent request fail. Listed explicitly for
#: documentation and tests; anything not target-scoped is session-scoped anyway.
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


class FailureScope(StrEnum):
    """Whether a per-target failure is local to that target or batch-wide."""

    TARGET = "target"
    SESSION = "session"


#: Error code raised when an action trigger exceeds ``PLAIVID_ACTION_TIMEOUT``.
COMMAND_TIMEOUT_CODE = "PVM_COMMAND_TIMEOUT"

#: Sentinel stop reason used when the fast daemon liveness probe fails.
DAEMON_OFFLINE_REASON = "Daemon Offline"


def classify_failure(errno: str | None, *, default: FailureScope = FailureScope.SESSION) -> FailureScope:
    """Classify a PVM failure from its sbell errno.

    An absent or unrecognised errno falls back to ``default`` (session scope) so
    an unexpected failure never silently continues a batch.
    """
    if errno is not None and errno.strip() in TARGET_SCOPED_ERRNOS:
        return FailureScope.TARGET
    return default


def is_target_scoped_error(outcome: TargetOutcome, *, daemon_alive: bool = True) -> bool:
    """True when this outcome must not abort the rest of its batch.

    When ``daemon_alive`` is ``False``, no failure is target-scoped: ``sballd``
    itself is unreachable and the remaining batch must fast-abort. When
    ``daemon_alive`` is ``True``, both documented target-state rejections
    (``errno 146``) and per-target action timeouts (``PVM_COMMAND_TIMEOUT``) are
    isolated to the current target so subsequent targets proceed immediately.
    """
    if not daemon_alive or not outcome.dispatched:
        # Nothing reached a responsive PVM: a transport/policy/process/daemon
        # failure is never about one target's state.
        return False
    if outcome.code == COMMAND_TIMEOUT_CODE:
        return True
    return classify_failure(outcome.errno, default=FailureScope.SESSION) is FailureScope.TARGET


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

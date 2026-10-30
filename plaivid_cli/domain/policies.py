"""Pure operation risk and freshness policies."""

from __future__ import annotations

from plaivid_cli.domain.models import Action, ActionPolicy, RiskLevel

_POLICIES = {
    Action.START: ActionPolicy(Action.START, RiskLevel.MODERATE, False, True),
    Action.STOP: ActionPolicy(Action.STOP, RiskLevel.HIGH, True, True),
    Action.KILL: ActionPolicy(Action.KILL, RiskLevel.CRITICAL, True, True),
    Action.RESET: ActionPolicy(Action.RESET, RiskLevel.HIGH, True, True),
    Action.PAUSE: ActionPolicy(Action.PAUSE, RiskLevel.HIGH, True, True),
    Action.RESUME: ActionPolicy(Action.RESUME, RiskLevel.MODERATE, False, True),
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

from __future__ import annotations

from plaivid_cli.domain.models import Action
from plaivid_cli.domain.policies import action_policy, bulk_may_dispatch


def test_all_six_action_confirmation_policies_are_explicit() -> None:
    expected = {
        Action.START: (False, True, "moderate"),
        Action.STOP: (True, True, "high"),
        Action.KILL: (True, True, "critical"),
        Action.RESET: (True, True, "high"),
        Action.PAUSE: (True, True, "high"),
        Action.RESUME: (False, True, "moderate"),
    }
    for action, policy_values in expected.items():
        policy = action_policy(action)
        assert (policy.confirm_single, policy.confirm_bulk, policy.risk.value) == policy_values


def test_destructive_bulk_requires_set_age_and_complete_fresh_inventory() -> None:
    assert not bulk_may_dispatch(
        action=Action.STOP, is_bulk=True, complete=True, fresh=True, max_age_seconds=None
    )
    assert not bulk_may_dispatch(
        action=Action.KILL, is_bulk=True, complete=False, fresh=True, max_age_seconds=30
    )
    assert not bulk_may_dispatch(
        action=Action.RESET, is_bulk=True, complete=True, fresh=False, max_age_seconds=30
    )
    assert bulk_may_dispatch(
        action=Action.STOP, is_bulk=True, complete=True, fresh=True, max_age_seconds=30
    )


def test_non_destructive_bulk_still_requires_explicit_confirmation_policy() -> None:
    assert bulk_may_dispatch(
        action=Action.START, is_bulk=True, complete=True, fresh=True, max_age_seconds=30
    )

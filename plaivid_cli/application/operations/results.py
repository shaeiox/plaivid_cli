"""Aggregate per-target lifecycle outcomes without hiding uncertainty."""

from __future__ import annotations

from plaivid_cli.domain.models import OperationState, TargetOutcome


def aggregate_state(outcomes: tuple[TargetOutcome, ...]) -> OperationState:
    """Apply the documented precedence without hiding any uncertain target."""
    if not outcomes:
        return OperationState.FAILED
    states = {outcome.state for outcome in outcomes}
    if OperationState.OUTCOME_UNKNOWN in states:
        return OperationState.OUTCOME_UNKNOWN
    if OperationState.COMMAND_ACCEPTED_UNCONFIRMED in states:
        return OperationState.COMMAND_ACCEPTED_UNCONFIRMED
    succeeded = sum(outcome.state is OperationState.SUCCEEDED for outcome in outcomes)
    if succeeded == len(outcomes):
        return OperationState.SUCCEEDED
    if succeeded:
        return OperationState.PARTIAL
    if OperationState.FAILED in states:
        return OperationState.FAILED
    if states <= {OperationState.REJECTED, OperationState.NOT_STARTED}:
        return OperationState.REJECTED
    if states == {OperationState.CANCELLED_BEFORE_DISPATCH}:
        return OperationState.CANCELLED_BEFORE_DISPATCH
    if OperationState.NOT_STARTED in states:
        return OperationState.PARTIAL
    return OperationState.FAILED


def _aggregate_message(state: OperationState, outcomes: list[TargetOutcome]) -> str:
    counts: dict[OperationState, int] = {}
    for outcome in outcomes:
        counts[outcome.state] = counts.get(outcome.state, 0) + 1
    summary = ", ".join(f"{count} {key.value}" for key, count in counts.items())
    failure = next(
        (outcome.message for outcome in outcomes if outcome.state is OperationState.FAILED),
        None,
    )
    if failure:
        summary = f"{summary}; {failure}"
    if state is OperationState.OUTCOME_UNKNOWN:
        return f"{summary}; do not retry until reconciled"
    if state is OperationState.COMMAND_ACCEPTED_UNCONFIRMED:
        return f"{summary}; accepted commands are not proof of completion"
    return summary

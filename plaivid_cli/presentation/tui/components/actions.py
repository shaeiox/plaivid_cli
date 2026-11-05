"""Shared lifecycle action labels for inventory-page controls."""

from plaivid_cli.domain.models import Action

BULK_ACTIONS: tuple[Action, ...] = (
    Action.START,
    Action.RESUME,
    Action.PAUSE,
    Action.STOP,
    Action.RESET,
    Action.KILL,
)


def action_label(action: Action) -> str:
    """Return a consistent user-facing label for an action value."""
    return action.value.title()

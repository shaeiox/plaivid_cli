"""Reusable selection/search/action controls shared by VM and Desktop pages."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, Select

from .actions import BULK_ACTIONS, action_label


class InventoryToolbar(Horizontal):
    """Present a page-scoped action chooser and local inventory filters."""

    def __init__(
        self,
        *,
        id: str,
        action_id: str,
        selection_id: str,
        selection_label: str,
        audit_id: str,
        search_id: str,
        search_placeholder: str,
    ) -> None:
        super().__init__(id=id)
        self._action_id = action_id
        self._selection_id = selection_id
        self._selection_label = selection_label
        self._audit_id = audit_id
        self._search_id = search_id
        self._search_placeholder = search_placeholder

    def compose(self) -> ComposeResult:
        yield Select(
            [(action_label(action), action.value) for action in BULK_ACTIONS],
            prompt="Bulk action",
            allow_blank=True,
            id=self._action_id,
        )
        yield Checkbox(self._selection_label, id=self._selection_id)
        yield Button("Audit", id=self._audit_id)
        yield Input(placeholder=self._search_placeholder, id=self._search_id)

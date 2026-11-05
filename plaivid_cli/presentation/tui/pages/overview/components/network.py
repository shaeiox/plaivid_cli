"""Network interface summary, selector, and selected-interface details."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from rich.console import RenderableType
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import Palette
from plaivid_cli.presentation.tui.components import DashboardCard


class NetworkCard(DashboardCard):
    """Present discovered interfaces and sampled counters; performs no discovery itself."""

    def __init__(
        self,
        palette: Palette,
        *,
        on_rediscover: Callable[[], None],
        on_select_interface: Callable[[str], None],
    ) -> None:
        super().__init__(id="network-box", group="io", title="Network interfaces", palette=palette)
        self._on_rediscover = on_rediscover
        self._on_select_interface = on_select_interface
        self._nic_names: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static("Waiting for collection…", id="metrics-network", markup=False)
        with Horizontal(id="nic-tabs"):
            pass
        yield Static("Discovering physical interfaces…", id="nic-detail", markup=False)
        yield Button("Rediscover", id="rediscover")

    def set_metrics(self, value: str) -> None:
        self.query_one("#metrics-network", Static).update(value)

    def set_detail(self, value: RenderableType) -> None:
        self.query_one("#nic-detail", Static).update(value)

    @on(Button.Pressed, "#rediscover")
    def rediscover(self) -> None:
        self._on_rediscover()

    @on(Button.Pressed, ".nic-tab")
    def interface_selected(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        try:
            index = int(button_id.rsplit("-", 1)[1])
            name = self._nic_names[index]
        except (ValueError, IndexError):
            return
        self.select_interface(name)
        self._on_select_interface(name)

    def set_interfaces(self, names: Sequence[str], selected: str | None) -> None:
        """Reconcile visible interface tabs while preserving stable event IDs."""
        tabs = self.query_one("#nic-tabs", Horizontal)
        current = tuple(button.label.plain for button in tabs.query(Button))
        self._nic_names = tuple(names)
        safe_names = tuple(redact_text(name) for name in names)
        if current != safe_names:
            tabs.remove_children()
            for index, name in enumerate(safe_names):
                tabs.mount(Button(name, id=f"nic-tab-{index}", classes="nic-tab"))
        self.select_interface(selected)

    def select_interface(self, selected: str | None) -> None:
        """Mark the active tab without changing any inventory or collection state."""
        for button in self.query_one("#nic-tabs", Horizontal).query(Button):
            button.variant = (
                "primary" if button.label.plain == redact_text(selected or "") else "default"
            )

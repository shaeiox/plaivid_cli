"""Compatibility exports for shared widgets and page-level presentation helpers."""

from plaivid_cli.presentation.tui.components import BULK_ACTIONS, CheckableTable
from plaivid_cli.presentation.tui.components.actions import action_label as _action_label
from plaivid_cli.presentation.tui.components.formatting import display as _display
from plaivid_cli.presentation.tui.components.status import section_status as _section_status
from plaivid_cli.presentation.tui.pages.overview.components.host_status import (
    _host_banner_text,
    _host_status_text,
    _quorum_verdict,
)
from plaivid_cli.presentation.tui.pages.overview.components.panels import (
    METRIC_PANEL_IDS as _METRIC_PANELS,
)
from plaivid_cli.presentation.tui.pages.virtual_desktops.policy import (
    MIN_REFRESH_SECONDS as DESKTOP_MIN_REFRESH_SECONDS,
)

__all__ = [
    "BULK_ACTIONS",
    "CheckableTable",
    "DESKTOP_MIN_REFRESH_SECONDS",
    "_METRIC_PANELS",
    "_action_label",
    "_display",
    "_host_banner_text",
    "_host_status_text",
    "_quorum_verdict",
    "_section_status",
]

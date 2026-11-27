"""Page-specific summary, inventory, and detail components for virtual desktops."""

from .details import DesktopAuditPanel, DesktopDetailPanel
from .inventory import DesktopInventoryPanel
from .summary import DesktopSummary

__all__ = [
    "DesktopAuditPanel",
    "DesktopDetailPanel",
    "DesktopInventoryPanel",
    "DesktopSummary",
]

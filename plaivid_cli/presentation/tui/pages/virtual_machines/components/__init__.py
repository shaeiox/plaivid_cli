"""Page-specific summary, inventory, and detail components for virtual machines."""

from .details import VMAuditPanel, VMDetailPanel
from .inventory import VMInventoryPanel
from .summary import VMSummary

__all__ = ["VMAuditPanel", "VMDetailPanel", "VMInventoryPanel", "VMSummary"]

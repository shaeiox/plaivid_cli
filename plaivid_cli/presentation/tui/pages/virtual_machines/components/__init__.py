"""Page-specific summary, inventory, and detail components for virtual machines."""

from .details import (
    DetailPlaceholder,
    VMAuditPanel,
    VMDetailPanel,
    build_detail_placeholder,
    build_vm_detail,
)
from .inventory import VMInventoryPanel
from .summary import VMSummary

__all__ = [
    "DetailPlaceholder",
    "VMAuditPanel",
    "VMDetailPanel",
    "VMInventoryPanel",
    "VMSummary",
    "build_detail_placeholder",
    "build_vm_detail",
]

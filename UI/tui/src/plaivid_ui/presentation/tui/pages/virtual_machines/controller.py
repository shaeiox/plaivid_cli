"""VM page controller composed from selection and lifecycle-action responsibilities."""

from .operations import VMOperationMixin
from .selection import VMSelectionMixin


class VirtualMachinesMixin(VMSelectionMixin, VMOperationMixin):
    """Compatibility behavior mixin used by the top-level TUI composition root."""

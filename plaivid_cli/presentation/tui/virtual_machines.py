"""VM page behavior composed from selection and lifecycle-operation concerns."""

from .vm_operations import VMOperationMixin
from .vm_selection import VMSelectionMixin


class VirtualMachinesMixin(VMSelectionMixin, VMOperationMixin):
    """Combined VM page API retained for the main TUI composition root."""

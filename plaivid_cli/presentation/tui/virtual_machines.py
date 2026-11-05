"""Compatibility facade for the page-oriented Virtual Machine controller."""

from .pages.virtual_machines.controller import VirtualMachinesMixin
from .pages.virtual_machines.operations import VMOperationMixin
from .pages.virtual_machines.selection import VMSelectionMixin

__all__ = ["VMOperationMixin", "VMSelectionMixin", "VirtualMachinesMixin"]

"""PVM gateway adapter and its documented local command request shapes."""

from .local import LocalPvmAdapter
from .requests import (
    DASHBOARD_QUERY,
    DESKTOP_QUERY,
    ERRNO_HINT,
    SBALLD_STATUS_ARGV,
    VM_QUERY,
)

__all__ = [
    "DASHBOARD_QUERY",
    "DESKTOP_QUERY",
    "ERRNO_HINT",
    "LocalPvmAdapter",
    "SBALLD_STATUS_ARGV",
    "VM_QUERY",
]

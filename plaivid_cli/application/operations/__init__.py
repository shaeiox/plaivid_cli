"""Lifecycle planning, dispatch coordination, task admission, and result aggregation."""

from .coordinator import OperationCoordinator
from .results import aggregate_state
from .task_registry import Admission, TaskManager

__all__ = ["Admission", "OperationCoordinator", "TaskManager", "aggregate_state"]

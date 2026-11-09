"""Immutable domain values, re-exported for a stable import surface."""

from .audit import AuditEntry, AuditSummary
from .enums import Action, CollectionStatus, ErrorKind, OperationState, RiskLevel, canonical_uuid
from .host import (
    ConsoleInfo,
    DiskInfo,
    HostMetrics,
    HostStatus,
    NetworkInterface,
    NicInfo,
    ProcessSample,
    StoragePartition,
    TemperatureReading,
    UserSession,
    VMDetail,
)
from .inventory import (
    InventoryData,
    ObjectVM,
    ProcessObservation,
    VMRecord,
    resolve_console_port,
)
from .operations import (
    ActionPolicy,
    OperationPlan,
    OperationResult,
    PvmReply,
    TargetOutcome,
)
from .session import PvmSession
from .snapshots import ApplicationSnapshot, SectionSnapshot, SourceResult
from .tasks import (
    TargetRef,
    TaskEvent,
    TaskKey,
    TaskRecord,
    TaskStatus,
    task_status_for,
)

__all__ = [
    "Action",
    "ActionPolicy",
    "ApplicationSnapshot",
    "AuditEntry",
    "AuditSummary",
    "CollectionStatus",
    "ConsoleInfo",
    "DiskInfo",
    "ErrorKind",
    "HostMetrics",
    "HostStatus",
    "InventoryData",
    "NetworkInterface",
    "NicInfo",
    "ObjectVM",
    "OperationPlan",
    "OperationResult",
    "OperationState",
    "PvmReply",
    "PvmSession",
    "ProcessObservation",
    "ProcessSample",
    "RiskLevel",
    "SectionSnapshot",
    "SourceResult",
    "StoragePartition",
    "TargetOutcome",
    "TargetRef",
    "TaskEvent",
    "TaskKey",
    "TaskRecord",
    "TaskStatus",
    "TemperatureReading",
    "UserSession",
    "VMDetail",
    "VMRecord",
    "canonical_uuid",
    "resolve_console_port",
    "task_status_for",
]

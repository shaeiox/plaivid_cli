"""Immutable domain values shared by application, CLI, and TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID


class CollectionStatus(StrEnum):
    NEVER = "never_collected"
    CURRENT = "current"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class Action(StrEnum):
    START = "start"
    STOP = "stop"
    KILL = "kill"
    RESET = "reset"
    PAUSE = "pause"
    RESUME = "resume"


class RiskLevel(StrEnum):
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class OperationState(StrEnum):
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    CANCELLED_BEFORE_DISPATCH = "CANCELLED_BEFORE_DISPATCH"
    NOT_STARTED = "NOT_STARTED"
    COMMAND_ACCEPTED_UNCONFIRMED = "COMMAND_ACCEPTED_UNCONFIRMED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class ErrorKind(StrEnum):
    CONFIGURATION = "configuration"
    PROCESS = "process"
    PROTOCOL = "protocol"
    PVM_RESPONSE = "pvm_response"
    AUTHENTICATION = "authentication"
    COLLECTION = "collection"
    POLICY = "policy"
    AUDIT = "audit"
    INTERNAL = "internal"


def canonical_uuid(value: str) -> str:
    """Normalize a UUID to lowercase hyphenated form or reject it."""
    try:
        return str(UUID(value.strip())).lower()
    except (AttributeError, ValueError, TypeError) as exc:
        raise ValueError("invalid UUID") from exc


@dataclass(frozen=True, slots=True)
class ObjectVM:
    uuid: str
    name: str
    state: str = "unknown"
    vcpu: int | None = None
    mem_mb: int | None = None
    description: str = ""
    configured_port: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))
        object.__setattr__(self, "name", self.name.strip() or self.uuid)
        object.__setattr__(self, "state", self.state.strip().lower() or "unknown")
        if self.vcpu is not None and self.vcpu < 0:
            raise ValueError("vcpu cannot be negative")
        if self.mem_mb is not None and self.mem_mb < 0:
            raise ValueError("mem_mb cannot be negative")


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    uuid: str
    pid: int | None = None
    uptime: str | None = None
    port: int | None = None
    vcpu: int | None = None
    mem_mb: int | None = None
    name: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))
        if self.pid is not None and self.pid <= 0:
            raise ValueError("pid must be positive")


@dataclass(frozen=True, slots=True)
class VMRecord:
    object: ObjectVM
    process: ProcessObservation | None = None
    state_disagreed: bool = False
    quality_issues: tuple[str, ...] = ()

    @property
    def uuid(self) -> str:
        return self.object.uuid

    @property
    def name(self) -> str:
        return self.object.name

    @property
    def state(self) -> str:
        return self.object.state

    @property
    def process_seen(self) -> bool:
        return self.process is not None

    @property
    def vcpu(self) -> int | None:
        return self.object.vcpu

    @property
    def mem_mb(self) -> int | None:
        return self.object.mem_mb


@dataclass(frozen=True, slots=True)
class InventoryData:
    objects: tuple[ObjectVM, ...] = ()
    process_rows: tuple[ProcessObservation, ...] = ()
    records: tuple[VMRecord, ...] = ()
    unmatched_process_rows: tuple[ProcessObservation, ...] = ()
    quality_issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HostStatus:
    name: str | None = None
    ip: str | None = None
    sball_state: str | None = None
    node_state: str | None = None
    version: str | None = None
    host_time: str | None = None
    cpu_pct: float | None = None
    cpu_count: int | None = None
    ram_used_bytes: int | None = None
    ram_total_bytes: int | None = None
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None
    storage_total_bytes: int | None = None
    storage_available_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class NetworkInterface:
    name: str
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    kind: str | None = None
    state: str | None = None


@dataclass(frozen=True, slots=True)
class StoragePartition:
    mountpoint: str
    filesystem: str
    total_bytes: int
    used_bytes: int | None = None
    used_percent: float | None = None
    category: str = "Other"


@dataclass(frozen=True, slots=True)
class DiskInfo:
    name: str
    media: str | None = None
    controller: str | None = None
    boot_index: str | None = None
    cache: str | None = None


@dataclass(frozen=True, slots=True)
class NicInfo:
    name: str
    device: str | None = None
    mac: str | None = None
    tap_name: str | None = None
    enabled: str | None = None


@dataclass(frozen=True, slots=True)
class ConsoleInfo:
    kind: str | None = None
    port: int | None = None
    bind_address: str | None = None
    password_enabled: str | None = None
    tls: str | None = None


@dataclass(frozen=True, slots=True)
class VMDetail:
    uuid: str
    name: str
    state: str
    host: str | None = None
    description: str = ""
    enabled: str | None = None
    ha: str | None = None
    created: str | None = None
    modified: str | None = None
    auto_start: str | None = None
    always_on: str | None = None
    qemu_version: str | None = None
    vcpu: int | None = None
    vcpu_topology: str | None = None
    cpu_model: str | None = None
    memory_mb: int | None = None
    machine: str | None = None
    uefi: str | None = None
    disks: tuple[DiskInfo, ...] = ()
    nics: tuple[NicInfo, ...] = ()
    console: ConsoleInfo | None = None
    pid: int | None = None
    uptime: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))


@dataclass(frozen=True, slots=True)
class HostMetrics:
    cpu_pct: float | None = None
    logical_cores: int | None = None
    physical_cores: int | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    swap_used_bytes: int | None = None
    swap_total_bytes: int | None = None
    hostname: str | None = None
    uptime: str | None = None
    os_version: str | None = None
    interfaces: tuple[NetworkInterface, ...] = ()
    storage: tuple[StoragePartition, ...] = ()


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SourceResult(Generic[T]):  # noqa: UP046 — local verifier is Python 3.11
    value: T | None
    status: CollectionStatus
    source: str
    attempted_at: datetime | None = None
    succeeded_at: datetime | None = None
    error: str | None = None
    quality_issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionSnapshot(Generic[T]):  # noqa: UP046 — keep local Python 3.11 verification possible
    name: str
    value: T | None
    last_good_value: T | None
    status: CollectionStatus
    attempted_at: datetime | None
    succeeded_at: datetime | None
    generation: int
    source: str | None = None
    error: str | None = None
    quality_issues: tuple[str, ...] = field(default_factory=tuple)
    attempted_monotonic: float | None = None
    succeeded_monotonic: float | None = None

    @property
    def has_value(self) -> bool:
        return self.value is not None or self.last_good_value is not None


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    generation: int
    created_at: datetime
    sections: tuple[SectionSnapshot[object], ...] = ()

    def section(self, name: str) -> SectionSnapshot[object] | None:
        return next((item for item in self.sections if item.name == name), None)


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    action: Action
    risk: RiskLevel
    confirm_single: bool
    confirm_bulk: bool = True


@dataclass(frozen=True, slots=True)
class AuditEntry:
    time: str
    user: str
    user_ip: str
    product: str
    command: str
    result: str
    succeeded: bool


@dataclass(frozen=True, slots=True)
class AuditSummary:
    total: int
    failures: int
    top_commands: tuple[tuple[str, int], ...]
    top_users: tuple[tuple[str, int], ...]
    span: tuple[str | None, str | None]


@dataclass(frozen=True, slots=True)
class PvmSession:
    username: str
    token: str = field(repr=False)
    authenticated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PvmReply:
    status: str
    action_id: str | None = None
    errno: str | None = None
    message: str | None = None
    returncode: int = 0


@dataclass(frozen=True, slots=True)
class OperationPlan:
    action: Action
    target_uuids: tuple[str, ...]
    inventory_generation: int
    inventory_succeeded_at: datetime
    is_bulk: bool
    freshness_limit_seconds: float
    created_at: datetime
    confirmation: str


@dataclass(frozen=True, slots=True)
class OperationApproval:
    action: Action
    target_uuids: tuple[str, ...]
    inventory_generation: int
    issued_at: datetime
    confirmation: str


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    uuid: str
    state: OperationState
    message: str = ""
    dispatched: bool = False


@dataclass(frozen=True, slots=True)
class OperationResult:
    operation_id: str
    action: Action
    state: OperationState
    targets: tuple[TargetOutcome, ...]
    started_at: datetime
    finished_at: datetime | None = None
    message: str = ""

    @property
    def succeeded_count(self) -> int:
        return sum(target.state is OperationState.SUCCEEDED for target in self.targets)

    @property
    def unknown_count(self) -> int:
        return sum(target.state is OperationState.OUTCOME_UNKNOWN for target in self.targets)

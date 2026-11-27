"""UI-owned wire DTOs for ``plaivid.engine.v1``; never import Engine types here."""

from __future__ import annotations

import time
import uuid as uuidlib
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar, get_args, get_origin, get_type_hints

T = TypeVar("T")


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


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_terminal(self) -> bool:
        return self not in {TaskStatus.QUEUED, TaskStatus.RUNNING}


def task_status_for(state: OperationState) -> TaskStatus:
    return {
        OperationState.QUEUED: TaskStatus.QUEUED,
        OperationState.DISPATCHING: TaskStatus.RUNNING,
        OperationState.RUNNING: TaskStatus.RUNNING,
        OperationState.SUCCEEDED: TaskStatus.SUCCEEDED,
        OperationState.COMMAND_ACCEPTED_UNCONFIRMED: TaskStatus.SUCCEEDED,
        OperationState.FAILED: TaskStatus.FAILED,
        OperationState.REJECTED: TaskStatus.REJECTED,
        OperationState.CANCELLED_BEFORE_DISPATCH: TaskStatus.REJECTED,
        OperationState.NOT_STARTED: TaskStatus.SKIPPED,
        OperationState.OUTCOME_UNKNOWN: TaskStatus.UNKNOWN,
        OperationState.PARTIAL: TaskStatus.UNKNOWN,
    }[state]


@dataclass(frozen=True, slots=True)
class SectionDTO:
    status: str
    value: Any = None
    error: str | None = None
    age_seconds: float | None = None
    generation: int | None = None
    attempted_at: datetime | None = None
    succeeded_at: datetime | None = None
    latency_seconds: float | None = None
    source: str | None = None
    quality_issues: tuple[str, ...] = ()

    @classmethod
    def from_wire(cls, value: object) -> SectionDTO | None:
        if value is None:
            return None
        if not isinstance(value, dict) or not isinstance(value.get("status"), str):
            raise ValueError("invalid section DTO")
        return cls(
            status=value["status"],
            value=value.get("value"),
            error=value.get("error") if isinstance(value.get("error"), str) else None,
            age_seconds=_number_or_none(value.get("age_seconds")),
            generation=_int_or_none(value.get("generation")),
            attempted_at=_datetime_or_none(value.get("attempted_at")),
            succeeded_at=_datetime_or_none(value.get("succeeded_at")),
            latency_seconds=_number_or_none(value.get("latency_seconds")),
            source=value.get("source") if isinstance(value.get("source"), str) else None,
            quality_issues=tuple(item for item in value.get("quality_issues", []) if isinstance(item, str)),
        )


@dataclass(frozen=True, slots=True)
class SnapshotDTO:
    generation: int
    sections: dict[str, SectionDTO]

    @classmethod
    def from_wire(cls, value: object) -> SnapshotDTO:
        if not isinstance(value, dict) or not isinstance(value.get("sections"), dict):
            raise ValueError("invalid snapshot DTO")
        generation = _int_or_none(value.get("generation"))
        if generation is None:
            raise ValueError("invalid snapshot generation")
        sections: dict[str, SectionDTO] = {}
        for name, raw in value["sections"].items():
            if not isinstance(name, str):
                raise ValueError("invalid section name")
            dto = SectionDTO.from_wire(raw)
            if dto is not None:
                sections[name] = dto
        return cls(generation, sections)

    def section(self, name: str) -> SectionDTO | None:
        return self.sections.get(name)


# The remaining records describe data received from RPC or UI task-board state.
@dataclass(frozen=True, slots=True)
class ObjectVM:
    uuid: str
    name: str
    state: str = "unknown"
    vcpu: int | None = None
    mem_mb: int | None = None
    description: str = ""
    configured_port: int | None = None
    host: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    uuid: str
    pid: int | None = None
    uptime: str | None = None
    port: int | None = None
    vcpu: int | None = None
    mem_mb: int | None = None
    name: str = ""
    row_number: int | None = None


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

    @property
    def host(self) -> str | None:
        return self.object.host


@dataclass(frozen=True, slots=True)
class InventoryData:
    objects: tuple[ObjectVM, ...] = ()
    process_rows: tuple[ProcessObservation, ...] = ()
    records: tuple[VMRecord, ...] = ()
    unmatched_process_rows: tuple[ProcessObservation, ...] = ()
    quality_issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionSnapshot(Generic[T]):
    name: str
    value: T | None
    last_good_value: T | None
    status: CollectionStatus
    attempted_at: datetime | None
    succeeded_at: datetime | None
    generation: int
    source: str | None = None
    error: str | None = None
    quality_issues: tuple[str, ...] = ()
    attempted_monotonic: float | None = None
    succeeded_monotonic: float | None = None
    latency_seconds: float | None = None

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
class VirtualDesktop:
    uuid: str
    name: str
    enabled: str | None = None
    local_status: str | None = None
    cluster_status: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    vcpu: int | None = None
    memory_size_raw: str | None = None
    parent_id: str | None = None


@dataclass(frozen=True, slots=True)
class HostStatus:
    name: str | None = None
    ip: str | None = None
    node_id: str | None = None
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
class TemperatureReading:
    sensor: str
    celsius: float


@dataclass(frozen=True, slots=True)
class UserSessionDTO:
    user: str
    terminal: str | None = None
    host: str | None = None
    started: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessSample:
    pid: int
    ppid: int | None = None
    username: str | None = None
    cpu_pct: float | None = None
    memory_pct: float | None = None
    threads: int | None = None
    state: str | None = None
    command: str | None = None
    exe: str | None = None
    started: str | None = None
    uptime: str | None = None


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
    host_id: str | None = None
    platform_family: str | None = None
    kernel_version: str | None = None
    virtualization: str | None = None
    boot_time: str | None = None
    uptime_seconds: int | None = None
    cpu_count: int | None = None
    cpu_model: str | None = None
    cpu_current_hz: float | None = None
    run_queue: int | None = None
    blocked_tasks: int | None = None
    blocked_percent: float | None = None
    total_tasks: int | None = None
    num_processes: int | None = None
    num_threads: int | None = None
    open_fds: int | None = None
    context_switches: int | None = None
    interrupts: int | None = None
    forks: int | None = None
    temperatures: tuple[TemperatureReading, ...] = ()
    users: tuple[UserSessionDTO, ...] = ()
    processes: tuple[ProcessSample, ...] = ()
    process_total: int | None = None
    command_summary: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class LocalHostSample:
    hostname: str | None = None
    cpu_percent: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None
    uptime_seconds: float | None = None
    pvm_uptime_seconds: float | None = None
    sballd_pid_file: bool | None = None


@dataclass(frozen=True, slots=True)
class DashboardSample:
    host_name: str | None = None
    host_id: str | None = None
    cpu_info: tuple[str, ...] = ()
    ram_free_raw: str | None = None
    ram_used_raw: str | None = None
    ram_total_raw: str | None = None
    vm_cpu: tuple[tuple[str, str], ...] = ()
    vm_ram: tuple[tuple[str, str], ...] = ()
    vm_network: tuple[tuple[str, str], ...] = ()
    vdis: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PhysicalNic:
    name: str
    identifier: str | None = None
    mac: str | None = None
    ip: str | None = None
    gateway: str | None = None
    management: str | None = None
    redundancy: str | None = None


@dataclass(frozen=True, slots=True)
class NicSample:
    name: str
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_packets: int | None = None
    tx_packets: int | None = None
    rx_errors: int | None = None
    tx_errors: int | None = None
    rx_dropped: int | None = None
    tx_dropped: int | None = None
    rx_crc_errors: int | None = None
    state: str | None = None
    rx_bytes_per_second: float | None = None
    tx_bytes_per_second: float | None = None


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
class TargetOutcome:
    uuid: str
    state: OperationState
    message: str = ""
    dispatched: bool = False
    errno: str | None = None
    code: str | None = None


@dataclass(frozen=True, slots=True)
class OperationResult:
    operation_id: str
    action: Action
    state: OperationState
    targets: tuple[TargetOutcome, ...]
    started_at: datetime
    finished_at: datetime | None = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class TargetRef:
    uuid: str
    label: str = ""
    kind: str = "vm"

    @property
    def short(self) -> str:
        return self.uuid[:8]


@dataclass(frozen=True, slots=True)
class TaskKey:
    action: Action
    target_uuid: str


@dataclass(slots=True)
class TaskRecord:
    key: TaskKey
    target: TargetRef
    operation_id: str
    task_id: str = field(default_factory=lambda: str(uuidlib.uuid4()))
    status: TaskStatus = TaskStatus.QUEUED
    message: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    def elapsed_seconds(self, *, now: datetime | None = None) -> float:
        if self.started_at is None:
            return 0.0
        return max(0.0, ((self.finished_at or now or datetime.now(UTC)) - self.started_at).total_seconds())

    def copy(self, **changes: object) -> TaskRecord:
        values = {
            "key": self.key,
            "target": self.target,
            "operation_id": self.operation_id,
            "task_id": self.task_id,
            "status": self.status,
            "message": self.message,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        values.update(changes)
        return TaskRecord(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class TaskEvent:
    kind: str
    record: TaskRecord | None = None
    operation_id: str = ""
    action: Action | None = None
    targets: tuple[TargetRef, ...] = ()
    reason: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class EngineConnection:
    username: str = "Engine session"


@dataclass(frozen=True, slots=True)
class TargetSelection:
    records: tuple[VMRecord, ...]
    is_bulk: bool


def decode_dataclass(cls: type[T], raw: object) -> T:
    """Decode a JSON object into a UI-owned DTO; reject malformed container shapes."""
    if not isinstance(raw, dict):
        raise ValueError(f"expected {cls.__name__} object")
    return _decode(cls, raw)


def _decode(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if value is None:
        return None
    if origin is tuple:
        subtype = args[0] if args else Any
        if not isinstance(value, (list, tuple)):
            raise ValueError("expected array in Engine response")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(subtype, item) for item in value)
        return tuple(_decode(t, item) for t, item in zip(args, value, strict=False))
    if origin in (list, set, frozenset):
        subtype = args[0] if args else Any
        if not isinstance(value, (list, tuple)):
            raise ValueError("expected array in Engine response")
        return origin(_decode(subtype, item) for item in value)
    if origin is not None and type(None) in args:
        for subtype in args:
            if subtype is not type(None):
                return _decode(subtype, value)
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    if annotation is datetime:
        if not isinstance(value, str):
            raise ValueError("expected timestamp in Engine response")
        return datetime.fromisoformat(value)
    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, dict):
            raise ValueError("expected object in Engine response")
        hints = get_type_hints(annotation)
        return annotation(**{
            field.name: _decode(hints.get(field.name, Any), value[field.name])
            for field in fields(annotation)
            if field.name in value
        })
    if annotation is Any:
        return value
    return value


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _datetime_or_none(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def as_inventory(section: SectionSnapshot | None) -> InventoryData | None:
    if section is None:
        return None
    value = section.value if section.value is not None else section.last_good_value
    if value is None:
        return None
    return value if isinstance(value, InventoryData) else decode_dataclass(InventoryData, value)


def as_vm_detail(section: SectionSnapshot | None) -> VMDetail:
    if section is None:
        raise ValueError("detail section is missing")
    value = section.value if section.value is not None else section.last_good_value
    if isinstance(value, VMDetail):
        return value
    return decode_dataclass(VMDetail, value)


def as_host_metrics(section: SectionSnapshot | None) -> HostMetrics | None:
    if section is None:
        return None
    value = section.value if section.value is not None else section.last_good_value
    if value is None:
        return None
    return value if isinstance(value, HostMetrics) else decode_dataclass(HostMetrics, value)


def as_host_status(section: SectionSnapshot | None) -> HostStatus | None:
    if section is None:
        return None
    value = section.value if section.value is not None else section.last_good_value
    if value is None:
        return None
    return value if isinstance(value, HostStatus) else decode_dataclass(HostStatus, value)


def as_snapshot(raw: object) -> ApplicationSnapshot:
    dto = SnapshotDTO.from_wire(raw)
    sections: list[SectionSnapshot] = []
    value_types: dict[str, type[Any]] = {
        "inventory": InventoryData,
        "desktops": tuple[VirtualDesktop, ...],
        "host_status": HostStatus,
        "host_metrics": HostMetrics,
        "local_host": LocalHostSample,
        "physical_nics": tuple[PhysicalNic, ...],
        "nic_samples": tuple[NicSample, ...],
        "dashboard": DashboardSample,
    }
    for name, item in dto.sections.items():
        value = item.value
        expected = value_types.get(name)
        if value is not None and expected is not None:
            value = _decode(expected, value)
        received = time.monotonic()
        succeeded_mono = (
            max(0.0, received - item.age_seconds)
            if item.age_seconds is not None
            else received if item.succeeded_at is not None else None
        )
        sections.append(SectionSnapshot(
            name=name,
            value=value,
            last_good_value=value,
            status=CollectionStatus(item.status),
            attempted_at=item.attempted_at,
            succeeded_at=item.succeeded_at,
            generation=item.generation or dto.generation,
            source=item.source,
            error=item.error,
            quality_issues=item.quality_issues,
            attempted_monotonic=received,
            succeeded_monotonic=succeeded_mono,
            latency_seconds=item.latency_seconds,
        ))
    return ApplicationSnapshot(dto.generation, datetime.now().astimezone(), tuple(sections))


def as_operation_result(raw: object) -> OperationResult:
    return decode_dataclass(OperationResult, raw)


def as_desktops(raw: object) -> tuple[VirtualDesktop, ...]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("invalid desktop list")
    return tuple(_decode(VirtualDesktop, item) for item in raw)


def as_audit_entries(raw: object) -> tuple[AuditEntry, ...]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("invalid audit result")
    return tuple(_decode(AuditEntry, item) for item in raw)

"""PVM object records and correlated local process observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .enums import canonical_uuid

if TYPE_CHECKING:  # pragma: no cover - annotation only, never imported at runtime
    from .host import VMDetail


@dataclass(frozen=True, slots=True)
class ObjectVM:
    uuid: str
    name: str
    state: str = "unknown"
    vcpu: int | None = None
    mem_mb: int | None = None
    description: str = ""
    configured_port: int | None = None
    # Node the VM runs/belongs on (`virtual_machine/cluster/host`), kept verbatim.
    host: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))
        object.__setattr__(self, "name", self.name.strip() or self.uuid)
        object.__setattr__(self, "state", self.state.strip().lower() or "unknown")
        object.__setattr__(self, "host", (self.host or "").strip() or None)
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
    row_number: int | None = None  # Number printed by pvm-running-vms, not VM inventory index.

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

    @property
    def host(self) -> str | None:
        return self.object.host


def resolve_console_port(record: VMRecord, detail: VMDetail | None = None) -> int | None:
    """Resolve the console port from the strongest available evidence.

    Precedence: live local process observation (`pvm-running-vms`), then the port
    configured on the object record, then the asynchronous detail read, then
    unknown (``None``). A configured port is never reported as a live one: the
    first source that provides a value wins and nothing is derived.
    """
    if record.process is not None and record.process.port is not None:
        return record.process.port
    if record.object.configured_port is not None:
        return record.object.configured_port
    if detail is not None and detail.console is not None:
        return detail.console.port
    return None


@dataclass(frozen=True, slots=True)
class InventoryData:
    objects: tuple[ObjectVM, ...] = ()
    process_rows: tuple[ProcessObservation, ...] = ()
    records: tuple[VMRecord, ...] = ()
    unmatched_process_rows: tuple[ProcessObservation, ...] = ()
    quality_issues: tuple[str, ...] = ()

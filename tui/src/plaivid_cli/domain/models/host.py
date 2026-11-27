"""Host telemetry and VM-detail domain values."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import canonical_uuid


@dataclass(frozen=True, slots=True)
class HostStatus:
    name: str | None = None
    ip: str | None = None
    # Cluster node number from `sball/show` (`node/id`), kept as text.
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
class UserSession:
    user: str
    terminal: str | None = None
    host: str | None = None
    started: str | None = None


@dataclass(frozen=True, slots=True)
class TemperatureReading:
    sensor: str
    celsius: float


@dataclass(frozen=True, slots=True)
class ProcessSample:
    # ``full_command`` is intentionally not modelled: it can carry sbell argv, including tokens.
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
    # system_info identity and kernel facts
    host_id: str | None = None
    platform_family: str | None = None
    kernel_version: str | None = None
    virtualization: str | None = None
    boot_time: str | None = None
    uptime_seconds: int | None = None
    # load_stats
    cpu_count: int | None = None
    # cpu_info/cpu_detail (first core): model name and current clock in Hz
    cpu_model: str | None = None
    cpu_current_hz: float | None = None
    run_queue: int | None = None
    blocked_tasks: int | None = None
    blocked_percent: float | None = None
    total_tasks: int | None = None
    # process_stats / system_stats
    num_processes: int | None = None
    num_threads: int | None = None
    open_fds: int | None = None
    context_switches: int | None = None
    interrupts: int | None = None
    forks: int | None = None
    # lists
    temperatures: tuple[TemperatureReading, ...] = ()
    users: tuple[UserSession, ...] = ()
    processes: tuple[ProcessSample, ...] = ()
    process_total: int | None = None
    # (command name, count) over every process, most common first; not limited to the top rows.
    command_summary: tuple[tuple[str, int], ...] = ()


def describe_host(
    node: str | None,
    local_hostname: str | None = None,
    local_node_id: str | None = None,
    *,
    local_node_name: str | None = None,
) -> str:
    """Format a VM's node as ``<node> (<hostname>)`` when that node is this host.

    The hostname is appended only when ``node`` is proven to identify the local
    node (by node number, node name, or the hostname itself). A remote or
    unknown node is returned verbatim: the local hostname is never borrowed for
    a node the caller cannot prove is this machine. ``None``/blank render ``—``,
    and PVM's ``auto`` placement marker is passed through untouched.
    """
    raw = (node or "").strip()
    if not raw or raw == "—":
        return "—"
    if raw.casefold() == "auto":
        return raw

    hostname = (local_hostname or "").strip() or None
    identifiers = (local_node_id, local_node_name, hostname)
    matched = any(
        value is not None and raw.casefold() == value.strip().casefold()
        for value in identifiers
    )
    if not matched or hostname is None:
        return raw
    if raw.casefold() == hostname.casefold():
        return hostname
    return f"{raw} ({hostname})"

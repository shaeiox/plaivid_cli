# Human-readable documentation for `host.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/models/host.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Host telemetry and VM-detail domain values.

## 2. Functional summary

Host telemetry and VM-detail domain values.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `describe_host(node: str | None, local_hostname: str | None=None, local_node_id: str | None=None, *, local_node_name: str | None=None) -> str`

Format a VM's node as ``<node> (<hostname>)`` when that node is this host. The hostname is appended only when ``node`` is proven to identify the local node (by node number, node name, or the hostname itself). A remote or unknown node is returned verbatim: the local hostname is never borrowed for a node the caller cannot prove is this machine. ``None``/blank render ``—``, and PVM's ``auto`` placement marker is passed through untouched.

### `VMDetail.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

## 6. Classes and data structures

### `HostStatus`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str | None` (default: `None`)
  - `ip: str | None` (default: `None`)
  - `node_id: str | None` (default: `None`)
  - `sball_state: str | None` (default: `None`)
  - `node_state: str | None` (default: `None`)
  - `version: str | None` (default: `None`)
  - `host_time: str | None` (default: `None`)
  - `cpu_pct: float | None` (default: `None`)
  - `cpu_count: int | None` (default: `None`)
  - `ram_used_bytes: int | None` (default: `None`)
  - `ram_total_bytes: int | None` (default: `None`)
  - `load1: float | None` (default: `None`)
  - `load5: float | None` (default: `None`)
  - `load15: float | None` (default: `None`)
  - `storage_total_bytes: int | None` (default: `None`)
  - `storage_available_bytes: int | None` (default: `None`)

### `NetworkInterface`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str`
  - `rx_bytes: int | None` (default: `None`)
  - `tx_bytes: int | None` (default: `None`)
  - `kind: str | None` (default: `None`)
  - `state: str | None` (default: `None`)

### `StoragePartition`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `mountpoint: str`
  - `filesystem: str`
  - `total_bytes: int`
  - `used_bytes: int | None` (default: `None`)
  - `used_percent: float | None` (default: `None`)
  - `category: str` (default: `'Other'`)

### `DiskInfo`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str`
  - `media: str | None` (default: `None`)
  - `controller: str | None` (default: `None`)
  - `boot_index: str | None` (default: `None`)
  - `cache: str | None` (default: `None`)

### `NicInfo`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str`
  - `device: str | None` (default: `None`)
  - `mac: str | None` (default: `None`)
  - `tap_name: str | None` (default: `None`)
  - `enabled: str | None` (default: `None`)

### `ConsoleInfo`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `kind: str | None` (default: `None`)
  - `port: int | None` (default: `None`)
  - `bind_address: str | None` (default: `None`)
  - `password_enabled: str | None` (default: `None`)
  - `tls: str | None` (default: `None`)

### `VMDetail`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `uuid: str`
  - `name: str`
  - `state: str`
  - `host: str | None` (default: `None`)
  - `description: str` (default: `''`)
  - `enabled: str | None` (default: `None`)
  - `ha: str | None` (default: `None`)
  - `created: str | None` (default: `None`)
  - `modified: str | None` (default: `None`)
  - `auto_start: str | None` (default: `None`)
  - `always_on: str | None` (default: `None`)
  - `qemu_version: str | None` (default: `None`)
  - `vcpu: int | None` (default: `None`)
  - `vcpu_topology: str | None` (default: `None`)
  - `cpu_model: str | None` (default: `None`)
  - `memory_mb: int | None` (default: `None`)
  - `machine: str | None` (default: `None`)
  - `uefi: str | None` (default: `None`)
  - `disks: tuple[DiskInfo, ...]` (default: `()`)
  - `nics: tuple[NicInfo, ...]` (default: `()`)
  - `console: ConsoleInfo | None` (default: `None`)
  - `pid: int | None` (default: `None`)
  - `uptime: str | None` (default: `None`)
- **Methods:** `__post_init__`.

### `UserSession`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `user: str`
  - `terminal: str | None` (default: `None`)
  - `host: str | None` (default: `None`)
  - `started: str | None` (default: `None`)

### `TemperatureReading`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `sensor: str`
  - `celsius: float`

### `ProcessSample`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `pid: int`
  - `ppid: int | None` (default: `None`)
  - `username: str | None` (default: `None`)
  - `cpu_pct: float | None` (default: `None`)
  - `memory_pct: float | None` (default: `None`)
  - `threads: int | None` (default: `None`)
  - `state: str | None` (default: `None`)
  - `command: str | None` (default: `None`)
  - `exe: str | None` (default: `None`)
  - `started: str | None` (default: `None`)
  - `uptime: str | None` (default: `None`)

### `HostMetrics`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `cpu_pct: float | None` (default: `None`)
  - `logical_cores: int | None` (default: `None`)
  - `physical_cores: int | None` (default: `None`)
  - `memory_used_bytes: int | None` (default: `None`)
  - `memory_total_bytes: int | None` (default: `None`)
  - `swap_used_bytes: int | None` (default: `None`)
  - `swap_total_bytes: int | None` (default: `None`)
  - `hostname: str | None` (default: `None`)
  - `uptime: str | None` (default: `None`)
  - `os_version: str | None` (default: `None`)
  - `interfaces: tuple[NetworkInterface, ...]` (default: `()`)
  - `storage: tuple[StoragePartition, ...]` (default: `()`)
  - `host_id: str | None` (default: `None`)
  - `platform_family: str | None` (default: `None`)
  - `kernel_version: str | None` (default: `None`)
  - `virtualization: str | None` (default: `None`)
  - `boot_time: str | None` (default: `None`)
  - `uptime_seconds: int | None` (default: `None`)
  - `cpu_count: int | None` (default: `None`)
  - `cpu_model: str | None` (default: `None`)
  - `cpu_current_hz: float | None` (default: `None`)
  - `run_queue: int | None` (default: `None`)
  - `blocked_tasks: int | None` (default: `None`)
  - `blocked_percent: float | None` (default: `None`)
  - `total_tasks: int | None` (default: `None`)
  - `num_processes: int | None` (default: `None`)
  - `num_threads: int | None` (default: `None`)
  - `open_fds: int | None` (default: `None`)
  - `context_switches: int | None` (default: `None`)
  - `interrupts: int | None` (default: `None`)
  - `forks: int | None` (default: `None`)
  - `temperatures: tuple[TemperatureReading, ...]` (default: `()`)
  - `users: tuple[UserSession, ...]` (default: `()`)
  - `processes: tuple[ProcessSample, ...]` (default: `()`)
  - `process_total: int | None` (default: `None`)
  - `command_summary: tuple[tuple[str, int], ...]` (default: `()`)

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not raw or raw == '—'`
- `raw.casefold() == 'auto'`
- `not matched or hostname is None`
- `raw.casefold() == hostname.casefold()`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `value in identifiers (comprehension)`

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `.enums`.
- **Standard-library/third-party imports:** `__future__`, `dataclasses`.

## 11. Real-world scenario

Host telemetry and VM-detail domain values.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`host.py` is part of `pvm_control_engine`. Host telemetry and VM-detail domain values. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

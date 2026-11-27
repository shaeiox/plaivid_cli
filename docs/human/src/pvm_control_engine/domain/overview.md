# Human-readable documentation for `overview.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/overview.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Read-only monitoring facts. Missing measurements are None, never synthetic zeroes.

## 2. Functional summary

Read-only monitoring facts. Missing measurements are None, never synthetic zeroes.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

No top-level functions or class methods are declared in this file.

## 6. Classes and data structures

### `LocalHostSample`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `hostname: str | None` (default: `None`)
  - `cpu_percent: float | None` (default: `None`)
  - `memory_used: int | None` (default: `None`)
  - `memory_total: int | None` (default: `None`)
  - `load1: float | None` (default: `None`)
  - `load5: float | None` (default: `None`)
  - `load15: float | None` (default: `None`)
  - `uptime_seconds: float | None` (default: `None`)
  - `pvm_uptime_seconds: float | None` (default: `None`)
  - `sballd_pid_file: bool | None` (default: `None`)

### `DashboardSample`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `host_name: str | None` (default: `None`)
  - `host_id: str | None` (default: `None`)
  - `cpu_info: tuple[str, ...]` (default: `()`)
  - `ram_free_raw: str | None` (default: `None`)
  - `ram_used_raw: str | None` (default: `None`)
  - `ram_total_raw: str | None` (default: `None`)
  - `vm_cpu: tuple[tuple[str, str], ...]` (default: `()`)
  - `vm_ram: tuple[tuple[str, str], ...]` (default: `()`)
  - `vm_network: tuple[tuple[str, str], ...]` (default: `()`)
  - `vdis: tuple[tuple[str, str], ...]` (default: `()`)

### `PhysicalNic`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str`
  - `identifier: str | None` (default: `None`)
  - `mac: str | None` (default: `None`)
  - `ip: str | None` (default: `None`)
  - `gateway: str | None` (default: `None`)
  - `management: str | None` (default: `None`)
  - `redundancy: str | None` (default: `None`)

### `NicSample`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `name: str`
  - `rx_bytes: int | None` (default: `None`)
  - `tx_bytes: int | None` (default: `None`)
  - `rx_packets: int | None` (default: `None`)
  - `tx_packets: int | None` (default: `None`)
  - `rx_errors: int | None` (default: `None`)
  - `tx_errors: int | None` (default: `None`)
  - `rx_dropped: int | None` (default: `None`)
  - `tx_dropped: int | None` (default: `None`)
  - `rx_crc_errors: int | None` (default: `None`)
  - `state: str | None` (default: `None`)
  - `rx_bytes_per_second: float | None` (default: `None`)
  - `tx_bytes_per_second: float | None` (default: `None`)

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** none directly declared.
- **Standard-library/third-party imports:** `__future__`, `dataclasses`.

## 11. Real-world scenario

Read-only monitoring facts. Missing measurements are None, never synthetic zeroes.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`overview.py` is part of `pvm_control_engine`. Read-only monitoring facts. Missing measurements are None, never synthetic zeroes. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

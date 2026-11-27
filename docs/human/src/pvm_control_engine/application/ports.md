# Human-readable documentation for `ports.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/application/ports.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Narrow outbound capabilities required by application use cases.

## 2. Functional summary

Narrow outbound capabilities required by application use cases.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `PvmGateway.login(self, username: str, password: str) -> PvmSession`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.validate_session(self, session: PvmSession) -> bool`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.logout(self, session: PvmSession) -> None`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.list_objects(self, token: str) -> SourceResult[tuple[ObjectVM, ...]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.list_desktops(self, token: str) -> SourceResult[tuple[VirtualDesktop, ...]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.list_processes(self) -> SourceResult[tuple[ProcessObservation, ...]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.host_status(self, token: str) -> SourceResult[HostStatus | None]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.host_metrics(self, token: str) -> SourceResult[HostMetrics | None]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.vm_detail(self, token: str, uuid: str) -> SourceResult[VMDetail | None]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.tap_mapping(self, token: str) -> SourceResult[dict[str, str]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `PvmGateway.is_daemon_alive(self, timeout: float=2.0, *, token: str | None=None) -> bool`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `MonitoringGateway.dashboard(self, token: str) -> SourceResult[DashboardSample]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `MonitoringGateway.local_host(self) -> SourceResult[LocalHostSample]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `MonitoringGateway.physical_nics(self, token: str) -> SourceResult[tuple[PhysicalNic, ...]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `MonitoringGateway.nic_samples(self, devices: tuple[PhysicalNic, ...]) -> SourceResult[tuple[NicSample, ...]]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `AuditGateway.recent(self, limit: int) -> tuple[AuditEntry, ...]`

No explicit return statement; the function returns `None` unless an exception interrupts execution.

## 6. Classes and data structures

### `PvmGateway`

- **Bases:** Protocol.
- **Description:** Class declared with bases: Protocol.
- **Methods:** `login`, `validate_session`, `logout`, `list_objects`, `list_desktops`, `list_processes`, `host_status`, `host_metrics`, `vm_detail`, `tap_mapping`, `is_daemon_alive`.

### `MonitoringGateway`

- **Bases:** Protocol.
- **Description:** Optional read-only extension; existing PvmGateway implementations still work.
- **Methods:** `dashboard`, `local_host`, `physical_nics`, `nic_samples`.

### `AuditGateway`

- **Bases:** Protocol.
- **Description:** Class declared with bases: Protocol.
- **Methods:** `recent`.

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.overview`.
- **Standard-library/third-party imports:** `__future__`, `typing`.

Related module documentation:

- [`pvm_control_engine.domain.desktops`](../domain/desktops.md)
- [`pvm_control_engine.domain.models`](../domain/models/__init__.md)
- [`pvm_control_engine.domain.overview`](../domain/overview.md)

## 11. Real-world scenario

Narrow outbound capabilities required by application use cases.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`ports.py` is part of `pvm_control_engine`. Narrow outbound capabilities required by application use cases. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

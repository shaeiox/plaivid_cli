# Human-readable documentation for `local.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/pvm/adapter/local.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Local PVM gateway implementation over bounded local process adapters.

## 2. Functional summary

Local PVM gateway implementation over bounded local process adapters.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `LocalPvmAdapter.__init__(self, sbell: SbellClient, process_runner: ProcessRunner, running_vms_argv: Sequence[str], *, allow_credential_argv: bool=False, action_timeout: float=10.0) -> None`

Calls `tuple`, `LinuxMonitor`, `any`, `ValueError`, `math.isfinite`. Reads or updates `self._sbell`, `self._runner`, `self._running_argv`, `self._allow_credential_argv`, `self._action_timeout`, `self._local_monitor`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('pvm-running-vms executable must be a non-empty argv')`, `ValueError('action_timeout must be finite and positive')`.

### `LocalPvmAdapter._call(self, module: str, command: str, params: str='<params/>', token: str | None=None, *, timeout: float | None=None) -> SbellResponse`

Calls `AppError`, `self._sbell.call`, `str`. Explicit return value(s): `self._sbell.call(module, command, params, token, timeout=timeout)`. Can raise `AppError(ErrorKind.POLICY, 'sbell token argv exposure requires explicit operator acknowledgement', c`, `AppError(ErrorKind.PROCESS, str(exc), code='PROCESS_START_FAILED')`, `AppError(ErrorKind.PROCESS, str(exc), code='PVM_COMMAND_TIMEOUT')`, `AppError(ErrorKind.PROCESS, str(exc), code='PVM_PROCESS_ERROR')`.

### `LocalPvmAdapter._require_read(response: SbellResponse, operation: str) -> ET.Element`

Calls `redact_text`, `AppError`, `ERRNO_HINT.get`, `operation.upper().replace`, `operation.upper`. Reads or updates `details`, `safe`, `code`. Explicit return value(s): `response.description`. Can raise `AppError(ErrorKind.PVM_RESPONSE, f'{operation} failed ({code}): {safe}', code=f"PVM_{operation.upper`, `AppError(ErrorKind.PROTOCOL, f'{operation} returned no description', code='PVM_DESCRIPTION_MISSING')`.

### `LocalPvmAdapter.login(self, username: str, password: str) -> PvmSession`

Calls `self._call`, `PvmSession`, `AppError`, `login_params`, `ERRNO_HINT.get`. Reads or updates `response`, `token`, `details`. Explicit return value(s): `PvmSession(username=username, token=token, authenticated_at=datetime.now(UTC))`. Can raise `AppError(ErrorKind.POLICY, 'sbell password argv exposure requires explicit operator acknowledgement'`, `AppError(ErrorKind.AUTHENTICATION, redact_text(details), code=f"PVM_LOGIN_{response.errno or 'FAILED`, `AppError(ErrorKind.PROTOCOL, 'login response did not contain a token', code='PVM_LOGIN_TOKEN_MISSING`.

### `LocalPvmAdapter.validate_session(self, session: PvmSession) -> bool`

Calls `self._call`. Reads or updates `response`. Explicit return value(s): `response.ok`.

### `LocalPvmAdapter.logout(self, session: PvmSession) -> None`

Calls `self._call`, `AppError`. Reads or updates `response`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `AppError(ErrorKind.AUTHENTICATION, 'PVM logout was rejected', code=f"PVM_LOGOUT_{response.errno or '`.

### `LocalPvmAdapter.list_objects(self, token: str) -> SourceResult[tuple[ObjectVM, ...]]`

Calls `self._require_read`, `parse_object_inventory`, `self._call`. Reads or updates `description`. Explicit return value(s): `parse_object_inventory(description)`.

### `LocalPvmAdapter.list_desktops(self, token: str) -> SourceResult[tuple[VirtualDesktop, ...]]`

Calls `self._require_read`, `parse_virtual_desktops`, `self._call`. Reads or updates `description`. Explicit return value(s): `parse_virtual_desktops(description)`.

### `LocalPvmAdapter.list_processes(self) -> SourceResult[tuple[ProcessObservation, ...]]`

Calls `parse_process_rows`, `self._runner.run`, `result.stdout.strip`, `AppError`, `SourceResult`. Reads or updates `parsed`, `result`, `issues`, `reason`. Explicit return value(s): `parsed`, `SourceResult(value=parsed.value, status=CollectionStatus.PARTIAL, source='pvm-running-vms', error=re`. Can raise `AppError(ErrorKind.PROCESS, f'pvm-running-vms returned no output (exit {result.returncode})', code='`, `AppError(ErrorKind.PROCESS, str(exc), code='RUNNING_VMS_PROCESS_ERROR')`.

### `LocalPvmAdapter.host_status(self, token: str) -> SourceResult[HostStatus | None]`

Calls `self._call`, `self._require_read`, `parse_sball_status`. Reads or updates `response`, `description`. Explicit return value(s): `parse_sball_status(description)`.

### `LocalPvmAdapter.host_metrics(self, token: str) -> SourceResult[HostMetrics | None]`

Calls `self._call`, `self._require_read`, `parse_metrics`. Reads or updates `response`, `description`. Explicit return value(s): `parse_metrics(description)`.

### `LocalPvmAdapter.vm_detail(self, token: str, uuid: str) -> SourceResult[VMDetail | None]`

Calls `canonical_uuid`, `self._call`, `self._require_read`, `parse_vm_detail`. Reads or updates `key`, `query`, `response`, `description`. Explicit return value(s): `parse_vm_detail(description, key)`.

### `LocalPvmAdapter.tap_mapping(self, token: str) -> SourceResult[dict[str, str]]`

Calls `self._call`, `self._require_read`, `parse_tap_mapping`. Reads or updates `response`, `description`. Explicit return value(s): `parse_tap_mapping(description)`.

### `LocalPvmAdapter.dashboard(self, token: str) -> SourceResult[DashboardSample]`

Calls `self._require_read`, `parse_dashboard`, `self._call`. Reads or updates `description`. Explicit return value(s): `parse_dashboard(description)`.

### `LocalPvmAdapter.local_host(self) -> SourceResult[LocalHostSample]`

Calls `self._local_monitor.host`, `replace`, `SourceResult`, `self._sball_uptime_seconds`, `sballd_pid_file_present`. Reads or updates `sample`, `status`. Explicit return value(s): `SourceResult(sample, status, 'local /proc, systemctl sballd')`.

### `LocalPvmAdapter._sball_uptime_seconds(self) -> float | None`

Calls `sball_uptime_seconds`, `self._runner.run`, `datetime.now`. Reads or updates `result`. Explicit return value(s): `sball_uptime_seconds(result.stdout, datetime.now(UTC))`, `None`.

### `LocalPvmAdapter.physical_nics(self, token: str) -> SourceResult[tuple[PhysicalNic, ...]]`

Calls `self._require_read`, `parse_nic_list`, `tuple`, `SourceResult`, `self._call`. Reads or updates `description`, `result`, `physical`. Explicit return value(s): `SourceResult(physical, result.status, result.source, quality_issues=result.quality_issues)`, `result`.

### `LocalPvmAdapter.nic_samples(self, devices: tuple[PhysicalNic, ...]) -> SourceResult[tuple[NicSample, ...]]`

Calls `tuple`, `self._local_monitor.nics`, `SourceResult`, `any`, `self._local_monitor.physical`. Reads or updates `physical`, `samples`, `status`. Explicit return value(s): `SourceResult(samples, status, 'local sysfs')`.

### `LocalPvmAdapter.is_daemon_alive(self, timeout: float=2.0, *, token: str | None=None) -> bool`

Probe ``sballd`` responsiveness with a short bounded deadline.

### `LocalPvmAdapter.authenticate_argv_warning(self) -> str`

Explicit return value(s): `'sbell credentials and tokens are passed in process arguments; this is not verified safe'`.

## 6. Classes and data structures

### `LocalPvmAdapter`

- **Bases:** no explicit base class.
- **Description:** Adapt the repository's existing local commands to typed source values.
- **Methods:** `__init__`, `_call`, `_require_read`, `login`, `validate_session`, `logout`, `list_objects`, `list_desktops`, `list_processes`, `host_status`, `host_metrics`, `vm_detail`, `tap_mapping`, `dashboard`, `local_host`, `_sball_uptime_seconds`, `physical_nics`, `nic_samples`, `is_daemon_alive`, `authenticate_argv_warning`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not running_vms_argv or any((not part for part in running_vms_argv))`
- `not math.isfinite(action_timeout) or action_timeout <= 0`
- `token and (not self._allow_credential_argv)`
- `not response.ok`
- `response.description is None`
- `not self._allow_credential_argv`
- `not response.ok`
- `not token`
- `not response.ok`
- `not result.stdout.strip()`
- `result.returncode != 0 or result.stdout_truncated`
- `result.value is None`
- `not math.isfinite(timeout) or timeout <= 0`
- `response.ok`
- `result.stdout_truncated`
- `sample.memory_total is not None and sample.load1 is not None` (with an `else` branch)
- `any((sample.rx_bytes is None or sample.tx_bytes is None for sample in samples))` (with an `else` branch)
- `token and self._allow_credential_argv` (with an `else` branch)
- `result.returncode != 0` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `item in result.value (comprehension)`
- `item in devices (comprehension)`
- `part in running_vms_argv (comprehension)`
- `sample in samples (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 99) handles: ProcessStartError, ProcessTimeout, ProcessError.
- `try` block (line 183) handles: ProcessError.
- `try` block (line 256) handles: ProcessError.
- `try` block (line 290) handles: (AppError, ProcessError, ValueError).

Explicitly raised exception expressions: `ValueError('pvm-running-vms executable must be a non-empty argv')`, `ValueError('action_timeout must be finite and positive')`, `AppError(ErrorKind.POLICY, 'sbell token argv exposure requires explicit operator acknowledgement', c`, `AppError(ErrorKind.PVM_RESPONSE, f'{operation} failed ({code}): {safe}', code=f"PVM_{operation.upper`, `AppError(ErrorKind.PROTOCOL, f'{operation} returned no description', code='PVM_DESCRIPTION_MISSING')`, `AppError(ErrorKind.POLICY, 'sbell password argv exposure requires explicit operator acknowledgement'`, `AppError(ErrorKind.AUTHENTICATION, redact_text(details), code=f"PVM_LOGIN_{response.errno or 'FAILED`, `AppError(ErrorKind.PROTOCOL, 'login response did not contain a token', code='PVM_LOGIN_TOKEN_MISSING`, `AppError(ErrorKind.AUTHENTICATION, 'PVM logout was rejected', code=f"PVM_LOGOUT_{response.errno or '`, `AppError(ErrorKind.PROCESS, f'pvm-running-vms returned no output (exit {result.returncode})', code='`, `ValueError('timeout must be finite and positive')`, `AppError(ErrorKind.PROCESS, str(exc), code='PROCESS_START_FAILED')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.overview`, `pvm_control_engine.infrastructure.diagnostics`, `pvm_control_engine.infrastructure.local_monitor`, `pvm_control_engine.infrastructure.process`, `pvm_control_engine.infrastructure.pvm.overview`, `pvm_control_engine.infrastructure.pvm.parsers`, `pvm_control_engine.infrastructure.pvm.sbell`, `pvm_control_engine.infrastructure.pvm.uptime`, `pvm_control_engine.infrastructure.sbell.commands.user.login`, `.requests`.
- **Standard-library/third-party imports:** `__future__`, `math`, `xml.etree.ElementTree`, `collections.abc`, `dataclasses`, `datetime`.

Related module documentation:

- [`pvm_control_engine.domain.desktops`](../../../domain/desktops.md)
- [`pvm_control_engine.domain.errors`](../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../domain/models/__init__.md)
- [`pvm_control_engine.domain.overview`](../../../domain/overview.md)
- [`pvm_control_engine.infrastructure.diagnostics`](../../diagnostics.md)
- [`pvm_control_engine.infrastructure.local_monitor`](../../local_monitor.md)
- [`pvm_control_engine.infrastructure.process`](../../process.md)
- [`pvm_control_engine.infrastructure.pvm.overview`](../overview.md)
- [`pvm_control_engine.infrastructure.pvm.parsers`](../parsers/__init__.md)
- [`pvm_control_engine.infrastructure.pvm.sbell`](../sbell.md)
- [`pvm_control_engine.infrastructure.pvm.uptime`](../uptime.md)
- [`pvm_control_engine.infrastructure.sbell.commands.user.login`](../../sbell/commands/user/login.md)

## 11. Real-world scenario

Local PVM gateway implementation over bounded local process adapters.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`local.py` is part of `pvm_control_engine`. Local PVM gateway implementation over bounded local process adapters. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

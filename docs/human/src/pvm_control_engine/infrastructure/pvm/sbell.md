# Human-readable documentation for `sbell.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/pvm/sbell.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Minimal argv-based adapter for the existing local ``sbell`` command.

## 2. Functional summary

Minimal argv-based adapter for the existing local ``sbell`` command.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `SbellResponse.ok(self) -> bool`

Explicit return value(s): `self.status == 'success'`.

### `SbellResponse.token(self) -> str | None`

Calls `self.description.text.strip`. Reads or updates `value`. Explicit return value(s): `value or None`, `None`.

### `SbellResponse.reply(self) -> PvmReply`

Calls `PvmReply`. Explicit return value(s): `PvmReply(status=self.status, action_id=self.action_id, errno=self.errno, message=self.what, returnco`.

### `SbellClient.__init__(self, executable: Sequence[str], runner: ProcessRunner, *, allow_credential_argv: bool=False) -> None`

Calls `tuple`, `any`, `ValueError`. Reads or updates `self._executable`, `self._runner`, `self._allow_credential_argv`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('sbell executable must be a non-empty argv')`.

### `SbellClient.call(self, module: str, command: str, params: str='<params/>', token: str | None=None, *, timeout: float | None=None) -> SbellResponse`

Calls `(root.findtext('status') or '').strip().lower`, `root.find`, `root.findtext`, `SbellResponse`, `ValueError`. Reads or updates `argv`, `status`, `description`, `errno`, `what`, `action_id`. Explicit return value(s): `SbellResponse(status=status, action_id=action_id, errno=errno, what=what, description=description, r`. Can raise `ValueError('invalid sbell module or command')`, `ValueError('sbell params must be non-empty XML text')`, `AppError(ErrorKind.POLICY, 'sbell token argv exposure requires explicit operator acknowledgement', c`, `AppError(ErrorKind.PROTOCOL, 'sbell response exceeded the configured output limit', code='SBELL_OUTP`.

## 6. Classes and data structures

### `SbellResponse`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `status: str`
  - `action_id: str | None`
  - `errno: str | None`
  - `what: str | None`
  - `description: ET.Element | None` (default: `field(repr=False)`)
  - `returncode: int`
- **Methods:** `ok`, `token`, `reply`.

### `SbellClient`

- **Bases:** no explicit base class.
- **Description:** Run an existing ``sbell MODULE COMMAND PARAMS [TOKEN]`` invocation.
- **Methods:** `__init__`, `call`.

### Module-level values

- `_IDENTIFIER` = `re.compile('^[A-Za-z0-9_-]+$')`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `self.description is None or not self.description.text`
- `not executable or any((not part for part in executable))`
- `not _IDENTIFIER.fullmatch(module) or not _IDENTIFIER.fullmatch(command)`
- `not isinstance(params, str) or not params`
- `token and (not self._allow_credential_argv)`
- `token`
- `result.stdout_truncated`
- `not result.stdout.strip()`
- `not status`
- `description is not None` (with an `else` branch)
- `description is not None` (with an `else` branch)
- `timeout is None` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `part in executable (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 90) handles: ProcessStartError, ProcessTimeout, ProcessError.
- `try` block (line 114) handles: ET.ParseError.

Explicitly raised exception expressions: `ValueError('sbell executable must be a non-empty argv')`, `ValueError('invalid sbell module or command')`, `ValueError('sbell params must be non-empty XML text')`, `AppError(ErrorKind.POLICY, 'sbell token argv exposure requires explicit operator acknowledgement', c`, `AppError(ErrorKind.PROTOCOL, 'sbell response exceeded the configured output limit', code='SBELL_OUTP`, `AppError(ErrorKind.PROCESS, f'sbell returned no response (exit {result.returncode})', code='SBELL_NO`, `AppError(ErrorKind.PROTOCOL, 'sbell response did not contain a status', code='SBELL_STATUS_MISSING')`, `AppError(ErrorKind.PROCESS, str(exc), code='PROCESS_START_FAILED')`, `AppError(ErrorKind.PROCESS, str(exc), code='PVM_COMMAND_TIMEOUT')`, `AppError(ErrorKind.PROCESS, str(exc), code='PVM_PROCESS_ERROR')`, `AppError(ErrorKind.PROTOCOL, 'sbell returned invalid XML', code='SBELL_INVALID_XML')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.infrastructure.process`.
- **Standard-library/third-party imports:** `__future__`, `re`, `xml.etree.ElementTree`, `collections.abc`, `dataclasses`.

Related module documentation:

- [`pvm_control_engine.domain.errors`](../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../domain/models/__init__.md)
- [`pvm_control_engine.infrastructure.process`](../process.md)

## 11. Real-world scenario

Minimal argv-based adapter for the existing local ``sbell`` command.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`sbell.py` is part of `pvm_control_engine`. Minimal argv-based adapter for the existing local ``sbell`` command. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

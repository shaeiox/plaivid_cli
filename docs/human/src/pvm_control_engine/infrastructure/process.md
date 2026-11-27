# Human-readable documentation for `process.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/process.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Bounded subprocess execution for local PVM commands. Arguments are passed as a vector and are never interpreted by a shell. Output is continuously drained but only a configured prefix is retained in memory.

## 2. Functional summary

Bounded subprocess execution for local PVM commands. Arguments are passed as a vector and are never interpreted by a shell. Output is continuously drained but only a configured prefix is retained in memory.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `_safe_child_environment() -> dict[str, str]`

Keep command lookup and locale/user context; omit ambient credentials.

### `ProcessTimeout.__init__(self, *, reaped: bool) -> None`

Calls `super().__init__`, `super`. Reads or updates `self.reaped`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `_Capture.__init__(self, limit: int) -> None`

Calls `threading.Lock`. Reads or updates `self.limit`, `self.parts`, `self.size`, `self.truncated`, `self.lock`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `_Capture.append(self, data: bytes) -> None`

Calls `max`, `self.parts.append`, `len`. Reads or updates `keep`, `fragment`, `self.size`, `self.truncated`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `_Capture.text(self) -> str`

Calls `raw.decode`, `b''.join`. Reads or updates `raw`. Explicit return value(s): `raw.decode('utf-8', errors='replace')`.

### `ProcessRunner.__init__(self, *, timeout: float=30.0, max_output_bytes: int=1048576, terminate_grace: float=2.0, cwd: str | Path | None=None, env: Mapping[str, str] | None=None) -> None`

Calls `ValueError`, `str`, `dict`, `_safe_child_environment`, `math.isfinite`. Reads or updates `self.timeout`, `self.max_output_bytes`, `self.terminate_grace`, `self.cwd`, `self.env`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('timeout must be finite and positive')`, `ValueError('max_output_bytes must be positive')`, `ValueError('terminate_grace must be finite and positive')`.

### `ProcessRunner.run(self, argv: Sequence[str], *, timeout: float | None=None) -> ProcessResult`

Calls `tuple`, `any`, `time.monotonic`, `_Capture`, `self._finish_readers`. Reads or updates `command`, `deadline`, `started`, `stdout`, `stderr`, `readers`. Explicit return value(s): `ProcessResult(returncode=child.returncode, stdout=stdout.text(), stderr=stderr.text(), stdout_trunca`, `None`. Can raise `ValueError('argv must be a non-empty sequence of strings')`, `ValueError('argv must contain non-empty strings')`, `ValueError('timeout must be finite and positive')`, `ProcessStartError('could not start configured local command')`.

### `ProcessRunner._finish_readers(self, readers: list[threading.Thread], child: subprocess.Popen[bytes]) -> None`

Calls `any`, `reader.join`, `self._kill_process_tree`, `self._close_pipes`, `reader.is_alive`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ProcessCleanupError('process output readers did not stop after cleanup')`.

### `ProcessRunner._kill_process_tree(child: subprocess.Popen[bytes]) -> None`

Kill the isolated POSIX process group; fall back to the direct child.

### `ProcessRunner._close_pipes(child: subprocess.Popen[bytes]) -> None`

Calls `pipe.close`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### Lexically nested definitions

#### `ProcessRunner.run.drain(pipe: object, capture: _Capture) -> None`

Calls `pipe.read`, `capture.append`. Reads or updates `chunk`. Explicit return value(s): `None`.

## 6. Classes and data structures

### `ProcessError`

- **Bases:** RuntimeError.
- **Description:** Safe process-boundary error; deliberately excludes argv and raw output.

### `ProcessStartError`

- **Bases:** ProcessError.
- **Description:** A configured local executable could not be started.

### `ProcessTimeout`

- **Bases:** ProcessError.
- **Description:** The command exceeded its deadline; ``reaped`` reports direct-child cleanup.
- **Methods:** `__init__`.

### `ProcessCleanupError`

- **Bases:** ProcessError.
- **Description:** The direct child could not be reaped within the cleanup deadline.

### `ProcessResult`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `returncode: int`
  - `stdout: str`
  - `stderr: str`
  - `stdout_truncated: bool`
  - `stderr_truncated: bool`
  - `elapsed_seconds: float`

### `_Capture`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Methods:** `__init__`, `append`, `text`.

### `ProcessRunner`

- **Bases:** no explicit base class.
- **Description:** Run one argv command with bounded output and POSIX process-group cleanup.
- **Methods:** `__init__`, `run`, `_finish_readers`, `_kill_process_tree`, `_close_pipes`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not math.isfinite(timeout) or timeout <= 0`
- `max_output_bytes <= 0`
- `not math.isfinite(terminate_grace) or terminate_grace <= 0`
- `isinstance(argv, (str, bytes)) or not argv`
- `any((not isinstance(part, str) or not part for part in command))`
- `not math.isfinite(deadline) or deadline <= 0`
- `any((reader.is_alive() for reader in readers))`
- `os.name == 'posix'`
- `keep`
- `len(data) > keep`
- `cwd is not None` (with an `else` branch)
- `env is not None` (with an `else` branch)
- `timeout is None` (with an `else` branch)
- `any((reader.is_alive() for reader in readers))`
- `pipe is not None`
- `not chunk`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `(pipe, capture, name) in ((child.stdout, stdout, 'stdout'), (child.stderr, stderr, 'stderr'))`
- `reader in readers`
- `pipe in (child.stdout, child.stderr)`
- `(key, value) in os.environ.items() (comprehension)`
- `reader in readers`
- `while True`
- `part in command (comprehension)`
- `reader in readers (comprehension)`
- `reader in readers (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 118) handles: OSError.
- `try` block (line 159) handles: subprocess.TimeoutExpired.
- `try` block (line 207) handles: ProcessLookupError.
- `try` block (line 140) handles: (OSError, ValueError).
- `try` block (line 200) handles: ProcessLookupError, OSError.
- `try` block (line 163) handles: subprocess.TimeoutExpired.
- `try` block (line 216) handles: OSError.

Explicitly raised exception expressions: `ValueError('timeout must be finite and positive')`, `ValueError('max_output_bytes must be positive')`, `ValueError('terminate_grace must be finite and positive')`, `ValueError('argv must be a non-empty sequence of strings')`, `ValueError('argv must contain non-empty strings')`, `ProcessStartError('could not start configured local command')`, `ProcessTimeout(reaped=True)`, `ProcessCleanupError('process output readers did not stop after cleanup')`, `ProcessCleanupError('timed-out local child could not be reaped')`.

## 10. Dependencies and interactions

- **Project imports:** none directly declared.
- **Standard-library/third-party imports:** `__future__`, `math`, `os`, `signal`, `subprocess`, `threading`, `time`, `collections.abc`, `dataclasses`, `pathlib`.

## 11. Real-world scenario

Bounded subprocess execution for local PVM commands. Arguments are passed as a vector and are never interpreted by a shell. Output is continuously drained but only a configured prefix is retained in memory.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`process.py` is part of `pvm_control_engine`. Bounded subprocess execution for local PVM commands. Arguments are passed as a vector and are never interpreted by a shell. Output is continuously drained but only a configured prefix is retained in memory. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

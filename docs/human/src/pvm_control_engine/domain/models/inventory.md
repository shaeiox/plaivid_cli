# Human-readable documentation for `inventory.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/models/inventory.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** PVM object records and correlated local process observations.

## 2. Functional summary

PVM object records and correlated local process observations.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `resolve_console_port(record: VMRecord, detail: VMDetail | None=None) -> int | None`

Resolve the console port from the strongest available evidence. Precedence: live local process observation (`pvm-running-vms`), then the port configured on the object record, then the asynchronous detail read, then unknown (``None``). A configured port is never reported as a live one: the first source that provides a value wins and nothing is derived.

### `ObjectVM.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`, `ValueError`, `self.name.strip`, `self.state.strip().lower`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('vcpu cannot be negative')`, `ValueError('mem_mb cannot be negative')`.

### `ProcessObservation.__post_init__(self) -> None`

Calls `object.__setattr__`, `canonical_uuid`, `ValueError`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('pid must be positive')`.

### `VMRecord.uuid(self) -> str`

Explicit return value(s): `self.object.uuid`.

### `VMRecord.name(self) -> str`

Explicit return value(s): `self.object.name`.

### `VMRecord.state(self) -> str`

Explicit return value(s): `self.object.state`.

### `VMRecord.process_seen(self) -> bool`

Explicit return value(s): `self.process is not None`.

### `VMRecord.vcpu(self) -> int | None`

Explicit return value(s): `self.object.vcpu`.

### `VMRecord.mem_mb(self) -> int | None`

Explicit return value(s): `self.object.mem_mb`.

### `VMRecord.host(self) -> str | None`

Explicit return value(s): `self.object.host`.

## 6. Classes and data structures

### `ObjectVM`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `uuid: str`
  - `name: str`
  - `state: str` (default: `'unknown'`)
  - `vcpu: int | None` (default: `None`)
  - `mem_mb: int | None` (default: `None`)
  - `description: str` (default: `''`)
  - `configured_port: int | None` (default: `None`)
  - `host: str | None` (default: `None`)
- **Methods:** `__post_init__`.

### `ProcessObservation`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `uuid: str`
  - `pid: int | None` (default: `None`)
  - `uptime: str | None` (default: `None`)
  - `port: int | None` (default: `None`)
  - `vcpu: int | None` (default: `None`)
  - `mem_mb: int | None` (default: `None`)
  - `name: str` (default: `''`)
  - `row_number: int | None` (default: `None`)
- **Methods:** `__post_init__`.

### `VMRecord`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `object: ObjectVM`
  - `process: ProcessObservation | None` (default: `None`)
  - `state_disagreed: bool` (default: `False`)
  - `quality_issues: tuple[str, ...]` (default: `()`)
- **Methods:** `uuid`, `name`, `state`, `process_seen`, `vcpu`, `mem_mb`, `host`.

### `InventoryData`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Annotated fields:**
  - `objects: tuple[ObjectVM, ...]` (default: `()`)
  - `process_rows: tuple[ProcessObservation, ...]` (default: `()`)
  - `records: tuple[VMRecord, ...]` (default: `()`)
  - `unmatched_process_rows: tuple[ProcessObservation, ...]` (default: `()`)
  - `quality_issues: tuple[str, ...]` (default: `()`)

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `TYPE_CHECKING`
- `record.process is not None and record.process.port is not None`
- `record.object.configured_port is not None`
- `detail is not None and detail.console is not None`
- `self.vcpu is not None and self.vcpu < 0`
- `self.mem_mb is not None and self.mem_mb < 0`
- `self.pid is not None and self.pid <= 0`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

Explicitly raised exception expressions: `ValueError('vcpu cannot be negative')`, `ValueError('mem_mb cannot be negative')`, `ValueError('pid must be positive')`.

## 10. Dependencies and interactions

- **Project imports:** `.enums`.
- **Standard-library/third-party imports:** `__future__`, `dataclasses`, `typing`.

## 11. Real-world scenario

PVM object records and correlated local process observations.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`inventory.py` is part of `pvm_control_engine`. PVM object records and correlated local process observations. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

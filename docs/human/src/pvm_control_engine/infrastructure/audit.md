# Human-readable documentation for `audit.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/audit.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Optional, bounded, read-only access to the PVM-owned audit database.

## 2. Functional summary

Optional, bounded, read-only access to the PVM-owned audit database.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `ReadOnlyAuditAdapter.__init__(self, database: Path) -> None`

Calls `database.expanduser`. Reads or updates `self._database`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `ReadOnlyAuditAdapter.recent(self, limit: int=40) -> tuple[AuditEntry, ...]`

Calls `tuple`, `ValueError`, `sqlite3.connect`, `connection.execute('SELECT time, user, user_ip, product, message FROM Log WHERE user != ? AND messag`, `connection.close`. Reads or updates `uri`, `entries`, `connection`, `columns`, `rows`, `match`. Explicit return value(s): `tuple(entries)`. Can raise `ValueError('audit row limit must be between 1 and 500')`, `AppError(ErrorKind.AUDIT, 'audit database is unavailable', code='AUDIT_OPEN_FAILED')`, `AppError(ErrorKind.AUDIT, 'audit database schema is unsupported', code='AUDIT_SCHEMA_UNSUPPORTED')`, `AppError(ErrorKind.AUDIT, 'audit query failed', code='AUDIT_QUERY_FAILED')`.

### `ReadOnlyAuditAdapter.summarize(entries: tuple[AuditEntry, ...]) -> AuditSummary`

Calls `Counter`, `AuditSummary`, `len`, `sum`, `tuple`. Reads or updates `commands`, `users`, `span`. Explicit return value(s): `AuditSummary(total=len(entries), failures=sum((not entry.succeeded for entry in entries)), top_comma`.

## 6. Classes and data structures

### `ReadOnlyAuditAdapter`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Methods:** `__init__`, `recent`, `summarize`.

### Module-level values

- `_COMMAND` = `re.compile("Command '([^']+)' has been (.+?)\\.?\\s*$")`
- `_REQUIRED_COLUMNS` = `{'time', 'user', 'user_ip', 'product', 'message'}`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `limit < 1 or limit > 500`
- `not _REQUIRED_COLUMNS.issubset(columns)`
- `match is None`
- `result.startswith('started')`
- `len(entries) >= limit`
- `entries` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `(time_value, user, ip, product, message) in rows`
- `row in connection.execute('PRAGMA table_info(Log)').fetchall() (comprehension)`
- `entry in entries (comprehension)`
- `entry in entries (comprehension)`
- `entry in entries (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 27) handles: sqlite3.Error.
- `try` block (line 33) handles: sqlite3.Error.

Explicitly raised exception expressions: `ValueError('audit row limit must be between 1 and 500')`, `AppError(ErrorKind.AUDIT, 'audit database is unavailable', code='AUDIT_OPEN_FAILED')`, `AppError(ErrorKind.AUDIT, 'audit database schema is unsupported', code='AUDIT_SCHEMA_UNSUPPORTED')`, `AppError(ErrorKind.AUDIT, 'audit query failed', code='AUDIT_QUERY_FAILED')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.infrastructure.diagnostics`.
- **Standard-library/third-party imports:** `__future__`, `re`, `sqlite3`, `collections`, `pathlib`, `urllib.parse`.

Related module documentation:

- [`pvm_control_engine.domain.errors`](../domain/errors.md)
- [`pvm_control_engine.domain.models`](../domain/models/__init__.md)
- [`pvm_control_engine.infrastructure.diagnostics`](diagnostics.md)

## 11. Real-world scenario

Optional, bounded, read-only access to the PVM-owned audit database.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`audit.py` is part of `pvm_control_engine`. Optional, bounded, read-only access to the PVM-owned audit database. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

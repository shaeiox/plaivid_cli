# Human-readable documentation for `session_store.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/auth/session_store.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Private, atomic local persistence for the Engine session token.

## 2. Functional summary

Private, atomic local persistence for the Engine session token.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `SessionStore.__init__(self, path: Path) -> None`

Calls `path.expanduser().absolute`, `path.expanduser`. Reads or updates `self.path`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `SessionStore._validate_parent(self, *, create: bool) -> None`

Calls `parent.mkdir`, `parent.stat`, `OSError`, `parent.resolve`, `os.chmod`. Reads or updates `parent`, `metadata`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `OSError('state directory is not a current-user-owned directory')`, `OSError('state directory path contains a symlink')`, `re-raise`, `OSError('state directory permissions are not private')`.

### `SessionStore.load(self) -> PvmSession | None`

Calls `self.path.is_symlink`, `PvmSession`, `self._validate_parent`, `AppError`, `os.open`. Reads or updates `(username, token)`, `flags`, `fd`, `metadata`, `value`. Explicit return value(s): `PvmSession(username=username, token=token)`, `None`. Can raise `AppError(ErrorKind.AUTHENTICATION, 'refusing to read a symlink at the cached session path', code='SE`, `AppError(ErrorKind.AUTHENTICATION, 'cached session is invalid')`, `AppError(ErrorKind.AUTHENTICATION, 'cached session directory is unsafe')`, `AppError(ErrorKind.AUTHENTICATION, 'could not safely read the cached session')`.

### `SessionStore.save(self, session: PvmSession) -> None`

Calls `self._validate_parent`, `json.dumps({'username': session.username, 'token': session.token}, separators=(',', ':')).encode`, `os.open`, `getattr`, `os.replace`. Reads or updates `parent`, `temporary`, `payload`, `flags`, `fd`, `directory_fd`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `AppError(ErrorKind.AUTHENTICATION, 'could not securely save the session')`, `re-raise`.

### `SessionStore.clear(self) -> None`

Calls `self.path.parent.is_symlink`, `self._validate_parent`, `self.path.is_symlink`, `self.path.unlink`, `AppError`. Explicit return value(s): `None`. Can raise `AppError(ErrorKind.AUTHENTICATION, 'refusing to clear the session through a symlinked state director`, `AppError(ErrorKind.AUTHENTICATION, 'refusing to remove a symlink at the cached session path', code='`, `re-raise`, `AppError(ErrorKind.AUTHENTICATION, 'could not clear the cached session')`.

## 6. Classes and data structures

### `SessionStore`

- **Bases:** no explicit base class.
- **Description:** Atomic 0600 JSON cache under the configured XDG state directory.
- **Methods:** `__init__`, `_validate_parent`, `load`, `save`, `clear`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `create`
- `self.path.is_symlink()`
- `not isinstance(value, dict)`
- `not isinstance(username, str) or not username.strip() or (not isinstance(token, str)) or (not token)`
- `not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid()`
- `parent.resolve(strict=True) != parent`
- `create` (with an `else` branch)
- `not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 63 or metadata.st_uid != os.getuid()`
- `fd >= 0`
- `self.path.parent.is_symlink()`
- `not self.path.parent.exists()`
- `self.path.is_symlink()`
- `stat.S_IMODE(metadata.st_mode) & 63`
- `not self.path.parent.exists()`
- `exc.errno == errno.ELOOP`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 26) handles: OSError.
- `try` block (line 40) handles: OSError.
- `try` block (line 52) handles: FileNotFoundError, OSError.
- `try` block (line 67) handles: AppError, (OSError, ValueError, TypeError).
- `try` block (line 103) handles: OSError.
- `try` block (line 134) handles: AppError, OSError.
- `try` block (line 112) handles: Exception.
- `try` block (line 120) handles: no typed handler.
- `try` block (line 125) handles: OSError.

Explicitly raised exception expressions: `AppError(ErrorKind.AUTHENTICATION, 'refusing to read a symlink at the cached session path', code='SE`, `AppError(ErrorKind.AUTHENTICATION, 'cached session is invalid')`, `OSError('state directory is not a current-user-owned directory')`, `OSError('state directory path contains a symlink')`, `re-raise`, `AppError(ErrorKind.AUTHENTICATION, 'cached session directory is unsafe')`, `AppError(ErrorKind.AUTHENTICATION, 'could not safely read the cached session')`, `AppError(ErrorKind.AUTHENTICATION, 'cached session ownership or permissions are unsafe; remove it an`, `AppError(ErrorKind.AUTHENTICATION, 'could not securely save the session')`, `AppError(ErrorKind.AUTHENTICATION, 'refusing to clear the session through a symlinked state director`, `AppError(ErrorKind.AUTHENTICATION, 'refusing to remove a symlink at the cached session path', code='`, `AppError(ErrorKind.AUTHENTICATION, 'could not clear the cached session')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`, `errno`, `json`, `os`, `stat`, `uuid`, `pathlib`.

Related module documentation:

- [`pvm_control_engine.domain.errors`](../domain/errors.md)
- [`pvm_control_engine.domain.models`](../domain/models/__init__.md)

## 11. Real-world scenario

Private, atomic local persistence for the Engine session token.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`session_store.py` is part of `pvm_control_engine`. Private, atomic local persistence for the Engine session token. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

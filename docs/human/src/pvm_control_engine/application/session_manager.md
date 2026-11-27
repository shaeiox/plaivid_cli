# Human-readable documentation for `session_manager.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/application/session_manager.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Session resume, login, logout, and restrictive local token storage.

## 2. Functional summary

Session resume, login, logout, and restrictive local token storage.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `SessionManager.__init__(self, provider: PvmGateway, settings: Settings, store: SessionStore) -> None`

Reads or updates `self._provider`, `self._settings`, `self._store`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `SessionManager.resume_or_login(self, *, username: str | None=None, password: str | None=None) -> tuple[PvmSession, bool]`

Calls `self._store.load`, `self._provider.login`, `self._store.save`, `self._store.clear`, `AppError`. Reads or updates `cached`, `session`. Explicit return value(s): `(session, True)`, `(cached, False)`. Can raise `AppError(ErrorKind.AUTHENTICATION, 'sign-in is required; provide credentials through the interactive`, `AppError(ErrorKind.POLICY, 'login is blocked because sbell exposes credentials in process arguments;`, `AppError(ErrorKind.AUTHENTICATION, 'username and password are required')`, `AppError(ErrorKind.AUTHENTICATION, 'cached session could not be validated; check local PVM access', `.

### `SessionManager.clear_local_cache(self) -> None`

Calls `self._store.clear`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `SessionManager.logout(self, session: PvmSession) -> None`

Calls `self._provider.logout`, `self._store.clear`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

## 6. Classes and data structures

### `SessionManager`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Methods:** `__init__`, `resume_or_login`, `clear_local_cache`, `logout`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `cached is not None`
- `username is None or password is None`
- `not self._settings.allow_credential_argv`
- `not username.strip() or not password`
- `self._provider.validate_session(cached)`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 58) handles: no typed handler.
- `try` block (line 26) handles: AppError.

Explicitly raised exception expressions: `AppError(ErrorKind.AUTHENTICATION, 'sign-in is required; provide credentials through the interactive`, `AppError(ErrorKind.POLICY, 'login is blocked because sbell exposes credentials in process arguments;`, `AppError(ErrorKind.AUTHENTICATION, 'username and password are required')`, `AppError(ErrorKind.AUTHENTICATION, 'cached session could not be validated; check local PVM access', `.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.ports`, `pvm_control_engine.auth.session_store`, `pvm_control_engine.config`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`.

Related module documentation:

- [`pvm_control_engine.application.ports`](ports.md)
- [`pvm_control_engine.auth.session_store`](../auth/session_store.md)
- [`pvm_control_engine.config`](../config.md)
- [`pvm_control_engine.domain.errors`](../domain/errors.md)
- [`pvm_control_engine.domain.models`](../domain/models/__init__.md)

## 11. Real-world scenario

Session resume, login, logout, and restrictive local token storage.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`session_manager.py` is part of `pvm_control_engine`. Session resume, login, logout, and restrictive local token storage. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.

"""Session resume, login, logout, and restrictive local token storage."""

from __future__ import annotations

import errno
import json
import os
import stat
import uuid
from pathlib import Path

from plaivid_cli.application.ports import PvmGateway
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import ErrorKind, PvmSession


class SessionStore:
    """Atomic 0600 JSON cache under the configured XDG state directory."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()

    def _validate_parent(self, *, create: bool) -> None:
        parent = self.path.parent
        if create:
            parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            metadata = parent.stat()
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise OSError("state directory is not a current-user-owned directory")
            if parent.resolve(strict=True) != parent:
                raise OSError("state directory path contains a symlink")
            if create:
                os.chmod(parent, 0o700)
            elif stat.S_IMODE(metadata.st_mode) & 0o077:
                raise OSError("state directory permissions are not private")
        except OSError:
            raise

    def load(self) -> PvmSession | None:
        try:
            self._validate_parent(create=False)
        except OSError as exc:
            if not self.path.parent.exists():
                return None
            raise AppError(ErrorKind.AUTHENTICATION, "cached session directory is unsafe") from exc
        if self.path.is_symlink():
            raise AppError(
                ErrorKind.AUTHENTICATION,
                "refusing to read a symlink at the cached session path",
                code="SESSION_PATH_UNSAFE",
            )
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags)
        except FileNotFoundError:
            return None
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise AppError(
                    ErrorKind.AUTHENTICATION,
                    "refusing to follow a symlink at the cached session path",
                    code="SESSION_PATH_UNSAFE",
                ) from exc
            raise AppError(ErrorKind.AUTHENTICATION, "could not safely read the cached session") from exc
        try:
            metadata = os.fstat(fd)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_uid != os.getuid()
            ):
                raise AppError(
                    ErrorKind.AUTHENTICATION,
                    "cached session ownership or permissions are unsafe; remove it and sign in again",
                    code="SESSION_PERMISSIONS_UNSAFE",
                )
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                fd = -1
                value = json.load(stream)
        except AppError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise AppError(ErrorKind.AUTHENTICATION, "cached session is invalid") from exc
        finally:
            if fd >= 0:
                os.close(fd)
        if not isinstance(value, dict):
            raise AppError(ErrorKind.AUTHENTICATION, "cached session is invalid")
        username, token = value.get("username"), value.get("token")
        if not isinstance(username, str) or not username.strip() or not isinstance(token, str) or not token:
            raise AppError(ErrorKind.AUTHENTICATION, "cached session is invalid")
        return PvmSession(username=username, token=token)

    def save(self, session: PvmSession) -> None:
        parent = self.path.parent
        try:
            self._validate_parent(create=True)
            temporary = parent / f".{self.path.name}.{uuid.uuid4().hex}.tmp"
            payload = json.dumps(
                {"username": session.username, "token": session.token},
                separators=(",", ":"),
            ).encode("utf-8")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(temporary, flags, 0o600)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                os.chmod(self.path, 0o600)
                directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except Exception:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
        except OSError as exc:
            raise AppError(ErrorKind.AUTHENTICATION, "could not securely save the session") from exc

    def clear(self) -> None:
        try:
            if self.path.parent.is_symlink():
                raise AppError(
                    ErrorKind.AUTHENTICATION,
                    "refusing to clear the session through a symlinked state directory",
                    code="SESSION_PATH_UNSAFE",
                )
            if not self.path.parent.exists():
                return
            self._validate_parent(create=False)
            if self.path.is_symlink():
                raise AppError(
                    ErrorKind.AUTHENTICATION,
                    "refusing to remove a symlink at the cached session path",
                    code="SESSION_PATH_UNSAFE",
                )
            self.path.unlink(missing_ok=True)
        except AppError:
            raise
        except OSError as exc:
            raise AppError(ErrorKind.AUTHENTICATION, "could not clear the cached session") from exc


class SessionManager:
    def __init__(self, provider: PvmGateway, settings: Settings, store: SessionStore) -> None:
        self._provider = provider
        self._settings = settings
        self._store = store

    def resume_or_login(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
    ) -> tuple[PvmSession, bool]:
        cached = self._store.load()
        if cached is not None:
            try:
                if self._provider.validate_session(cached):
                    return cached, False
            except AppError as exc:
                raise AppError(
                    ErrorKind.AUTHENTICATION,
                    "cached session could not be validated; check local PVM access",
                    code="SESSION_VALIDATION_FAILED",
                ) from exc
            self._store.clear()
        if username is None or password is None:
            raise AppError(
                ErrorKind.AUTHENTICATION,
                "sign-in is required; provide credentials through the interactive login form",
                code="LOGIN_REQUIRED",
            )
        if not self._settings.allow_credential_argv:
            raise AppError(
                ErrorKind.POLICY,
                "login is blocked because sbell exposes credentials in process arguments; explicit acknowledgement is required",
                code="CREDENTIAL_ARGV_ACK_REQUIRED",
            )
        if not username.strip() or not password:
            raise AppError(ErrorKind.AUTHENTICATION, "username and password are required")
        session = self._provider.login(username.strip(), password)
        self._store.save(session)
        return session, True

    def clear_local_cache(self) -> None:
        self._store.clear()

    def logout(self, session: PvmSession) -> None:
        try:
            self._provider.logout(session)
        finally:
            self._store.clear()

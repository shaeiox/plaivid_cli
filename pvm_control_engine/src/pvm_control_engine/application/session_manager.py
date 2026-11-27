"""Session resume, login, logout, and restrictive local token storage."""

from __future__ import annotations

from pvm_control_engine.application.ports import PvmGateway
from pvm_control_engine.auth.session_store import SessionStore
from pvm_control_engine.config import Settings
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import ErrorKind, PvmSession


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

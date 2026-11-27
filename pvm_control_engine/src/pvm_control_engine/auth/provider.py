"""Validated access to the Engine's locally cached PVM session."""

from __future__ import annotations

from pvm_control_engine.application.ports import PvmGateway
from pvm_control_engine.auth.session_store import SessionStore
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import ErrorKind, PvmSession


class AuthProvider:
    """Load and validate the private session before exposing its token to a command."""

    def __init__(self, store: SessionStore, gateway: PvmGateway) -> None:
        self._store = store
        self._gateway = gateway

    def session(self) -> PvmSession:
        session = self._store.load()
        if session is None:
            raise AppError(ErrorKind.AUTHENTICATION, "login required", code="LOGIN_REQUIRED")
        valid = self._gateway.validate_session(session)
        if not valid:
            self._store.clear()
            raise AppError(ErrorKind.AUTHENTICATION, "login required", code="LOGIN_REQUIRED")
        return session

    def token(self) -> str:
        return self.session().token

    def stored_session(self) -> PvmSession | None:
        """Return the cache for logout without placing the token in a response."""
        return self._store.load()

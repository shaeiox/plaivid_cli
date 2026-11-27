"""User logout command; clears the local session even when no token is cached."""

from pvm_control_engine.application.session_manager import SessionManager
from pvm_control_engine.auth.provider import AuthProvider


class UserLogout:
    def __init__(self, sessions: SessionManager, auth: AuthProvider) -> None:
        self._sessions = sessions
        self._auth = auth

    def execute(self) -> None:
        session = self._auth.stored_session()
        if session is None:
            self._sessions.clear_local_cache()
            return
        self._sessions.logout(session)

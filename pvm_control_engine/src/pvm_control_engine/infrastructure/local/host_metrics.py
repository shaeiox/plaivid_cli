"""Authenticated local read-only host sample query command."""

from pvm_control_engine.auth.provider import AuthProvider


class LocalHostMetrics:
    def __init__(self, application, auth: AuthProvider):
        self._application = application
        self._auth = auth

    def execute(self):
        token = self._auth.token()
        return self._application.refresh(token, sections=("local_host",)).section("local_host")

"""Authenticated sball/show query command."""

from pvm_control_engine.auth.provider import AuthProvider


class SballShow:
    def __init__(self, application, auth: AuthProvider):
        self._application = application
        self._auth = auth

    def execute(self):
        return self._application.host_status(self._auth.token())

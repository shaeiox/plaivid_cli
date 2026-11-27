"""Authenticated network/nic-list query command."""

from pvm_control_engine.auth.provider import AuthProvider


class NetworkNicList:
    def __init__(self, application, auth: AuthProvider):
        self._application = application
        self._auth = auth

    def execute(self):
        return self._application.refresh(self._auth.token(), sections=("physical_nics",)).section(
            "physical_nics"
        )

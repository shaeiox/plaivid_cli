"""Authenticated local read-only physical NIC counter query command."""

from pvm_control_engine.auth.provider import AuthProvider


class LocalNicSamples:
    def __init__(self, application, auth: AuthProvider):
        self._application = application
        self._auth = auth

    def execute(self):
        token = self._auth.token()
        snapshot = self._application.refresh(token, sections=("physical_nics", "nic_samples"))
        return snapshot.section("physical_nics"), snapshot.section("nic_samples")

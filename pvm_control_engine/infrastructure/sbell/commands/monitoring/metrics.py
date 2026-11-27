"""Authenticated monitoring/metrics query command."""

from pvm_control_engine.auth.provider import AuthProvider


class MonitoringMetrics:
    def __init__(self, application, auth: AuthProvider):
        self._application = application
        self._auth = auth

    def execute(self):
        return self._application.host_metrics(self._auth.token())

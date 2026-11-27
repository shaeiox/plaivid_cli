"""Explicit monitoring/metrics query facade."""


class MonitoringMetrics:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str):
        return self.application.host_metrics(token)

"""Read-only audit query facade."""

class LocalAudit:
    def __init__(self, adapter):
        self.adapter = adapter

    def execute(self, limit: int = 100):
        return self.adapter.recent(limit)

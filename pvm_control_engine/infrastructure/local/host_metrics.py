"""Local read-only host sample query facade."""

class LocalHostMetrics:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str):
        return self.application.refresh(token, sections=("local_host",)).section("local_host")

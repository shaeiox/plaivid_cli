"""Explicit sball/show query facade."""


class SballShow:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str):
        return self.application.host_status(token)

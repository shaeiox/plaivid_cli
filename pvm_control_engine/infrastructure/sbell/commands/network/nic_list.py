"""Explicit network/nic-list query facade."""


class NetworkNicList:
    def __init__(self, application):
        self.application = application

    def execute(self, token: str):
        return self.application.refresh(token, sections=("physical_nics",)).section("physical_nics")

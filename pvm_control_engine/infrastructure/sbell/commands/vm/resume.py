"""Explicit vm/resume command facade."""


class VMResume:
    def __init__(self, use_case):
        self.use_case = use_case

    def execute(self, token: str, uuid: str):
        return self.use_case.execute(token, uuid)

"""Explicit vm/pause command facade."""


class VMPause:
    def __init__(self, use_case):
        self.use_case = use_case

    def execute(self, token: str, uuid: str):
        return self.use_case.execute(token, uuid)

    def execute_many(self, token: str, uuids: tuple[str, ...]):
        return self.use_case.execute_many(token, uuids)

"""Explicit user/whoami session-validation command facade."""


class UserWhoami:
    def __init__(self, provider):
        self.provider = provider

    def execute(self, session) -> bool:
        return bool(self.provider.validate_session(session))

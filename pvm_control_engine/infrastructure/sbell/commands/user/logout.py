"""Explicit user/logout command facade."""


class UserLogout:
    def __init__(self, sessions):
        self.sessions = sessions

    def execute(self, session) -> None:
        self.sessions.logout(session)

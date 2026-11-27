"""Explicit user/login command facade; credentials remain behind SessionManager's gate."""


class UserLogin:
    def __init__(self, sessions):
        self.sessions = sessions

    def execute(self, username: str, password: str):
        return self.sessions.resume_or_login(username=username, password=password)

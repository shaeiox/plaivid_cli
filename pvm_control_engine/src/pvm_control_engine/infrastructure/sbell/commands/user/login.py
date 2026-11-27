"""User login command and safe XML parameters for the approved local sbell call."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def login_params(username: str, password: str) -> str:
    root = ET.Element("params")
    ET.SubElement(root, "username").text = username
    ET.SubElement(root, "password").text = password
    return ET.tostring(root, encoding="unicode", short_empty_elements=False)


class UserLogin:
    def __init__(self, sessions):
        self.sessions = sessions

    def execute(self, username: str, password: str):
        return self.sessions.resume_or_login(username=username, password=password)

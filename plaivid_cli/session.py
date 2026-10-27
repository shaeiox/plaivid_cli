"""Session handling: login, token cache and validation.

Requirement: if no valid session is found when the TUI opens, prompt for a
username and password once; otherwise reuse the cached token silently.
"""

import base64
import getpass
import json
import os
import time

from . import config, transport


def _xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Session(object):
    def __init__(self, username, token):
        self.username = username
        self.token = token

    # --- JWT payload (for display only) --------------------------------------
    def claims(self):
        try:
            payload = self.token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            data = base64.urlsafe_b64decode(payload.encode())
            return json.loads(data.decode("utf-8", "replace"))
        except Exception:
            return {}


def _save(session):
    try:
        os.makedirs(config.STATE_DIR, exist_ok=True)
        tmp = config.SESSION_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"username": session.username,
                       "token": session.token,
                       "saved_at": int(time.time())}, fh)
        os.replace(tmp, config.SESSION_FILE)
        try:
            os.chmod(config.SESSION_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass  # a non-persistable cache is not fatal


def _load():
    try:
        with open(config.SESSION_FILE) as fh:
            data = json.load(fh)
        return Session(data.get("username", ""), data.get("token", ""))
    except (OSError, ValueError):
        return None


def clear():
    try:
        os.remove(config.SESSION_FILE)
    except OSError:
        pass


def _is_valid(session):
    """Cheap server-side check that the cached token still works."""
    if not session or not session.token:
        return False
    try:
        resp = transport.sbell("user", "whoami", token=session.token)
    except transport.TransportError:
        return False
    return resp.ok


def _login_params(username, password, delete_uuid=None):
    extra = ""
    if delete_uuid:
        extra = "<session_delete_uuid>%s</session_delete_uuid>" % delete_uuid
    return ("<params><username>%s</username><password>%s</password>%s</params>"
            % (_xml_escape(username), _xml_escape(password), extra))


def _session_uuids(username, password):
    """List the user's current session uuids (needs no token)."""
    params = ("<params><username>%s</username><password>%s</password></params>"
              % (_xml_escape(username), _xml_escape(password)))
    try:
        resp = transport.sbell("user", "list-current-user-sessions", params)
    except transport.TransportError:
        return []
    uuids = []
    if resp.ok and resp.description is not None:
        slist = resp.description.find("pvm_session_list")
        if slist is not None:
            for obj in slist.findall("pvm_um_obj"):
                u = obj.findtext("uuid")
                if u:
                    uuids.append(u)
    return uuids


def login(username, password):
    resp = transport.sbell("user", "login", _login_params(username, password))
    # errno 185 = session cap reached; evict one old session and retry, which
    # is exactly what the web UI does on this error.
    if not resp.ok and resp.errno == "185":
        uuids = _session_uuids(username, password)
        if uuids:
            resp = transport.sbell(
                "user", "login", _login_params(username, password, uuids[0]))
    if not resp.ok:
        raise transport.TransportError(resp.error_text())
    token = resp.token
    if not token:
        raise transport.TransportError("login succeeded but returned no token")
    session = Session(username, token)
    _save(session)
    return session


def logout(session):
    if session and session.token:
        try:
            transport.sbell("user", "logout", token=session.token)
        except transport.TransportError:
            pass
    clear()


def resume_or_prompt(prompt_fn=None):
    """Return a valid Session: reuse the cached one, else prompt to log in.

    ``prompt_fn`` lets the UI own how credentials are collected; the default
    reads from the terminal with getpass.
    """
    cached = _load()
    if _is_valid(cached):
        return cached, False  # (session, newly_logged_in)

    if prompt_fn is None:
        prompt_fn = _default_prompt
    username, password = prompt_fn()
    return login(username, password), True


def _default_prompt():
    username = input("Username [%s]: " % config.DEFAULT_USER).strip() \
        or config.DEFAULT_USER
    password = getpass.getpass("Password: ")
    return username, password

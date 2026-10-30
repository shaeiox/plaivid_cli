from __future__ import annotations

import os
import stat

from plaivid_cli.application.session import SessionManager, SessionStore
from plaivid_cli.config import load_settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import PvmSession


class FakeGateway:
    def __init__(self) -> None:
        self.valid = True
        self.login_calls = 0
        self.logout_calls = 0

    def validate_session(self, session):
        return self.valid

    def login(self, username, password):
        self.login_calls += 1
        return PvmSession(username, "secret-token")

    def logout(self, session):
        self.logout_calls += 1


def test_session_store_round_trips_token_with_restrictive_modes(tmp_path):
    path = tmp_path / "state" / "session.json"
    store = SessionStore(path)
    session = PvmSession("operator", "secret-token")
    store.save(session)
    loaded = store.load()
    assert loaded is not None
    assert loaded.username == "operator"
    assert loaded.token == "secret-token"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    store.clear()
    assert store.load() is None


def test_session_store_rejects_world_readable_token_cache(tmp_path):
    path = tmp_path / "session.json"
    path.write_text('{"username":"operator","token":"secret"}')
    os.chmod(path, 0o644)
    try:
        SessionStore(path).load()
    except AppError as exc:
        assert exc.code == "SESSION_PERMISSIONS_UNSAFE"
    else:
        raise AssertionError("unsafe token cache was accepted")


def test_session_store_rejects_symlinked_session_and_state_directory(tmp_path):
    target = tmp_path / "target.json"
    target.write_text('{"username":"operator","token":"secret"}')
    os.chmod(target, 0o600)
    link = tmp_path / "session.json"
    link.symlink_to(target)
    try:
        SessionStore(link).load()
    except AppError as exc:
        assert exc.code == "SESSION_PATH_UNSAFE"
    else:
        raise AssertionError("symlinked session token was accepted")

    real_dir = tmp_path / "real-state"
    real_dir.mkdir(mode=0o700)
    symlink_dir = tmp_path / "linked-state"
    symlink_dir.symlink_to(real_dir, target_is_directory=True)
    try:
        SessionStore(symlink_dir / "session.json").save(PvmSession("operator", "secret"))
    except AppError as exc:
        assert "securely save" in str(exc)
    else:
        raise AssertionError("session was saved through a symlinked directory")


def test_session_store_rejects_insecure_state_directory(tmp_path):
    directory = tmp_path / "state"
    directory.mkdir(mode=0o700)
    os.chmod(directory, 0o755)
    path = directory / "session.json"
    path.write_text('{"username":"operator","token":"secret"}')
    os.chmod(path, 0o600)
    try:
        SessionStore(path).load()
    except AppError as exc:
        assert "directory is unsafe" in str(exc)
    else:
        raise AssertionError("session in public state directory was accepted")


def test_session_manager_reuses_valid_token_without_prompt_or_login(tmp_path):
    gateway = FakeGateway()
    store = SessionStore(tmp_path / "session.json")
    store.save(PvmSession("operator", "cached"))
    manager = SessionManager(gateway, load_settings({}), store)
    session, newly_logged_in = manager.resume_or_login()
    assert session.token == "cached"
    assert not newly_logged_in
    assert gateway.login_calls == 0


def test_login_is_default_denied_before_gateway_invocation(tmp_path):
    gateway = FakeGateway()
    manager = SessionManager(gateway, load_settings({}), SessionStore(tmp_path / "session.json"))
    try:
        manager.resume_or_login(username="operator", password="secret")
    except AppError as exc:
        assert exc.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
    else:
        raise AssertionError("credential argv gate was bypassed")
    assert gateway.login_calls == 0


def test_login_requires_explicit_argv_acknowledgement_and_persists(tmp_path):
    gateway = FakeGateway()
    settings = load_settings({"PLAIVID_ALLOW_CREDENTIAL_ARGV": "true"})
    store = SessionStore(tmp_path / "session.json")
    manager = SessionManager(gateway, settings, store)
    session, newly_logged_in = manager.resume_or_login(username="operator", password="secret")
    assert newly_logged_in
    assert session.token == "secret-token"
    assert store.load().token == "secret-token"
    assert gateway.login_calls == 1


def test_invalid_cached_session_is_cleared_and_requires_new_credentials(tmp_path):
    gateway = FakeGateway()
    gateway.valid = False
    store = SessionStore(tmp_path / "session.json")
    store.save(PvmSession("operator", "expired"))
    manager = SessionManager(gateway, load_settings({}), store)
    try:
        manager.resume_or_login()
    except AppError as exc:
        assert exc.code == "LOGIN_REQUIRED"
    else:
        raise AssertionError("expired session unexpectedly resumed")
    assert store.load() is None

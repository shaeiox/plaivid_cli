from __future__ import annotations

import pytest

from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import ErrorKind, PvmSession


class Store:
    def __init__(self, session):
        self.value = session
        self.clears = 0

    def load(self):
        return self.value

    def clear(self):
        self.clears += 1
        self.value = None


class Gateway:
    def __init__(self, valid=True, error=None):
        self.valid = valid
        self.error = error
        self.checked = []

    def validate_session(self, session):
        self.checked.append(session)
        if self.error is not None:
            raise self.error
        return self.valid


def test_auth_provider_returns_only_a_valid_cached_session_token():
    session = PvmSession("operator", "synthetic-token")
    store = Store(session)
    gateway = Gateway()
    auth = AuthProvider(store, gateway)

    assert auth.token() == "synthetic-token"
    assert gateway.checked == [session]


def test_auth_provider_clears_expired_cache_and_rejects_missing_session():
    store = Store(PvmSession("operator", "expired-token"))
    auth = AuthProvider(store, Gateway(valid=False))

    with pytest.raises(AppError) as caught:
        auth.token()

    assert caught.value.code == "LOGIN_REQUIRED"
    assert store.clears == 1
    assert store.load() is None


def test_auth_provider_does_not_hide_credential_gate_or_process_errors():
    failure = AppError(
        ErrorKind.POLICY,
        "credential argv acknowledgement required",
        code="CREDENTIAL_ARGV_ACK_REQUIRED",
    )
    auth = AuthProvider(Store(PvmSession("operator", "token")), Gateway(error=failure))

    with pytest.raises(AppError) as caught:
        auth.token()

    assert caught.value is failure
    assert caught.value.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
